from __future__ import annotations

import pandas as pd
from sqlalchemy import Engine, event

from invest_bot.dashboard.service import DashboardDataService
from invest_bot.dashboard.streamlit_state import DashboardFrameLoader
from invest_bot.db.frame_storage import DbFrameStorage
from tests.helpers import init_test_db


def test_snapshot_reuses_report_and_chart_frames_without_queries_and_refreshes_next_render(tmp_path):
    database_url = f"sqlite:///{tmp_path / 'snapshot_frames.db'}"
    init_test_db(database_url)
    storage = DbFrameStorage(database_url)
    service = DashboardDataService(dataset_storage=storage)
    service._load_symbol_name_map = lambda: {}

    storage.save("market_reports", "005930_report.csv", pd.DataFrame([
        {"symbol": "005930", "date": "2026-09-25", "final_opinion": "buy"},
    ]))
    storage.save("daily_prices_indicators", "005930_indicator.csv", pd.DataFrame([
        {"symbol": "005930", "date": "2026-09-25", "open": 99, "high": 101,
         "low": 98, "close": 100, "volume": 1000},
    ]))
    storage.save("investor_daily", "005930_investor.csv", pd.DataFrame([
        {"symbol": "005930", "date": "2026-09-25", "foreign_net": 10},
    ]))

    snapshot = service.build_snapshot()
    preview = next(p for p in snapshot.processed_previews if p.name == "market_reports")
    loader = DashboardFrameLoader(service, snapshot.latest_records)
    selects = []

    def observe(conn, cursor, statement, parameters, context, executemany):
        if statement.lstrip().upper().startswith("SELECT"):
            selects.append(statement)

    event.listen(Engine, "before_cursor_execute", observe)
    try:
        report = loader.read_preview(preview)
        chart = loader.load_professional("005930")
        indicator = loader.load_indicator("005930")
    finally:
        event.remove(Engine, "before_cursor_execute", observe)
    assert selects == []
    assert report.iloc[-1]["final_opinion"] == "buy"
    assert chart is not None and chart.iloc[-1]["close"] == 100
    assert chart.iloc[-1]["foreign_net"] == 10
    assert indicator is not None and indicator.iloc[-1]["close"] == 100

    # A DB snapshot without a symbol is authoritative even if storage has a frame.
    empty_loader = DashboardFrameLoader(service, ())
    event.listen(Engine, "before_cursor_execute", observe)
    try:
        assert empty_loader.load_indicator("005930") is None
    finally:
        event.remove(Engine, "before_cursor_execute", observe)
    assert selects == []

    indicator.loc[0, "close"] = -1
    assert loader.load_indicator("005930").iloc[-1]["close"] == 100
    storage.save("daily_prices_indicators", "005930_indicator.csv", pd.DataFrame([
        {"symbol": "005930", "date": "2026-09-26", "open": 199, "high": 201,
         "low": 198, "close": 200, "volume": 2000},
    ]))
    assert loader.load_indicator("005930").iloc[-1]["close"] == 100
    next_snapshot = service.build_snapshot()
    next_loader = DashboardFrameLoader(service, next_snapshot.latest_records)
    assert next_loader.load_indicator("005930").iloc[-1]["close"] == 200
