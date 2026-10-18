"""Shared saved-data dates and next-action guidance for dashboard read views."""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path

import pandas as pd

from invest_bot.dashboard.service import DashboardDataService
from invest_bot.db.contracts import DatasetFrameRecord
from invest_bot.db.repositories import frame_from_json, frame_to_json, normalize_symbol


@dataclass(frozen=True, slots=True)
class WatchlistDataStatus:
    symbol: str
    label: str
    detail: str
    daily_date: date | None
    investor_date: date | None
    indicator_date: date | None
    signal_date: date | None
    report_date: date | None
    collection_created_at: datetime | None = None
    analysis_created_at: datetime | None = None

    @property
    def needs_update(self) -> bool:
        return self.label != "최신"


@dataclass(frozen=True, slots=True)
class WatchlistProcessingTimes:
    collection_created_at: datetime | None = None
    analysis_created_at: datetime | None = None


def build_watchlist_data_statuses(
    service: DashboardDataService,
    favorite_symbols: set[str],
    *,
    today: date | None = None,
    processing_times: Mapping[str, WatchlistProcessingTimes] | None = None,
    latest_records: Sequence[DatasetFrameRecord] | None = None,
) -> list[WatchlistDataStatus]:
    target_date = _latest_expected_market_date(today or date.today())
    snapshot_records = (
        {(record.dataset, record.symbol): record for record in latest_records}
        if latest_records is not None else None
    )
    return [
        build_watchlist_data_status(
            service,
            symbol,
            target_date=target_date,
            processing_times=(processing_times or {}).get(symbol),
            snapshot_records=snapshot_records,
        )
        for symbol in sorted(favorite_symbols)
    ]


def build_watchlist_data_status(
    service: DashboardDataService,
    symbol: str,
    *,
    target_date: date,
    processing_times: WatchlistProcessingTimes | None = None,
    snapshot_records: Mapping[tuple[str, str], DatasetFrameRecord] | None = None,
    report_frame: pd.DataFrame | None = None,
) -> WatchlistDataStatus:
    processing_times = processing_times or WatchlistProcessingTimes()
    daily_date = _load_latest_dataset_date(
        service, "daily_prices", symbol, ("trade_date", "stck_bsop_date", "date"), snapshot_records=snapshot_records,
    )
    investor_date = _load_latest_dataset_date(
        service,
        "investor_daily_summary",
        symbol,
        ("trade_date", "stck_bsop_date", "date"),
        snapshot_records=snapshot_records,
    )
    indicator_date = _load_latest_dataset_date(
        service, "daily_prices_indicators", symbol, ("date", "trade_date", "stck_bsop_date"), snapshot_records=snapshot_records,
    )
    signal_date = _load_latest_dataset_date(
        service, "golden_cross_signals", symbol, ("date", "trade_date", "stck_bsop_date"), snapshot_records=snapshot_records,
    )
    report_date = (
        _load_latest_dataset_date(service, "market_reports", symbol, ("date",), snapshot_records=snapshot_records)
        if report_frame is None else latest_frame_date(report_frame, ("date",))
    )

    return classify_data_dates(
        symbol, target_date=target_date, daily_date=daily_date, investor_date=investor_date,
        indicator_date=indicator_date, signal_date=signal_date, report_date=report_date,
        processing_times=processing_times,
    )


def build_watchlist_processing_times(snapshot, favorite_symbols: set[str]) -> dict[str, WatchlistProcessingTimes]:
    collection_datasets = {"daily_prices", "investor_daily", "investor_daily_summary"}
    analysis_datasets = {"daily_prices_indicators", "golden_cross_signals", "market_reports"}
    collection_times: dict[str, datetime] = {}
    analysis_times: dict[str, datetime] = {}

    for preview in getattr(snapshot, "raw_previews", []):
        if preview.symbol not in favorite_symbols or preview.name not in collection_datasets or preview.created_at is None:
            continue
        collection_times[preview.symbol] = max(collection_times.get(preview.symbol, preview.created_at), preview.created_at)
    for preview in getattr(snapshot, "processed_previews", []):
        if preview.symbol not in favorite_symbols or preview.name not in analysis_datasets or preview.created_at is None:
            continue
        analysis_times[preview.symbol] = max(analysis_times.get(preview.symbol, preview.created_at), preview.created_at)

    return {
        symbol: WatchlistProcessingTimes(
            collection_created_at=collection_times.get(symbol),
            analysis_created_at=analysis_times.get(symbol),
        )
        for symbol in favorite_symbols
    }


def _latest_expected_market_date(today: date) -> date:
    if today.weekday() < 5:
        return today
    return today - timedelta(days=today.weekday() - 4)


def _load_latest_dataset_date(
    service: DashboardDataService,
    dataset: str,
    symbol: str,
    date_columns: Sequence[str],
    *,
    snapshot_records: Mapping[tuple[str, str], DatasetFrameRecord] | None = None,
) -> date | None:
    if snapshot_records is None:
        frame = _load_latest_dataset_frame(service, dataset, symbol)
    else:
        record = snapshot_records.get((dataset, normalize_symbol(symbol)))
        frame = frame_from_json(record.frame_json) if record is not None else None
    return latest_frame_date(frame, date_columns)


def latest_frame_date(frame: pd.DataFrame | None, date_columns: Sequence[str]) -> date | None:
    if frame is None or frame.empty:
        return None

    for column in date_columns:
        if column not in frame.columns:
            continue
        parsed = pd.to_datetime(frame[column], errors="coerce")
        parsed = parsed.dropna()
        if parsed.empty:
            continue
        return parsed.max().date()
    return None


