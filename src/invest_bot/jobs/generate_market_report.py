from __future__ import annotations

from dataclasses import dataclass

import pandas as pd
from pandas.errors import EmptyDataError

from invest_bot.config.settings import AppSettings
from invest_bot.db.engine import build_engine, build_session_factory
from invest_bot.db.frame_storage import DbFrameStorage
from invest_bot.db.repositories import SqlAlchemyStockRepository
from invest_bot.market.repositories import DatasetStorage
from invest_bot.market.stock_master import StockMasterRepository
from invest_bot.market.storage import SavedDataset
from invest_bot.strategy import MeanReversionStrategy, RSIStrategy, TrendFilterStrategy


SOURCE_DATE_COLUMN_ALIASES = ("date", "trade_date", "stck_bsop_date")
SOURCE_DATE_COLUMN = "__source_date"
SOURCE_DATE_HINT_COLUMN = "__source_date_hint"
INVESTOR_VALUE_COLUMNS = {"frgn_ntby_qty", "orgn_ntby_qty", "prsn_ntby_qty"}


class MarketReportDataError(ValueError):
    """Raised when a required report input cannot establish a usable as-of date."""


@dataclass(slots=True)
class MarketReportRequest:
    symbol: str
    indicator_filename: str
    signal_filename: str
    investor_filename: str
    stock_info_filename: str | None = None
    investor_summary_filename: str | None = None


