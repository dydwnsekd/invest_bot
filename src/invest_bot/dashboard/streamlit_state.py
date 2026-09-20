from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pandas as pd

from invest_bot.dashboard.service import DashboardDataService, DatasetPreview
from invest_bot.jobs.scheduled_collection import load_schedule_status


DAILY_PRICE_COLUMN_MAP = {
    "stck_bsop_date": "date",
    "stck_oprc": "open",
    "stck_hgpr": "high",
    "stck_lwpr": "low",
    "stck_clpr": "close",
    "acml_vol": "volume",
    "acml_tr_pbmn": "turnover",
}


class DashboardFrameLoader:
    """Reuse immutable frame reads during one Streamlit render request."""

    def __init__(self, service: DashboardDataService) -> None:
        self._service = service
        self._frames: dict[tuple[str, str], pd.DataFrame | None] = {}

    def load_indicator(self, symbol: str) -> pd.DataFrame | None:
        return self._load_latest(
            "daily_prices_indicators",
            symbol,
            root=self._service.processed_root,
        )

    def load_professional(self, symbol: str) -> pd.DataFrame | None:
        base_frame = _load_professional_chart_base_frame(
            self._service,
            symbol,
            load_indicator_frame=self.load_indicator,
            load_daily_prices_frame=lambda: self._load_latest(
                "daily_prices",
                symbol,
                root=self._service.raw_root,
            ),
        )
        if base_frame is None:
            return None

        investor_frame = self._load_latest("investor_daily", symbol, root=self._service.raw_root)
        return _merge_investor_flow(base_frame, investor_frame)

    def _load_latest(self, dataset: str, symbol: str, *, root: Path) -> pd.DataFrame | None:
        key = (dataset, symbol)
        if key not in self._frames:
            self._frames[key] = _load_latest_dataset_frame(self._service, dataset, symbol, root=root)
        frame = self._frames[key]
        return None if frame is None else frame.copy()


def load_optional_schedule_status():
    try:
        return load_schedule_status()
    except (FileNotFoundError, ValueError):
        return None


def read_preview_frame(service: DashboardDataService, source: DatasetPreview | Path) -> pd.DataFrame:
    if isinstance(source, DatasetPreview):
        return service.load_preview_frame(source)
    try:
        return pd.read_csv(source)
    except pd.errors.EmptyDataError:
        return pd.DataFrame()


def load_indicator_frame_for_symbol(service: DashboardDataService, symbol: str) -> pd.DataFrame | None:
    return DashboardFrameLoader(service).load_indicator(symbol)


def load_professional_chart_frame_for_symbol(service: DashboardDataService, symbol: str) -> pd.DataFrame | None:
    return DashboardFrameLoader(service).load_professional(symbol)


def _merge_investor_flow(
    base_frame: pd.DataFrame,
    investor_frame: pd.DataFrame | None,
) -> pd.DataFrame:
    if investor_frame is None:
        return base_frame

    normalized_investor = _normalize_date_column(investor_frame)
    if normalized_investor is None:
        return base_frame

    flow_columns = [
        column
        for column in (
            "foreign_net",
            "institutional_net",
            "personal_net",
            "frgn_ntby_qty",
            "orgn_ntby_qty",
            "prsn_ntby_qty",
        )
        if column in normalized_investor.columns
    ]
    flow_columns = [column for column in flow_columns if _has_usable_flow_values(normalized_investor[column])]
    if not flow_columns:
        return base_frame

    investor_subset = normalized_investor[["date", *flow_columns]].copy()
    investor_subset = investor_subset.dropna(subset=["date"])
    investor_subset = investor_subset.drop_duplicates(subset=["date"], keep="last")
    return base_frame.merge(investor_subset, on="date", how="left")


def _has_usable_flow_values(series: pd.Series) -> bool:
    normalized = pd.to_numeric(series, errors="coerce")
    return normalized.notna().any()


