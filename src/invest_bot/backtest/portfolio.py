"""Transparent equal-weight portfolio aggregation for backtest equity curves."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

import pandas as pd

from .runner import DEFAULT_MARK_TO_MARKET_INITIAL_EQUITY


PORTFOLIO_EQUITY_COLUMNS = (
    "date",
    "equity",
    "equity_return_pct",
    "position_state",
    "symbol",
    "symbol_name",
    "strategy_id",
    "strategy_name",
    "series_label",
    "constituent_count",
    "weighting_method",
    "rebalancing_method",
    "date_policy",
)
PORTFOLIO_SUMMARY_COLUMNS = (
    "strategy_id",
    "strategy_name",
    "start_date",
    "end_date",
    "initial_equity",
    "final_equity",
    "total_return_pct",
    "max_drawdown_pct",
    "included_symbol_count",
    "excluded_symbol_count",
    "weighting_method",
    "rebalancing_method",
    "date_policy",
)
PORTFOLIO_CONSTITUENT_COLUMNS = (
    "strategy_id",
    "strategy_name",
    "symbol",
    "symbol_name",
    "status",
    "reason",
    "weight_pct",
    "start_equity",
    "end_equity",
    "constituent_return_pct",
    "contribution_pct_point",
)
PORTFOLIO_WEIGHTING_METHOD = "동일 비중"
PORTFOLIO_REBALANCING_METHOD = "리밸런싱 없음"
PORTFOLIO_DATE_POLICY = "공통 거래일"


@dataclass(frozen=True, slots=True)
class PortfolioAggregationResult:
    """Portfolio curves, summaries, and constituent inclusion decisions."""

    equity_frame: pd.DataFrame
    summary_frame: pd.DataFrame
    constituent_frame: pd.DataFrame
    notices: tuple[str, ...]


def build_equal_weight_portfolios(
    daily_equity_frame: pd.DataFrame,
    *,
    selected_symbols: list[str],
    initial_equity: float = DEFAULT_MARK_TO_MARKET_INITIAL_EQUITY,
) -> PortfolioAggregationResult:
    """Aggregate each strategy separately using equal initial allocations.

    The first common trading day is rebased to ``initial_equity`` for every
    constituent. This prevents performance before another constituent's data
    begins from changing the comparable portfolio period. Each constituent is
    then left untouched: no daily or periodic rebalancing is applied.
    """

    symbols = tuple(
        dict.fromkeys(str(symbol).strip() for symbol in selected_symbols if str(symbol).strip())
    )
    if len(symbols) < 2:
        return _empty_result("포트폴리오 집계는 종목을 두 개 이상 선택했을 때만 계산합니다.")
    if initial_equity <= 0:
        raise ValueError("포트폴리오 초기자금은 0보다 커야 합니다.")
    required_columns = {"date", "equity", "symbol", "strategy_id"}
    if daily_equity_frame.empty or not required_columns.issubset(daily_equity_frame.columns):
        return _empty_result("포트폴리오에 사용할 일별 평가금액 데이터가 없습니다.")

    normalized = daily_equity_frame.copy()
    normalized["date"] = pd.to_datetime(normalized["date"], errors="coerce")
    normalized["equity"] = pd.to_numeric(normalized["equity"], errors="coerce")
    normalized["symbol"] = normalized["symbol"].astype(str).str.strip()
    normalized["strategy_id"] = normalized["strategy_id"].astype(str).str.strip()
    normalized = normalized[
        normalized["symbol"].isin(symbols)
        & normalized["strategy_id"].ne("")
        & normalized["date"].notna()
    ].copy()
    if normalized.empty:
        return _empty_result("선택한 종목에 맞는 일별 평가금액 데이터가 없습니다.")

    strategy_ids = list(dict.fromkeys(normalized["strategy_id"].tolist()))
    curves: list[pd.DataFrame] = []
    summaries: list[dict[str, object]] = []
    constituents: list[pd.DataFrame] = []
    notices: list[str] = []
    for strategy_id in strategy_ids:
        strategy_result = _build_strategy_portfolio(
            normalized[normalized["strategy_id"] == strategy_id],
            selected_symbols=symbols,
            initial_equity=float(initial_equity),
        )
        constituents.append(strategy_result.constituent_frame)
        notices.extend(strategy_result.notices)
        if not strategy_result.equity_frame.empty:
            curves.append(strategy_result.equity_frame)
        if not strategy_result.summary_frame.empty:
            summaries.extend(strategy_result.summary_frame.to_dict("records"))

    return PortfolioAggregationResult(
        equity_frame=pd.concat(curves, ignore_index=True) if curves else _empty_frame(PORTFOLIO_EQUITY_COLUMNS),
        summary_frame=pd.DataFrame(summaries, columns=PORTFOLIO_SUMMARY_COLUMNS),
        constituent_frame=(
            pd.concat(constituents, ignore_index=True)
            if constituents
            else _empty_frame(PORTFOLIO_CONSTITUENT_COLUMNS)
        ),
        notices=tuple(dict.fromkeys(notices)),
    )


def _build_strategy_portfolio(
    strategy_frame: pd.DataFrame,
    *,
    selected_symbols: tuple[str, ...],
    initial_equity: float,
) -> PortfolioAggregationResult:
    strategy_id = str(strategy_frame["strategy_id"].iloc[0])
    strategy_name = _first_text(strategy_frame, "strategy_name") or strategy_id
    member_frames: dict[str, pd.DataFrame] = {}
    constituent_rows: list[dict[str, object]] = []
    for symbol in selected_symbols:
        member = _normalize_member_frame(strategy_frame[strategy_frame["symbol"] == symbol])
        symbol_name = _first_text(member, "symbol_name") or _first_text(
            strategy_frame[strategy_frame["symbol"] == symbol], "symbol_name"
        )
        if len(member) < 2:
            constituent_rows.append(
                _excluded_constituent_row(
                    strategy_id,
                    strategy_name,
                    symbol,
                    symbol_name,
                    "유효한 일별 평가금액이 2일 미만",
                )
            )
            continue
        member_frames[symbol] = member

    if len(member_frames) < 2:
        return _unavailable_strategy_result(
            strategy_id,
            strategy_name,
            constituent_rows,
            "포함 가능한 종목이 2개 미만입니다.",
        )

    common_dates = _common_dates(member_frames.values())
    if len(common_dates) < 2:
        for symbol, member in member_frames.items():
            constituent_rows.append(
                _excluded_constituent_row(
                    strategy_id,
                    strategy_name,
                    symbol,
                    _first_text(member, "symbol_name"),
                    "공통 거래일이 2일 미만",
                )
            )
        return _unavailable_strategy_result(
            strategy_id,
            strategy_name,
            constituent_rows,
            "공통 거래일이 2일 미만입니다.",
        )

    weight = 1.0 / len(member_frames)
    wealth_indices: list[pd.Series] = []
    for symbol, member in member_frames.items():
        aligned = member.set_index("date").loc[common_dates]
        base_equity = float(aligned["equity"].iloc[0])
        wealth_index = aligned["equity"] / base_equity
        wealth_indices.append(wealth_index.rename(symbol))
        final_index = float(wealth_index.iloc[-1])
        constituent_rows.append(
            {
                "strategy_id": strategy_id,
                "strategy_name": strategy_name,
                "symbol": symbol,
                "symbol_name": _first_text(member, "symbol_name"),
                "status": "포함",
                "reason": "공통 거래일 기준 포함",
                "weight_pct": weight * 100.0,
                "start_equity": initial_equity * weight,
                "end_equity": initial_equity * weight * final_index,
                "constituent_return_pct": (final_index - 1.0) * 100.0,
                "contribution_pct_point": weight * (final_index - 1.0) * 100.0,
            }
        )

    wealth_frame = pd.concat(wealth_indices, axis=1)
    portfolio_equity = wealth_frame.mean(axis=1) * initial_equity
    portfolio_returns = ((portfolio_equity / initial_equity) - 1.0) * 100.0
    rolling_peak = portfolio_equity.cummax()
    max_drawdown_pct = abs(float((((portfolio_equity / rolling_peak) - 1.0) * 100.0).min()))
    equity_frame = pd.DataFrame(
        {
            "date": common_dates,
            "equity": portfolio_equity.to_numpy(),
            "equity_return_pct": portfolio_returns.to_numpy(),
            "position_state": PORTFOLIO_REBALANCING_METHOD,
            "symbol": "portfolio",
            "symbol_name": "포트폴리오",
            "strategy_id": strategy_id,
            "strategy_name": strategy_name,
            "series_label": f"포트폴리오 · {strategy_name}",
            "constituent_count": len(member_frames),
            "weighting_method": PORTFOLIO_WEIGHTING_METHOD,
            "rebalancing_method": PORTFOLIO_REBALANCING_METHOD,
            "date_policy": PORTFOLIO_DATE_POLICY,
        }
    )
    summary_frame = pd.DataFrame(
        [
            {
                "strategy_id": strategy_id,
                "strategy_name": strategy_name,
                "start_date": common_dates[0],
                "end_date": common_dates[-1],
                "initial_equity": initial_equity,
                "final_equity": float(portfolio_equity.iloc[-1]),
                "total_return_pct": float(portfolio_returns.iloc[-1]),
                "max_drawdown_pct": max_drawdown_pct,
                "included_symbol_count": len(member_frames),
                "excluded_symbol_count": len(selected_symbols) - len(member_frames),
                "weighting_method": PORTFOLIO_WEIGHTING_METHOD,
                "rebalancing_method": PORTFOLIO_REBALANCING_METHOD,
                "date_policy": PORTFOLIO_DATE_POLICY,
            }
        ],
        columns=PORTFOLIO_SUMMARY_COLUMNS,
    )
    return PortfolioAggregationResult(
        equity_frame=equity_frame,
        summary_frame=summary_frame,
        constituent_frame=pd.DataFrame(constituent_rows, columns=PORTFOLIO_CONSTITUENT_COLUMNS),
        notices=(),
    )


def _normalize_member_frame(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return frame.copy()
    return (
        frame.assign(equity=lambda value: pd.to_numeric(value["equity"], errors="coerce"))
        .dropna(subset=["date", "equity"])
        .loc[lambda value: value["equity"] > 0]
        .sort_values("date")
        .drop_duplicates(subset=["date"], keep="last")
        .reset_index(drop=True)
    )


def _common_dates(member_frames: Iterable[pd.DataFrame]) -> list[pd.Timestamp]:
    date_sets = [set(member["date"]) for member in member_frames]
    shared_dates = set.intersection(*date_sets) if date_sets else set()
    return sorted(pd.Timestamp(value) for value in shared_dates)


def _unavailable_strategy_result(
    strategy_id: str,
    strategy_name: str,
    constituent_rows: list[dict[str, object]],
    reason: str,
) -> PortfolioAggregationResult:
    return PortfolioAggregationResult(
        equity_frame=_empty_frame(PORTFOLIO_EQUITY_COLUMNS),
        summary_frame=_empty_frame(PORTFOLIO_SUMMARY_COLUMNS),
        constituent_frame=pd.DataFrame(constituent_rows, columns=PORTFOLIO_CONSTITUENT_COLUMNS),
        notices=(f"{strategy_name} 포트폴리오를 계산하지 않았습니다: {reason}",),
    )


def _excluded_constituent_row(
    strategy_id: str,
    strategy_name: str,
    symbol: str,
    symbol_name: str,
    reason: str,
) -> dict[str, object]:
    return {
        "strategy_id": strategy_id,
        "strategy_name": strategy_name,
        "symbol": symbol,
        "symbol_name": symbol_name,
        "status": "제외",
        "reason": reason,
        "weight_pct": None,
        "start_equity": None,
        "end_equity": None,
        "constituent_return_pct": None,
        "contribution_pct_point": None,
    }


def _empty_result(notice: str) -> PortfolioAggregationResult:
    return PortfolioAggregationResult(
        equity_frame=_empty_frame(PORTFOLIO_EQUITY_COLUMNS),
        summary_frame=_empty_frame(PORTFOLIO_SUMMARY_COLUMNS),
        constituent_frame=_empty_frame(PORTFOLIO_CONSTITUENT_COLUMNS),
        notices=(notice,),
    )


def _empty_frame(columns: tuple[str, ...]) -> pd.DataFrame:
    return pd.DataFrame(columns=list(columns))


def _first_text(frame: pd.DataFrame, column: str) -> str:
    if column not in frame.columns:
        return ""
    values = frame[column].dropna().astype(str).str.strip()
    non_empty = values[values.ne("")]
    return "" if non_empty.empty else str(non_empty.iloc[0])
