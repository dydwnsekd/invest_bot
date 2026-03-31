from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from invest_bot.market.storage import CsvStorage, SavedDataset


@dataclass(slots=True)
class IndicatorRequest:
    symbol: str
    source_filename: str


class DailyPriceAnalyzer:
    """Load saved daily price CSV files and calculate starter indicators."""

    def __init__(
        self,
        raw_storage: CsvStorage | None = None,
        processed_storage: CsvStorage | None = None,
    ) -> None:
        self.raw_storage = raw_storage or CsvStorage("data/raw/domestic_stock")
        self.processed_storage = processed_storage or CsvStorage("data/processed/domestic_stock")

    def load_daily_prices(self, request: IndicatorRequest) -> pd.DataFrame:
        file_path = self.raw_storage.root_dir / "daily_prices" / request.source_filename
        frame = pd.read_csv(file_path)
        return self._normalize_daily_prices(frame)

    def calculate_indicators(self, frame: pd.DataFrame) -> pd.DataFrame:
        if frame.empty:
            return frame.copy()

        result = frame.copy()
        result["close"] = pd.to_numeric(result["close"], errors="coerce")
        result["volume"] = pd.to_numeric(result["volume"], errors="coerce")

        result["ma_5"] = result["close"].rolling(window=5, min_periods=5).mean()
        result["ma_20"] = result["close"].rolling(window=20, min_periods=20).mean()
        result["ma_60"] = result["close"].rolling(window=60, min_periods=60).mean()
        result["volume_ma_5"] = result["volume"].rolling(window=5, min_periods=5).mean()
        result["rsi_14"] = self._calculate_rsi(result["close"], period=14)
        return result

    def save_indicators(self, filename: str, frame: pd.DataFrame) -> SavedDataset:
        return self.processed_storage.save("daily_prices_indicators", filename, frame)

    @staticmethod
    def _normalize_daily_prices(frame: pd.DataFrame) -> pd.DataFrame:
        result = frame.copy()
        rename_map = {
            "stck_bsop_date": "date",
            "stck_oprc": "open",
            "stck_hgpr": "high",
            "stck_lwpr": "low",
            "stck_clpr": "close",
            "acml_vol": "volume",
            "acml_tr_pbmn": "turnover",
        }
        result = result.rename(columns=rename_map)

        if "date" in result.columns:
            result["date"] = pd.to_datetime(result["date"], format="%Y%m%d", errors="coerce")

        numeric_columns = ["open", "high", "low", "close", "volume", "turnover"]
        for column in numeric_columns:
            if column in result.columns:
                result[column] = pd.to_numeric(result[column], errors="coerce")

        sort_columns = ["date"] if "date" in result.columns else None
        if sort_columns:
            result = result.sort_values(sort_columns).reset_index(drop=True)

        return result

    @staticmethod
    def _calculate_rsi(series: pd.Series, period: int) -> pd.Series:
        delta = series.diff()
        gain = delta.clip(lower=0)
        loss = -delta.clip(upper=0)
        avg_gain = gain.rolling(window=period, min_periods=period).mean()
        avg_loss = loss.rolling(window=period, min_periods=period).mean()
        relative_strength = avg_gain / avg_loss.replace(0, pd.NA)
        rsi = 100 - (100 / (1 + relative_strength))
        return rsi
