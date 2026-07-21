from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass(slots=True)
class BacktestResult:
    trades: pd.DataFrame
    summary: pd.DataFrame


class NormalizedSignalBacktestRunner:
    """Run next-close backtests from normalized strategy signal rows."""

    def run(self, symbol: str, signal_rows: pd.DataFrame) -> BacktestResult:
        if signal_rows.empty:
            empty = pd.DataFrame(columns=self._trade_columns())
            return BacktestResult(trades=empty, summary=self._build_summary(symbol, empty, signal_rows))

        frame = signal_rows.copy()
        frame["date"] = pd.to_datetime(frame["date"], errors="coerce")
        frame = frame.sort_values("date").reset_index(drop=True)

        trades: list[dict[str, object]] = []
        open_position: dict[str, object] | None = None

        for index, row in frame.iterrows():
            signal = str(row.get("signal", "hold")).strip().lower()
            if signal == "buy" and open_position is None:
                entry_index = index + 1
                if entry_index >= len(frame):
                    continue
                entry_row = frame.iloc[entry_index]
                open_position = {
                    "symbol": symbol,
                    "strategy_id": row.get("strategy_id"),
                    "strategy_name": row.get("strategy_name"),
                    "entry_signal_date": row["date"],
                    "entry_date": entry_row["date"],
                    "entry_price": float(entry_row["close"]),
                }
                continue

            if signal == "sell" and open_position is not None:
                exit_index = index + 1
                if exit_index >= len(frame):
                    exit_index = len(frame) - 1
                    exit_reason = "sell_signal_final_close"
                else:
                    exit_reason = "sell_signal"
                exit_row = frame.iloc[exit_index]
                trades.append(self._close_position(open_position, row["date"], exit_row, exit_reason))
                open_position = None

        if open_position is not None:
            final_row = frame.iloc[-1]
            trades.append(self._close_position(open_position, final_row["date"], final_row, "final_close"))

        trades_frame = pd.DataFrame(trades, columns=self._trade_columns())
        return BacktestResult(trades=trades_frame, summary=self._build_summary(symbol, trades_frame, frame))

    def _close_position(
        self,
        position: dict[str, object],
        exit_signal_date: pd.Timestamp,
        exit_row: pd.Series,
        exit_reason: str,
    ) -> dict[str, object]:
        entry_price = float(position["entry_price"])
        exit_price = float(exit_row["close"])
        entry_date = pd.Timestamp(position["entry_date"])
        exit_date = pd.Timestamp(exit_row["date"])
        return {
            "symbol": position["symbol"],
            "strategy_id": position.get("strategy_id"),
            "strategy_name": position.get("strategy_name"),
            "entry_signal_date": pd.Timestamp(position["entry_signal_date"]),
            "entry_date": entry_date,
            "entry_price": entry_price,
            "exit_signal_date": pd.Timestamp(exit_signal_date),
            "exit_date": exit_date,
            "exit_price": exit_price,
            "return_pct": ((exit_price / entry_price) - 1.0) * 100.0,
            "holding_days": max((exit_date - entry_date).days, 0),
            "exit_reason": exit_reason,
        }

    def _build_summary(self, symbol: str, trades_frame: pd.DataFrame, signal_frame: pd.DataFrame) -> pd.DataFrame:
        signals = signal_frame.get("signal")
        signal_series = signals.astype(str).str.lower() if signals is not None else pd.Series(dtype="object")
        buy_signal_count = int((signal_series == "buy").sum())
        sell_signal_count = int((signal_series == "sell").sum())
        strategy_id = _first_present(signal_frame.get("strategy_id"))
        strategy_name = _first_present(signal_frame.get("strategy_name"))

        if trades_frame.empty:
            return pd.DataFrame(
                [
                    {
                        "symbol": symbol,
                        "strategy_id": strategy_id,
                        "strategy_name": strategy_name,
                        "source_rows": len(signal_frame),
                        "buy_signal_count": buy_signal_count,
                        "sell_signal_count": sell_signal_count,
                        "trade_count": 0,
                        "win_rate_pct": 0.0,
                        "average_return_pct": 0.0,
                        "total_return_pct": 0.0,
                        "max_drawdown_pct": 0.0,
                        "final_equity": 1.0,
                    }
                ]
            )

        trade_returns = trades_frame["return_pct"].astype(float) / 100.0
        equity_curve = (1.0 + trade_returns).cumprod()
        rolling_peak = equity_curve.cummax()
        drawdowns = ((equity_curve / rolling_peak) - 1.0) * 100.0
        winning_trades = int((trades_frame["return_pct"].astype(float) > 0).sum())
        trade_count = len(trades_frame)

        return pd.DataFrame(
            [
                {
                    "symbol": symbol,
                    "strategy_id": strategy_id,
                    "strategy_name": strategy_name,
                    "source_rows": len(signal_frame),
                    "buy_signal_count": buy_signal_count,
                    "sell_signal_count": sell_signal_count,
                    "trade_count": trade_count,
                    "win_rate_pct": (winning_trades / trade_count) * 100.0,
                    "average_return_pct": float(trades_frame["return_pct"].mean()),
                    "total_return_pct": (float(equity_curve.iloc[-1]) - 1.0) * 100.0,
                    "max_drawdown_pct": abs(float(drawdowns.min())) if not drawdowns.empty else 0.0,
                    "final_equity": float(equity_curve.iloc[-1]),
                }
            ]
        )

    @staticmethod
    def _trade_columns() -> list[str]:
        return [
            "symbol",
            "strategy_id",
            "strategy_name",
            "entry_signal_date",
            "entry_date",
            "entry_price",
            "exit_signal_date",
            "exit_date",
            "exit_price",
            "return_pct",
            "holding_days",
            "exit_reason",
        ]


DEFAULT_BACKTEST_RUNNER = NormalizedSignalBacktestRunner()


def _first_present(series: pd.Series | None) -> object | None:
    if series is None:
        return None
    non_null = series.dropna()
    if non_null.empty:
        return None
    return non_null.iloc[0]
