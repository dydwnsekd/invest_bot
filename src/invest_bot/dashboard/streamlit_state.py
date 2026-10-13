from __future__ import annotations

import re
from collections.abc import Callable, Sequence
from copy import deepcopy
from io import StringIO
from pathlib import Path

import pandas as pd

from invest_bot.dashboard.service import DashboardDataService, DatasetPreview
from invest_bot.db.contracts import DatasetFrameRecord
from invest_bot.db.frame_storage import DbFrameStorage
from invest_bot.db.repositories import frame_from_json, normalize_symbol
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

    def __init__(
        self,
        service: DashboardDataService,
        latest_records: Sequence[DatasetFrameRecord] | None = None,
    ) -> None:
        self._service = service
        self._frames: dict[tuple[str, str], pd.DataFrame | None] = {}
        self._latest_by_symbol = (
            {(record.dataset, record.symbol): record for record in latest_records}
            if latest_records is not None else None
        )
        self._latest_by_filename = (
            {(record.dataset, record.filename): record for record in latest_records}
            if latest_records is not None else None
        )

    def read_preview(self, source: DatasetPreview | Path) -> pd.DataFrame:
        if isinstance(source, DatasetPreview) and self._latest_by_filename is not None:
            record = self._latest_by_filename.get((source.name, source.path.name))
            if record is not None and record.frame_json:
                return frame_from_json(record.frame_json)
        return read_preview_frame(self._service, source)

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

        investor_frame, detail_issue = _prepare_investor_flow(
            self._load_latest("investor_daily", symbol, root=self._service.raw_root)
        )
        source: str | None = "detail"
        if investor_frame is None:
            investor_frame, summary_issue = _prepare_investor_flow(
                self._load_latest("investor_daily_summary", symbol, root=self._service.raw_root)
            )
            source = "summary" if investor_frame is not None else None

        merged = _merge_investor_flow(base_frame, investor_frame)
        merged.attrs["investor_flow_source"] = source
        if source is None:
            message = f"수급 데이터 없음: 상세 수급은 {detail_issue} 요약 수급은 {summary_issue}"
        elif not any(merged[column].notna().any() for column in investor_frame.columns if column != "date"):
            message = "수급 데이터 없음: 수급 관측일과 가격 날짜가 일치하지 않습니다."
        else:
            source_label = "상세" if source == "detail" else "요약"
            message = f"수급: {source_label}의 실제 관측일별 값을 표시합니다. 일치하지 않는 날과 누락된 값은 미관측입니다."
            if source == "summary":
                message += f" 상세 수급은 {detail_issue}"
        merged.attrs["investor_flow_message"] = message
        return merged

    def _load_latest(self, dataset: str, symbol: str, *, root: Path) -> pd.DataFrame | None:
        key = (dataset, normalize_symbol(symbol))
        if key not in self._frames:
            if self._latest_by_symbol is None:
                self._frames[key] = _load_latest_dataset_frame(self._service, dataset, symbol, root=root)
            else:
                record = self._latest_by_symbol.get(key)
                if record is None:
                    self._frames[key] = None
                elif record.frame_json.strip():
                    self._frames[key] = (
                        _read_investor_frame(record.frame_json)
                        if dataset in {"investor_daily", "investor_daily_summary"}
                        else frame_from_json(record.frame_json)
                    )
                else:
                    # An explicit snapshot is authoritative, including an empty payload.
                    self._frames[key] = None
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
    # Only the selected investor dataset establishes flow provenance. Remove
    # any stale aliases carried by a price/indicator frame before attaching it.
    merged = base_frame.drop(columns=[
        "foreign_net", "institutional_net", "personal_net",
        "frgn_ntby_qty", "orgn_ntby_qty", "prsn_ntby_qty",
    ], errors="ignore").copy()
    merged.attrs = deepcopy(base_frame.attrs)
    if investor_frame is None:
        return merged

    # Compare civil observation days without changing the price timestamps.
    # Multiple price rows on one day cannot identify a single daily candle;
    # leave that day's flow unobserved rather than repeating a daily total.
    days = base_frame["date"].map(_parse_investor_observation_date)
    days = days.mask(days.duplicated(keep=False))
    aligned = investor_frame.set_index("date").reindex(pd.DatetimeIndex(days))
    for column in aligned.columns:
        merged[column] = aligned[column].to_numpy()
    return merged


def _prepare_investor_flow(frame: pd.DataFrame | None) -> tuple[pd.DataFrame | None, str]:
    """Keep dated, finite observations from one source; never infer dates from prices."""
    if frame is None or frame.empty:
        return None, "저장된 관측값이 없습니다."

    dates = pd.Series(pd.NaT, index=frame.index, dtype="datetime64[ns]")
    for column in ("date", "trade_date", "stck_bsop_date"):
        if column in frame.columns:
            dates = dates.fillna(frame[column].map(_parse_investor_observation_date))
    if dates.isna().all():
        return None, "유효한 관측일이 없습니다."

    observations = pd.DataFrame({"date": dates})
    for canonical, raw in (
        ("foreign_net", "frgn_ntby_qty"),
        ("institutional_net", "orgn_ntby_qty"),
        ("personal_net", "prsn_ntby_qty"),
    ):
        aliases = [column for column in (canonical, raw) if column in frame.columns]
        if not aliases:
            continue
        values = None
        for column in aliases:
            numeric = pd.to_numeric(frame[column], errors="coerce").replace([float("inf"), -float("inf")], float("nan"))
            values = numeric if values is None else values.fillna(numeric)
        observations[aliases[0]] = values

    flow_columns = [column for column in observations.columns if column != "date"]
    observations = observations.loc[dates.notna() & observations[flow_columns].notna().any(axis=1)]
    observations = observations.drop_duplicates(subset=["date"], keep="last")
    flow_columns = [column for column in flow_columns if observations[column].notna().any()]
    if observations.empty or not flow_columns:
        return None, "관측일에 연결할 유효한 순매수 값이 없습니다."
    return observations[["date", *flow_columns]], ""


def _read_investor_frame(payload: str) -> pd.DataFrame:
    # Keep numeric YYYYMMDD observation aliases intact until chart-local parsing.
    # Do not change the shared DB decoder or its other consumers (G01b).
    return pd.read_json(StringIO(payload), orient="table", convert_dates=False)


def _parse_investor_observation_date(value: object) -> pd.Timestamp:
    # Strings prevent numeric YYYYMMDD from being interpreted as epoch nanoseconds.
    text = str(value).strip()
    if len(text) == 10 and text.endswith(".0") and text[:8].isdigit():
        text = text[:8]
    if not (re.fullmatch(r"\d{8}", text) or re.match(r"\d{4}[-/]\d{1,2}[-/]\d{1,2}(?:$|[ T])", text)):
        return pd.NaT
    parsed = pd.to_datetime(text, format="mixed", errors="coerce")
    if pd.isna(parsed):
        return pd.NaT
    # Observation days are civil dates: discard time/zone without shifting the day.
    return parsed.tz_localize(None).normalize()


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
        if dataset in {"investor_daily", "investor_daily_summary"} and isinstance(storage, DbFrameStorage):
            record = storage.repository.latest_for_symbol(dataset, symbol)
            return _read_investor_frame(record.frame_json) if record is not None and record.frame_json.strip() else None
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