class MarketReportGenerator:
    """Build a one-row market summary report from saved datasets."""

    def __init__(
        self,
        raw_storage: DatasetStorage | None = None,
        processed_storage: DatasetStorage | None = None,
        settings: AppSettings | None = None,
    ) -> None:
        self.raw_storage = raw_storage or DbFrameStorage.from_settings(settings)
        self.processed_storage = processed_storage or DbFrameStorage.from_settings(settings)

    def load_indicator_frame(self, request: MarketReportRequest) -> pd.DataFrame:
        return self._load_processed_csv("daily_prices_indicators", request.indicator_filename, parse_date=True)

    def load_signal_frame(self, request: MarketReportRequest) -> pd.DataFrame:
        return self._load_processed_csv("golden_cross_signals", request.signal_filename, parse_date=True)

    def load_investor_frame(self, request: MarketReportRequest) -> pd.DataFrame:
        frame = self._load_raw_csv("investor_daily", request.investor_filename)
        if not frame.empty and any(column in frame.columns for column in SOURCE_DATE_COLUMN_ALIASES):
            return frame
        if not request.investor_summary_filename:
            raise MarketReportDataError(
                "Investor detail has no observation date. A matching investor_daily_summary snapshot is required; "
                "refresh investor data before generating the report."
            )

        summary = self._load_raw_csv("investor_daily_summary", request.investor_summary_filename)
        if summary.empty:
            raise MarketReportDataError(
                "Investor detail has no observation date and its matching investor_daily_summary snapshot is missing; "
                "refresh investor data before generating the report."
            )
        try:
            normalized_summary, date_source = self._normalize_dated_source(summary, "investor_daily_summary")
        except MarketReportDataError as error:
            raise MarketReportDataError(
                "Investor detail has no observation date and its matching investor_daily_summary has no valid "
                "observation date; refresh investor data before generating the report."
            ) from error
        summary_date_source = f"summary:{date_source}"
        if INVESTOR_VALUE_COLUMNS.intersection(normalized_summary.columns):
            normalized_summary[SOURCE_DATE_HINT_COLUMN] = summary_date_source
            return normalized_summary
        if len(frame.index) != 1:
            raise MarketReportDataError(
                "Investor detail has no observation date and contains multiple rows, while its matching "
                "investor_daily_summary has dates only. The observations cannot be aligned safely; refresh investor "
                "data with dated values before generating the report."
            )
        frame["stck_bsop_date"] = normalized_summary[SOURCE_DATE_COLUMN].max()
        frame[SOURCE_DATE_HINT_COLUMN] = summary_date_source
        return frame

    def load_stock_info_frame(self, request: MarketReportRequest) -> pd.DataFrame:
        filename = request.stock_info_filename or f"{request.symbol}.csv"
        return self._load_raw_csv("stock_info", filename)

    def generate_report(
        self,
        request: MarketReportRequest,
        indicator_frame: pd.DataFrame,
        signal_frame: pd.DataFrame,
        investor_frame: pd.DataFrame,
        stock_info_frame: pd.DataFrame,
    ) -> pd.DataFrame:
        dated_sources = {
            "indicator": self._normalize_dated_source(indicator_frame, "indicator"),
            "signal": self._normalize_dated_source(signal_frame, "signal"),
            "investor": self._normalize_dated_source(investor_frame, "investor"),
        }
        reference_date = min(frame[SOURCE_DATE_COLUMN].max() for frame, _ in dated_sources.values())
        selected_sources: dict[str, tuple[pd.Series, str]] = {}
        for name, (frame, date_source) in dated_sources.items():
            eligible = frame.loc[frame[SOURCE_DATE_COLUMN] <= reference_date]
            if eligible.empty:
                raise MarketReportDataError(
                    f"Required market report source '{name}' has no row on or before reference date "
                    f"{reference_date:%Y-%m-%d}."
                )
            selected_sources[name] = (eligible.iloc[-1], date_source)
        normalized_indicator = dated_sources["indicator"][0]
        indicator_history = normalized_indicator.loc[normalized_indicator[SOURCE_DATE_COLUMN] <= reference_date]
        latest_indicator, indicator_date_source = selected_sources["indicator"]
        latest_signal, signal_date_source = selected_sources["signal"]
        latest_investor, investor_date_source = selected_sources["investor"]
        latest_stock_info = self._latest_row(stock_info_frame)
        market_snapshot = self._build_market_snapshot(indicator_history, latest_indicator)
        strategy_outcomes = self._evaluate_strategy_outcomes(market_snapshot)

        symbol_name = self._resolve_symbol_name(
            request.symbol,
            self._text_value(latest_stock_info.get("prdt_abrv_name")),
            self._text_value(latest_indicator.get("symbol_name")),
        )
        close = self._number_value(latest_indicator.get("close"))
        ma_5 = self._number_value(latest_indicator.get("ma_5"))
        ma_20 = self._number_value(latest_indicator.get("ma_20"))
        ma_60 = self._number_value(latest_indicator.get("ma_60"))
        rsi_14 = self._number_value(latest_indicator.get("rsi_14"))
        volume = self._number_value(latest_indicator.get("volume"))
        volume_ma_5 = self._number_value(latest_indicator.get("volume_ma_5"))

        foreign_net = self._number_value(latest_investor.get("frgn_ntby_qty"))
        institutional_net = self._number_value(latest_investor.get("orgn_ntby_qty"))
        personal_net = self._number_value(latest_investor.get("prsn_ntby_qty"))

        trend_state = self._classify_trend(close=close, ma_5=ma_5, ma_20=ma_20, ma_60=ma_60)
        rsi_state = self._classify_rsi(rsi_14)
        volume_state = self._classify_volume(volume=volume, volume_ma_5=volume_ma_5)
        investor_flow = self._classify_investor_flow(foreign_net, institutional_net, personal_net)

        golden_cross_signal = self._text_value(latest_signal.get("signal")) or "hold"
        golden_cross_reason = self._text_value(latest_signal.get("signal_reason"))

        final_opinion = self._classify_final_opinion(
            trend_state=trend_state,
            signal=golden_cross_signal,
            rsi_state=rsi_state,
            investor_flow=investor_flow,
        )
        summary = self._build_summary(
            trend_state=trend_state,
            signal=golden_cross_signal,
            rsi_state=rsi_state,
            volume_state=volume_state,
            investor_flow=investor_flow,
        )
        indicator_date = pd.Timestamp(latest_indicator[SOURCE_DATE_COLUMN])
        signal_date = pd.Timestamp(latest_signal[SOURCE_DATE_COLUMN])
        investor_date = pd.Timestamp(latest_investor[SOURCE_DATE_COLUMN])

        report = pd.DataFrame(
            [
                {
                    "symbol": request.symbol,
                    "symbol_name": symbol_name,
                    "date": self._text_value(reference_date),
                    "reference_date": self._text_value(reference_date),
                    "indicator_date": self._text_value(indicator_date),
                    "indicator_data_status": self._source_status(indicator_date, reference_date),
                    "indicator_date_source": indicator_date_source,
                    "signal_date": self._text_value(signal_date),
                    "signal_data_status": self._source_status(signal_date, reference_date),
                    "signal_date_source": signal_date_source,
                    "investor_date": self._text_value(investor_date),
                    "investor_data_status": self._source_status(investor_date, reference_date),
                    "investor_date_source": investor_date_source,
                    "close": close,
                    "ma_5": ma_5,
                    "ma_20": ma_20,
                    "ma_60": ma_60,
                    "rsi_14": rsi_14,
                    "volume": volume,
                    "volume_ma_5": volume_ma_5,
                    "golden_cross_signal": golden_cross_signal,
                    "golden_cross_reason": golden_cross_reason,
                    "rsi_strategy_signal": strategy_outcomes["rsi"]["signal"],
                    "rsi_strategy_reason": strategy_outcomes["rsi"]["reason"],
                    "trend_filter_signal": strategy_outcomes["trend_filter"]["signal"],
                    "trend_filter_reason": strategy_outcomes["trend_filter"]["reason"],
                    "mean_reversion_signal": strategy_outcomes["mean_reversion"]["signal"],
                    "mean_reversion_reason": strategy_outcomes["mean_reversion"]["reason"],
                    "trend_state": trend_state,
                    "rsi_state": rsi_state,
                    "volume_state": volume_state,
                    "investor_flow": investor_flow,
                    "foreign_net": foreign_net,
                    "institutional_net": institutional_net,
                    "personal_net": personal_net,
                    "summary": summary,
                    "final_opinion": final_opinion,
                }
            ]
        )
        return report

    def save_report(self, filename: str, frame: pd.DataFrame) -> SavedDataset:
        return self.processed_storage.save("market_reports", filename, frame)

    def _resolve_symbol_name(self, symbol: str, *candidates: str) -> str:
        canonical_name = self._load_symbol_name_from_db(symbol) or self._load_symbol_name_from_master(symbol)
        if self._is_meaningful_symbol_name(symbol, canonical_name):
            return canonical_name
        for candidate in candidates:
            if self._is_meaningful_symbol_name(symbol, candidate):
                return candidate.strip()
        return ""

    def _load_symbol_name_from_db(self, symbol: str) -> str:
        database_url = getattr(self.raw_storage, "database_url", "").strip()
        if not database_url:
            return ""
        try:
            engine = build_engine(database_url)
            try:
                repository = SqlAlchemyStockRepository(build_session_factory(engine))
                record = repository.get_by_symbol(symbol)
                return record.symbol_name.strip() if record is not None else ""
            finally:
                engine.dispose()
        except Exception:
            return ""

    @staticmethod
    def _load_symbol_name_from_master(symbol: str) -> str:
        try:
            repository = StockMasterRepository()
            normalized = MarketReportGenerator._normalize_symbol(symbol)
            for entry in repository.load_entries():
                if MarketReportGenerator._normalize_symbol(entry.get("symbol", "")) == normalized:
                    return str(entry.get("symbol_name", "")).strip()
        except Exception:
            return ""
        return ""

    def _load_processed_csv(self, dataset: str, filename: str, parse_date: bool = False) -> pd.DataFrame:
        try:
            frame = self.processed_storage.load(dataset, filename)
        except (EmptyDataError, FileNotFoundError):
            return pd.DataFrame()
        if parse_date and "date" in frame.columns:
            frame["date"] = self._parse_date_series(frame["date"])
            frame = frame.sort_values("date").reset_index(drop=True)
        return frame

    def _load_raw_csv(self, dataset: str, filename: str) -> pd.DataFrame:
        try:
            return self.raw_storage.load(dataset, filename)
        except (EmptyDataError, FileNotFoundError):
            return pd.DataFrame()

    @classmethod
    def _normalize_dated_source(
        cls,
        frame: pd.DataFrame,
        source_name: str,
    ) -> tuple[pd.DataFrame, str]:
        if frame.empty:
            raise MarketReportDataError(f"Required market report source '{source_name}' is empty.")

        normalized = frame.copy()
        for column in SOURCE_DATE_COLUMN_ALIASES:
            if column not in normalized.columns:
                continue
            parsed = cls._parse_date_series(normalized[column])
            normalized[SOURCE_DATE_COLUMN] = parsed
            normalized = normalized.dropna(subset=[SOURCE_DATE_COLUMN])
            if normalized.empty:
                raise MarketReportDataError(
                    f"Required market report source '{source_name}' has no valid values in date column '{column}'."
                )
            date_source = f"column:{column}"
            if SOURCE_DATE_HINT_COLUMN in normalized.columns:
                hints = normalized[SOURCE_DATE_HINT_COLUMN].dropna()
                if not hints.empty:
                    date_source = str(hints.iloc[-1])
            return normalized.sort_values(SOURCE_DATE_COLUMN, kind="stable").reset_index(drop=True), date_source

        suffix = (
            " A matching investor_daily_summary snapshot is required; refresh investor data."
            if source_name == "investor"
            else ""
        )
        raise MarketReportDataError(f"Required market report source '{source_name}' has no usable date.{suffix}")

    @staticmethod
    def _parse_date_series(series: pd.Series) -> pd.Series:
        text = series.astype("string").str.strip()
        compact_date = text.str.fullmatch(r"\d{8}(?:\.0+)?", na=False)
        parsed = pd.Series(pd.NaT, index=series.index, dtype="datetime64[ns]")
        parsed.loc[compact_date] = pd.to_datetime(
            text.loc[compact_date].str.split(".").str[0],
            format="%Y%m%d",
            errors="coerce",
        )
        parsed.loc[~compact_date] = pd.to_datetime(series.loc[~compact_date], errors="coerce")
        return parsed

    @staticmethod
    def _source_status(source_date: pd.Timestamp, reference_date: pd.Timestamp) -> str:
        return "aligned" if source_date == reference_date else "lagging"

    @staticmethod
    def _build_market_snapshot(indicator_frame: pd.DataFrame, latest_indicator: pd.Series) -> dict[str, object]:
        snapshot = latest_indicator.to_dict() if not latest_indicator.empty else {}
        if len(indicator_frame.index) >= 2:
            snapshot["prev_close"] = indicator_frame.iloc[-2].get("close")
        return snapshot

    @staticmethod
    def _evaluate_strategy_outcomes(market_snapshot: dict[str, object]) -> dict[str, dict[str, str]]:
        strategies = {
            "rsi": RSIStrategy(),
            "trend_filter": TrendFilterStrategy(),
            "mean_reversion": MeanReversionStrategy(),
        }
        outcomes: dict[str, dict[str, str]] = {}
        for key, strategy in strategies.items():
            result = strategy.evaluate(market_snapshot)
            outcomes[key] = {
                "signal": result.signal.value,
                "reason": result.reason,
            }
        return outcomes

    @staticmethod
    def _latest_row(frame: pd.DataFrame) -> pd.Series:
        if frame.empty:
            return pd.Series(dtype=object)
        return frame.iloc[-1]

    @staticmethod
    def _number_value(value: object) -> float | None:
        if value is None or pd.isna(value):
            return None
        return float(value)

    @staticmethod
    def _text_value(value: object) -> str:
        if value is None or pd.isna(value):
            return ""
        if isinstance(value, pd.Timestamp):
            return value.strftime("%Y-%m-%d")
        return str(value)

    @staticmethod
    def _normalize_symbol(value: object) -> str:
        text = str(value).strip()
        if text.isdigit():
            return text.zfill(6)
        return text

    @classmethod
    def _is_meaningful_symbol_name(cls, symbol: str, name: str) -> bool:
        cleaned = str(name).strip()
        return bool(cleaned) and cls._normalize_symbol(cleaned) != cls._normalize_symbol(symbol)

    @staticmethod
    def _classify_trend(close: float | None, ma_5: float | None, ma_20: float | None, ma_60: float | None) -> str:
        if None in {close, ma_5, ma_20, ma_60}:
            return "unknown"
        if close > ma_20 and ma_5 > ma_20 and close > ma_60:
            return "bullish"
        if close < ma_20 and ma_5 < ma_20 and close < ma_60:
            return "bearish"
        return "neutral"

    @staticmethod
    def _classify_rsi(rsi_14: float | None) -> str:
        if rsi_14 is None:
            return "unknown"
        if rsi_14 >= 70:
            return "overbought"
        if rsi_14 <= 30:
            return "oversold"
        if rsi_14 >= 55:
            return "strong"
        if rsi_14 <= 45:
            return "weak"
        return "neutral"

    @staticmethod
    def _classify_volume(volume: float | None, volume_ma_5: float | None) -> str:
        if volume is None or volume_ma_5 in {None, 0}:
            return "unknown"
        ratio = volume / volume_ma_5
        if ratio >= 1.2:
            return "active"
        if ratio <= 0.8:
            return "quiet"
        return "normal"

    @staticmethod
    def _classify_investor_flow(
        foreign_net: float | None,
        institutional_net: float | None,
        personal_net: float | None,
    ) -> str:
        if foreign_net is None or institutional_net is None or personal_net is None:
            return "unknown"
        if foreign_net > 0 and institutional_net > 0:
            return "supportive"
        if foreign_net < 0 and institutional_net < 0:
            return "weak"
        return "mixed"

    @staticmethod
    def _classify_final_opinion(
        trend_state: str,
        signal: str,
        rsi_state: str,
        investor_flow: str,
    ) -> str:
        if signal == "buy" and trend_state == "bullish" and rsi_state not in {"overbought", "unknown"}:
            return "buy"
        if signal == "sell" or trend_state == "bearish":
            return "sell"
        if investor_flow == "supportive" and signal == "hold" and trend_state != "bearish":
            return "watch"
        return "hold"

    @staticmethod
    def _build_summary(
        trend_state: str,
        signal: str,
        rsi_state: str,
        volume_state: str,
        investor_flow: str,
    ) -> str:
        return (
            f"Trend is {trend_state}, golden cross signal is {signal}, RSI state is {rsi_state}, "
            f"volume is {volume_state}, and investor flow is {investor_flow}."
        )
