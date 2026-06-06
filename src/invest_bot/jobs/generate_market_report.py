from __future__ import annotations

from dataclasses import dataclass

import pandas as pd
from pandas.errors import EmptyDataError

from invest_bot.market.repositories import DatasetStorage
from invest_bot.market.storage import CsvStorage, SavedDataset


@dataclass(slots=True)
class MarketReportRequest:
    symbol: str
    indicator_filename: str
    signal_filename: str
    investor_filename: str
    stock_info_filename: str | None = None


class MarketReportGenerator:
    """Build a one-row market summary report from saved datasets."""

    def __init__(
        self,
        raw_storage: DatasetStorage | None = None,
        processed_storage: DatasetStorage | None = None,
    ) -> None:
        self.raw_storage = raw_storage or CsvStorage("data/raw/domestic_stock")
        self.processed_storage = processed_storage or CsvStorage("data/processed/domestic_stock")

    def load_indicator_frame(self, request: MarketReportRequest) -> pd.DataFrame:
        return self._load_processed_csv("daily_prices_indicators", request.indicator_filename, parse_date=True)

    def load_signal_frame(self, request: MarketReportRequest) -> pd.DataFrame:
        return self._load_processed_csv("golden_cross_signals", request.signal_filename, parse_date=True)

    def load_investor_frame(self, request: MarketReportRequest) -> pd.DataFrame:
        return self._load_raw_csv("investor_daily", request.investor_filename)

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
        latest_indicator = self._latest_row(indicator_frame)
        latest_signal = self._latest_row(signal_frame)
        latest_investor = self._latest_row(investor_frame)
        latest_stock_info = self._latest_row(stock_info_frame)

        symbol_name = self._text_value(latest_stock_info.get("prdt_abrv_name")) or self._text_value(
            latest_indicator.get("symbol_name")
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

        report = pd.DataFrame(
            [
                {
                    "symbol": request.symbol,
                    "symbol_name": symbol_name,
                    "date": self._text_value(latest_signal.get("date")) or self._text_value(latest_indicator.get("date")),
                    "close": close,
                    "ma_5": ma_5,
                    "ma_20": ma_20,
                    "ma_60": ma_60,
                    "rsi_14": rsi_14,
                    "volume": volume,
                    "volume_ma_5": volume_ma_5,
                    "golden_cross_signal": golden_cross_signal,
                    "golden_cross_reason": golden_cross_reason,
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

    def _load_processed_csv(self, dataset: str, filename: str, parse_date: bool = False) -> pd.DataFrame:
        try:
            frame = pd.read_csv(self.processed_storage.root_dir / dataset / filename)
        except EmptyDataError:
            return pd.DataFrame()
        if parse_date and "date" in frame.columns:
            frame["date"] = pd.to_datetime(frame["date"], errors="coerce")
            frame = frame.sort_values("date").reset_index(drop=True)
        return frame

    def _load_raw_csv(self, dataset: str, filename: str) -> pd.DataFrame:
        try:
            return pd.read_csv(self.raw_storage.root_dir / dataset / filename)
        except EmptyDataError:
            return pd.DataFrame()

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
