from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from invest_bot.market.repositories import DatasetStorage
from invest_bot.market.storage import CsvStorage, SavedDataset


@dataclass(slots=True)
class BacktestRequest:
    symbol: str
    source_filename: str


@dataclass(slots=True)
class BacktestResult:
    trades: pd.DataFrame
    summary: pd.DataFrame


class GoldenCrossBacktestGenerator:
    """Draft backtest runner for golden cross signals."""

    def __init__(self, processed_storage: DatasetStorage | None = None) -> None:
        self.processed_storage = processed_storage or CsvStorage("data/processed/domestic_stock")

    def load_signal_frame(self, request: BacktestRequest) -> pd.DataFrame:
        frame = pd.read_csv(
            self.processed_storage.root_dir / "golden_cross_signals" / request.source_filename
        )
        if "date" in frame.columns:
            frame["date"] = pd.to_datetime(frame["date"])
        return frame.sort_values("date").reset_index(drop=True)

    def run_backtest(self, symbol: str, signal_frame: pd.DataFrame) -> BacktestResult:
        if signal_frame.empty:
            return BacktestResult(
                trades=pd.DataFrame(
                    columns=[
                        "symbol",
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
                ),
                summary=self._build_summary(symbol, pd.DataFrame(), signal_frame),
            )

        frame = signal_frame.sort_values("date").reset_index(drop=True).copy()
        trades: list[dict[str, object]] = []
        open_position: dict[str, object] | None = None

        for index, row in frame.iterrows():
            signal = str(row.get("signal", "hold")).lower()

            if signal == "buy" and open_position is None:
                entry_index = index + 1
                if entry_index >= len(frame):
                    continue
                entry_row = frame.iloc[entry_index]
                open_position = {
                    "symbol": symbol,
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

        trades_frame = pd.DataFrame(trades)
        summary_frame = self._build_summary(symbol, trades_frame, frame)
        return BacktestResult(trades=trades_frame, summary=summary_frame)

    def save_trades(self, source_filename: str, trades: pd.DataFrame) -> SavedDataset:
        return self.processed_storage.save("backtest_trades", source_filename, trades)

    def save_summary(self, source_filename: str, summary: pd.DataFrame) -> SavedDataset:
        return self.processed_storage.save("backtest_summaries", source_filename, summary)

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

    def _build_summary(
        self,
        symbol: str,
        trades_frame: pd.DataFrame,
        signal_frame: pd.DataFrame,
    ) -> pd.DataFrame:
        buy_signal_count = int((signal_frame.get("signal") == "buy").sum()) if "signal" in signal_frame else 0
        sell_signal_count = int((signal_frame.get("signal") == "sell").sum()) if "signal" in signal_frame else 0

        if trades_frame.empty:
            return pd.DataFrame(
                [
                    {
                        "symbol": symbol,
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