def _load_professional_chart_base_frame(
    service: DashboardDataService,
    symbol: str,
    *,
    load_indicator_frame: Callable[[str], pd.DataFrame | None] | None = None,
    load_daily_prices_frame: Callable[[], pd.DataFrame | None] | None = None,
) -> pd.DataFrame | None:
    indicator_frame = (
        load_indicator_frame(symbol)
        if load_indicator_frame is not None
        else _load_latest_dataset_frame(
            service,
            "daily_prices_indicators",
            symbol,
            root=service.processed_root,
        )
    )
    load_daily_prices = load_daily_prices_frame or (
        lambda: _load_latest_dataset_frame(service, "daily_prices", symbol, root=service.raw_root)
    )
    if _has_ohlc_columns(indicator_frame):
        normalized_indicator = _normalize_date_column(indicator_frame)
        if normalized_indicator is not None:
            if _has_non_null_volume(normalized_indicator):
                return normalized_indicator

            normalized_daily_prices = _normalize_daily_prices_frame(load_daily_prices())
            if normalized_daily_prices is None or "volume" not in normalized_daily_prices.columns:
                return normalized_indicator

            volume_subset = (
                normalized_daily_prices[["date", "volume"]]
                .dropna(subset=["date"])
                .drop_duplicates(subset=["date"], keep="last")
            )
            if volume_subset.empty:
                return normalized_indicator

            merged = normalized_indicator.merge(volume_subset, on="date", how="left", suffixes=("", "_daily_prices"))
            if "volume" not in merged.columns and "volume_daily_prices" in merged.columns:
                merged["volume"] = merged["volume_daily_prices"]
            elif "volume_daily_prices" in merged.columns:
                merged["volume"] = merged["volume"].where(merged["volume"].notna(), merged["volume_daily_prices"])
            return merged.drop(columns=["volume_daily_prices"], errors="ignore")

    normalized_daily_prices = _normalize_daily_prices_frame(load_daily_prices())
    if not _has_ohlc_columns(normalized_daily_prices):
        return None

    return _normalize_date_column(normalized_daily_prices)


def _has_ohlc_columns(frame: pd.DataFrame | None) -> bool:
    return frame is not None and {"open", "high", "low", "close"}.issubset(frame.columns)


def _has_non_null_volume(frame: pd.DataFrame | None) -> bool:
    return frame is not None and "volume" in frame.columns and frame["volume"].notna().any()


def _load_latest_dataset_frame(
    service: DashboardDataService,
    dataset: str,
    symbol: str,
    *,
    root: Path,
) -> pd.DataFrame | None:
    storage = service.get_dataset_storage()
    filename = None
    if storage is not None:
        filename = storage.latest_filename(dataset, symbol)
    else:
        dataset_dir = root / dataset
        if not dataset_dir.exists():
            return None
        matches = sorted(dataset_dir.glob(f"{symbol}_*.csv"), key=lambda item: item.stat().st_mtime, reverse=True)
        if matches:
            filename = matches[0].name
    if filename is None:
        return None
    try:
        return storage.load(dataset, filename) if storage is not None else pd.read_csv(root / dataset / filename)
    except (pd.errors.EmptyDataError, FileNotFoundError):
        return None


def _normalize_daily_prices_frame(daily_prices_frame: pd.DataFrame | None) -> pd.DataFrame | None:
    if daily_prices_frame is None:
        return None

    normalized = daily_prices_frame.copy().rename(columns=DAILY_PRICE_COLUMN_MAP)
    if "date" in normalized.columns:
        normalized["date"] = pd.to_datetime(normalized["date"], format="%Y%m%d", errors="coerce")
        if normalized["date"].isna().all():
            normalized["date"] = pd.to_datetime(normalized["date"], errors="coerce")

    for column in ("open", "high", "low", "close", "volume", "turnover"):
        if column in normalized.columns:
            normalized[column] = pd.to_numeric(normalized[column], errors="coerce")

    if "date" in normalized.columns:
        normalized = normalized.sort_values("date").reset_index(drop=True)
    return normalized


def _normalize_date_column(frame: pd.DataFrame) -> pd.DataFrame | None:
    if frame.empty:
        result = frame.copy()
        result["date"] = pd.to_datetime(pd.Series(dtype="object"))
        return result

    if "date" in frame.columns:
        date_source = frame["date"]
    elif "stck_bsop_date" in frame.columns:
        date_source = frame["stck_bsop_date"]
    else:
        return None

    result = frame.copy()
    result["date"] = pd.to_datetime(date_source, format="%Y%m%d", errors="coerce")
    if result["date"].isna().all():
        result["date"] = pd.to_datetime(date_source, errors="coerce")
    if result["date"].isna().all():
        return None
    return result
