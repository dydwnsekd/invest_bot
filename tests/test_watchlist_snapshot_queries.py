from datetime import UTC, date, datetime

import pandas as pd
from sqlalchemy import Engine, event

from invest_bot.dashboard.service import DashboardDataService
from invest_bot.dashboard.streamlit_watchlist import build_watchlist_data_statuses, build_watchlist_processing_times
from invest_bot.db.contracts import DatasetFrameRecord
from invest_bot.db.frame_storage import DbFrameStorage
from invest_bot.db.repositories import frame_to_json
from invest_bot.market.storage import CsvStorage
from tests.helpers import init_test_db


def test_watchlist_snapshot_preserves_statuses_without_extra_queries_and_refreshes_next_render(tmp_path):
    database_url = f"sqlite:///{tmp_path / 'watchlist.db'}"
    init_test_db(database_url)
    storage = DbFrameStorage(database_url)
    service = DashboardDataService(dataset_storage=storage)
    service._load_symbol_name_map = lambda: {}
    today = date(2026, 9, 25)
    symbols = {"005930", "000660", "005380", "005385"}
    datasets = ("daily_prices", "investor_daily_summary", "daily_prices_indicators", "golden_cross_signals", "market_reports")
    for dataset in datasets:
        storage.save(dataset, f"005930_{dataset}.csv", pd.DataFrame([
            {"symbol": "005930", "date": "2026-09-25"},
        ]))
    # Newer save time and filename must not replace the newer as_of_date.
    storage.save("daily_prices", "005930_20990101.csv", pd.DataFrame([
        {"symbol": "005930", "date": "2026-09-24"},
    ]))
    # Record symbol is authoritative even when the filename has no symbol.
    storage.save("daily_prices", "alternate.csv", pd.DataFrame([
        {"symbol": "000660", "date": "2026-09-25"},
    ]))
    storage.save("investor_daily_summary", "000660_flow.csv", pd.DataFrame([
        {"symbol": "000660", "date": "2026-09-25"},
    ]))
    storage.save("market_reports", "000660_report.csv", pd.DataFrame([
        {"symbol": "000660", "date": "2026-09-24"},
    ]))
    # Preserve column precedence and fallback past an all-invalid column.
    storage.save("daily_prices", "005380_prices.csv", pd.DataFrame([
        {"symbol": "005380", "trade_date": "invalid", "stck_bsop_date": "20260924", "date": "2026-09-25"},
    ]))
    storage.repository.save(DatasetFrameRecord(
        dataset="investor_daily_summary", filename="005380_empty.csv", symbol="005380",
        frame_json=frame_to_json(pd.DataFrame()), row_count=0, created_at=datetime.now(UTC),
    ))
    # 005385 is entirely missing and must not trigger fallback lookups.
    snapshot = service.build_snapshot()
    times = build_watchlist_processing_times(snapshot, symbols)
    baseline = build_watchlist_data_statuses(service, symbols, today=today, processing_times=times)
    selects = []

    def observe(conn, cursor, statement, parameters, context, executemany):
        if statement.lstrip().upper().startswith("SELECT"):
            selects.append(statement)

    event.listen(Engine, "before_cursor_execute", observe)
    try:
        actual = build_watchlist_data_statuses(
            service, symbols, today=today, processing_times=times, latest_records=snapshot.latest_records,
        )
    finally:
        event.remove(Engine, "before_cursor_execute", observe)
    assert actual == baseline
    assert selects == []
    by_symbol = {item.symbol: item for item in actual}
    assert by_symbol["005930"].label == "최신"
    assert by_symbol["000660"].label == "분석 갱신 필요"
    assert by_symbol["005380"].daily_date == date(2026, 9, 24)
    assert by_symbol["005385"].daily_date is None

    # An empty authoritative snapshot must stay missing even if storage has data.
    empty = build_watchlist_data_statuses(service, {"005930"}, today=today, latest_records=())
    assert empty[0].daily_date is None

    storage.save("market_reports", "005930_market_reports.csv", pd.DataFrame([
        {"symbol": "005930", "date": "2026-09-24"},
    ]))
    same_snapshot = build_watchlist_data_statuses(service, symbols, today=today, latest_records=snapshot.latest_records)
    assert next(item for item in same_snapshot if item.symbol == "005930").label == "최신"
    next_snapshot = service.build_snapshot()
    refreshed = build_watchlist_data_statuses(service, symbols, today=today, latest_records=next_snapshot.latest_records)
    assert next(item for item in refreshed if item.symbol == "005930").label == "분석 갱신 필요"


def test_watchlist_file_snapshot_keeps_file_reads_and_sees_updated_dates(tmp_path):
    raw = CsvStorage(tmp_path / "raw")
    processed = CsvStorage(tmp_path / "processed")
    service = DashboardDataService(raw_root=raw.root_dir, processed_root=processed.root_dir)
    service._load_symbol_name_map = lambda: {}
    raw.save("daily_prices", "005930_prices.csv", pd.DataFrame([{"date": "2026-09-24"}]))
    raw.save("investor_daily_summary", "005930_flow.csv", pd.DataFrame([{"date": "2026-09-25"}]))
    for dataset in ("daily_prices_indicators", "golden_cross_signals", "market_reports"):
        processed.save(dataset, f"005930_{dataset}.csv", pd.DataFrame([{"date": "2026-09-25"}]))
    snapshot = service.build_snapshot()
    assert snapshot.latest_records is None
    statuses = build_watchlist_data_statuses(
        service, {"005930"}, today=date(2026, 9, 25), latest_records=snapshot.latest_records,
    )
    assert statuses[0].label == "데이터 갱신 필요"
    raw.save("daily_prices", "005930_prices.csv", pd.DataFrame([{"date": "2026-09-25"}]))
    updated = build_watchlist_data_statuses(service, {"005930"}, today=date(2026, 9, 25))
    assert updated[0].label == "최신"
