from __future__ import annotations

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
    return _load_latest_dataset_frame(
        service,
        "daily_prices_indicators",
        symbol,
        root=service.processed_root,
    )


def load_professional_chart_frame_for_symbol(service: DashboardDataService, symbol: str) -> pd.DataFrame | None:
    base_frame = _load_professional_chart_base_frame(service, symbol)
    if base_frame is None:
        return None

    investor_frame = _load_latest_dataset_frame(service, "investor_daily", symbol, root=service.raw_root)
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


def _load_professional_chart_base_frame(service: DashboardDataService, symbol: str) -> pd.DataFrame | None:
    indicator_frame = load_indicator_frame_for_symbol(service, symbol)
    if _has_ohlc_columns(indicator_frame):
        normalized_indicator = _normalize_date_column(indicator_frame)
        if normalized_indicator is not None:
            if _has_non_null_volume(normalized_indicator):
                return normalized_indicator

            normalized_daily_prices = _load_normalized_daily_prices_frame(service, symbol)
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

    normalized_daily_prices = _load_normalized_daily_prices_frame(service, symbol)
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


def _load_normalized_daily_prices_frame(service: DashboardDataService, symbol: str) -> pd.DataFrame | None:
    daily_prices_frame = _load_latest_dataset_frame(service, "daily_prices", symbol, root=service.raw_root)
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
