from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from invest_bot.market.repositories import DatasetStorage
from invest_bot.market.storage import CsvStorage, SavedDataset
from invest_bot.strategy import GoldenCrossStrategy


@dataclass(slots=True)
class GoldenCrossSignalRequest:
    symbol: str
    source_filename: str


class GoldenCrossSignalGenerator:
    """Generate golden-cross signals from saved indicator CSV files."""

    def __init__(self, processed_storage: DatasetStorage | None = None) -> None:
        self.processed_storage = processed_storage or CsvStorage("data/processed/domestic_stock")
        self.strategy = GoldenCrossStrategy()

    def load_indicator_frame(self, request: GoldenCrossSignalRequest) -> pd.DataFrame:
        file_path = self.processed_storage.root_dir / "daily_prices_indicators" / request.source_filename
        frame = pd.read_csv(file_path)
        if "date" in frame.columns:
            frame["date"] = pd.to_datetime(frame["date"], errors="coerce")
        return frame.sort_values("date").reset_index(drop=True) if "date" in frame.columns else frame

    def generate_signals(self, frame: pd.DataFrame) -> pd.DataFrame:
        if frame.empty:
            return frame.copy()

        result = frame.copy()
        result["signal"] = "hold"
        result["signal_reason"] = "Not enough data to detect a crossover."
        result["signal_prev_ma_5"] = pd.NA
        result["signal_prev_ma_20"] = pd.NA
        result["signal_ma_5"] = pd.NA
        result["signal_ma_20"] = pd.NA

        for index in range(1, len(result)):
            window = result.iloc[index - 1 : index + 1]
            signal_result = self.strategy.evaluate_frame(window)

            result.at[index, "signal"] = signal_result.signal.value
            result.at[index, "signal_reason"] = signal_result.reason
            result.at[index, "signal_prev_ma_5"] = signal_result.indicators.get("prev_ma_5")
            result.at[index, "signal_prev_ma_20"] = signal_result.indicators.get("prev_ma_20")
            result.at[index, "signal_ma_5"] = signal_result.indicators.get("ma_5")
            result.at[index, "signal_ma_20"] = signal_result.indicators.get("ma_20")

        return result

    def save_signals(self, filename: str, frame: pd.DataFrame) -> SavedDataset:
        return self.processed_storage.save("golden_cross_signals", filename, frame)
