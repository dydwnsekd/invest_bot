from __future__ import annotations

import pandas as pd
import pytest

from invest_bot.backtest import build_equal_weight_portfolios


def _curve(
    symbol: str,
    values: list[float],
    *,
    strategy_id: str = "rsi",
    strategy_name: str = "RSI",
    dates: list[str] | None = None,
) -> pd.DataFrame:
    resolved_dates = dates or [f"2026-04-{index + 1:02d}" for index in range(len(values))]
    return pd.DataFrame(
        {
            "date": resolved_dates,
            "equity": values,
            "symbol": symbol,
            "symbol_name": f"종목 {symbol}",
            "strategy_id": strategy_id,
            "strategy_name": strategy_name,
        }
    )


def test_equal_weight_portfolio_keeps_initial_allocations_without_rebalancing() -> None:
    result = build_equal_weight_portfolios(
        pd.concat(
            [
                _curve("A", [1_000_000, 2_000_000, 1_000_000]),
                _curve("B", [1_000_000, 500_000, 1_000_000]),
            ],
            ignore_index=True,
        ),
        selected_symbols=["A", "B"],
    )

    assert result.equity_frame["equity"].tolist() == [1_000_000.0, 1_250_000.0, 1_000_000.0]
    assert result.equity_frame["equity_return_pct"].tolist() == [0.0, 25.0, 0.0]
    assert result.summary_frame.iloc[0]["rebalancing_method"] == "리밸런싱 없음"


def test_portfolio_uses_common_dates_and_rebases_each_member_at_common_start() -> None:
    result = build_equal_weight_portfolios(
        pd.concat(
            [
                _curve("A", [1_000_000, 1_100_000, 1_210_000]),
                _curve(
                    "B",
                    [800_000, 880_000, 968_000],
                    dates=["2026-04-02", "2026-04-03", "2026-04-04"],
                ),
            ],
            ignore_index=True,
        ),
        selected_symbols=["A", "B"],
    )

    assert result.equity_frame["date"].dt.strftime("%Y-%m-%d").tolist() == ["2026-04-02", "2026-04-03"]
    assert result.equity_frame["equity"].tolist() == [1_000_000.0, 1_100_000.0]
    assert result.equity_frame["equity_return_pct"].tolist() == pytest.approx([0.0, 10.0])
    assert result.summary_frame.iloc[0]["date_policy"] == "공통 거래일"


def test_portfolio_contributions_sum_to_the_total_return() -> None:
    result = build_equal_weight_portfolios(
        pd.concat(
            [
                _curve("A", [1_000_000, 1_100_000, 1_210_000]),
                _curve("B", [1_000_000, 900_000, 990_000]),
            ],
            ignore_index=True,
        ),
        selected_symbols=["A", "B"],
    )

    constituents = result.constituent_frame.set_index("symbol")
    summary = result.summary_frame.iloc[0]
    assert constituents["weight_pct"].sum() == pytest.approx(100.0)
    assert constituents.loc["A", "contribution_pct_point"] == pytest.approx(10.5)
    assert constituents.loc["B", "contribution_pct_point"] == pytest.approx(-0.5)
    assert constituents["contribution_pct_point"].sum() == pytest.approx(summary["total_return_pct"])
    assert constituents["end_equity"].sum() == pytest.approx(summary["final_equity"])


def test_portfolio_excludes_invalid_constituent_and_reweights_remaining_symbols() -> None:
    result = build_equal_weight_portfolios(
        pd.concat(
            [
                _curve("A", [1_000_000, 1_100_000]),
                _curve("B", [1_000_000, 900_000]),
                _curve("C", [float("nan")], dates=["2026-04-01"]),
            ],
            ignore_index=True,
        ),
        selected_symbols=["A", "B", "C"],
    )

    constituents = result.constituent_frame.set_index("symbol")
    assert constituents.loc["A", "weight_pct"] == pytest.approx(50.0)
    assert constituents.loc["B", "weight_pct"] == pytest.approx(50.0)
    assert constituents.loc["C", "status"] == "제외"
    assert constituents.loc["C", "reason"] == "유효한 일별 평가금액이 2일 미만"
    assert result.summary_frame.iloc[0]["excluded_symbol_count"] == 1


def test_equal_weight_portfolio_weights_always_sum_to_one_hundred_percent() -> None:
    result = build_equal_weight_portfolios(
        pd.concat(
            [
                _curve("A", [1_000_000, 1_100_000]),
                _curve("B", [1_000_000, 900_000]),
                _curve("C", [1_000_000, 1_000_000]),
            ],
            ignore_index=True,
        ),
        selected_symbols=["A", "B", "C"],
    )

    assert result.constituent_frame["weight_pct"].sum() == pytest.approx(100.0)
    assert result.constituent_frame["weight_pct"].tolist() == pytest.approx([100.0 / 3.0] * 3)


def test_portfolio_marks_strategy_unavailable_without_two_common_trading_days() -> None:
    result = build_equal_weight_portfolios(
        pd.concat(
            [
                _curve("A", [1_000_000, 1_100_000], dates=["2026-04-01", "2026-04-02"]),
                _curve("B", [1_000_000, 1_100_000], dates=["2026-04-03", "2026-04-04"]),
            ],
            ignore_index=True,
        ),
        selected_symbols=["A", "B"],
    )

    assert result.equity_frame.empty
    assert result.summary_frame.empty
    assert set(result.constituent_frame["status"]) == {"제외"}
    assert any("공통 거래일이 2일 미만" in notice for notice in result.notices)


def test_portfolios_are_separated_by_strategy() -> None:
    frame = pd.concat(
        [
            _curve("A", [1_000_000, 1_100_000], strategy_id="rsi", strategy_name="RSI"),
            _curve("B", [1_000_000, 1_100_000], strategy_id="rsi", strategy_name="RSI"),
            _curve("A", [1_000_000, 900_000], strategy_id="momentum", strategy_name="Momentum"),
            _curve("B", [1_000_000, 900_000], strategy_id="momentum", strategy_name="Momentum"),
        ],
        ignore_index=True,
    )

    result = build_equal_weight_portfolios(frame, selected_symbols=["A", "B"])

    summary = result.summary_frame.set_index("strategy_id")
    assert set(summary.index) == {"rsi", "momentum"}
    assert summary.loc["rsi", "total_return_pct"] == pytest.approx(10.0)
    assert summary.loc["momentum", "total_return_pct"] == pytest.approx(-10.0)