def _load_latest_dataset_frame(service: DashboardDataService, dataset: str, symbol: str) -> pd.DataFrame | None:
    storage = service.get_dataset_storage()
    if storage is not None:
        filename = storage.latest_filename(dataset, symbol)
        if filename is None:
            return None
        try:
            return storage.load(dataset, filename)
        except FileNotFoundError:
            return None

    dataset_root = _dataset_root(service, dataset)
    if not dataset_root.exists():
        return None
    matches = sorted(dataset_root.glob(f"{symbol}_*.csv"), key=lambda item: item.stat().st_mtime, reverse=True)
    if not matches:
        return None
    try:
        return pd.read_csv(matches[0])
    except (FileNotFoundError, pd.errors.EmptyDataError):
        return pd.DataFrame()


def _dataset_root(service: DashboardDataService, dataset: str) -> Path:
    if dataset in service.RAW_DATASETS:
        return service.raw_root / dataset
    return service.processed_root / dataset


def classify_data_dates(
    symbol: str, *, target_date: date, daily_date: date | None, investor_date: date | None,
    indicator_date: date | None, signal_date: date | None, report_date: date | None,
    processing_times: WatchlistProcessingTimes | None = None,
) -> WatchlistDataStatus:
    processing_times = processing_times or WatchlistProcessingTimes()
    dates = dict(
        daily_date=daily_date, investor_date=investor_date, indicator_date=indicator_date,
        signal_date=signal_date, report_date=report_date,
        collection_created_at=processing_times.collection_created_at,
        analysis_created_at=processing_times.analysis_created_at,
    )
    sources = (("가격", daily_date), ("수급", investor_date))
    missing = [label for label, value in sources if value is None]
    stale = [label for label, value in sources if value is not None and value < target_date]
    ahead = [label for label, value in sources if value is not None and value > target_date]
    if missing:
        label = "데이터 갱신 필요"
        detail = f"{', '.join(missing)} 원본 데이터가 없습니다. 해당 원본의 수집 결과를 확인하세요."
    elif ahead:
        label = "기준일 불일치"
        detail = f"{', '.join(ahead)} 원본이 확인 기준일({target_date.isoformat()})보다 앞섭니다. 저장된 관측일을 확인하세요."
    elif stale:
        label = "데이터 갱신 필요"
        detail = f"{', '.join(stale)} 데이터가 최신 영업일({target_date.isoformat()}) 기준으로 준비되지 않았습니다. 해당 원본의 수집 결과를 확인하세요."
    else:
        reference = max(daily_date, investor_date)
        outputs = (("분석", indicator_date, daily_date), ("신호", signal_date, daily_date), ("리포트", report_date, reference))
        ahead_outputs = [name for name, value, source_date in outputs if value is not None and value > source_date]
        outdated = [name for name, value, source_date in outputs if value is None or value < source_date]
        if ahead_outputs:
            label = "기준일 불일치"
            detail = f"{', '.join(ahead_outputs)} 기준일이 원본보다 앞섭니다. 원본과 판단의 저장 기준일을 대조하세요."
        elif outdated:
            label = "분석 갱신 필요"
            detail = f"가격·수급 데이터는 최신입니다. {', '.join(outdated)} 결과를 다시 생성하세요."
        else:
            label = "최신"
            detail = f"가격·수급·분석·신호·리포트가 최신 영업일({target_date.isoformat()}) 기준으로 준비되었습니다."
    return WatchlistDataStatus(symbol=symbol, label=label, detail=detail, **dates)


def build_snapshot_data_statuses(service, snapshot, *, symbols=None, today=None, read_preview_frame=None):
    if symbols is None:
        symbols = {
            preview.symbol
            for preview in (*getattr(snapshot, "raw_previews", ()), *getattr(snapshot, "processed_previews", ()))
            if getattr(preview, "symbol", "")
        }
    return build_watchlist_data_statuses(
        service, set(symbols), today=today,
        processing_times=build_watchlist_processing_times(snapshot, set(symbols)),
        latest_records=_snapshot_records(snapshot, read_preview_frame),
    )


def build_report_data_status(service, snapshot, symbol, row, *, today=None, read_preview_frame=None):
    records = _snapshot_records(snapshot, read_preview_frame)
    snapshot_records = {(record.dataset, record.symbol): record for record in records} if records is not None else None
    times = build_watchlist_processing_times(snapshot, {symbol}).get(symbol)
    return build_watchlist_data_status(
        service, symbol, target_date=_latest_expected_market_date(today or date.today()),
        processing_times=times, snapshot_records=snapshot_records,
        report_frame=pd.DataFrame([row]),
    )


def format_status_dates(status: WatchlistDataStatus) -> str:
    def display(value):
        return value.isoformat() if value is not None else "없음"
    return (
        f"원본 가격 {display(status.daily_date)} · 수급 {display(status.investor_date)} · "
        f"분석 지표 {display(status.indicator_date)} · 전략 신호 {display(status.signal_date)} · "
        f"판단 리포트 {display(status.report_date)}"
    )


def _snapshot_records(snapshot, read_preview_frame):
    # Explicit None keeps the existing file-backed contract; empty DB records
    # remain authoritative. Lightweight render callers may only supply previews.
    if hasattr(snapshot, "latest_records"):
        return snapshot.latest_records
    records = []
    for preview in (*getattr(snapshot, "raw_previews", ()), *getattr(snapshot, "processed_previews", ())):
        if read_preview_frame is None or not getattr(preview, "symbol", ""):
            continue
        frame = read_preview_frame(preview)
        if frame is None:
            continue
        records.append(DatasetFrameRecord(
            dataset=preview.name, filename=preview.path.name, symbol=preview.symbol,
            row_count=len(frame), frame_json=frame_to_json(frame),
            created_at=getattr(preview, "created_at", None),
        ))
    return records
