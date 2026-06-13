from __future__ import annotations

import pandas as pd

from invest_bot.dashboard.service import DashboardDataService
from invest_bot.dashboard.streamlit_state import load_indicator_frame_for_symbol, read_preview_frame
from invest_bot.market.storage import CsvStorage
from tests.helpers import make_test_dir


def test_read_preview_frame_uses_injected_service_context() -> None:
    test_dir = make_test_dir("streamlit_state_preview")
    raw_storage = CsvStorage(test_dir / "raw")
    processed_storage = CsvStorage(test_dir / "processed")
    raw_storage.save("stock_info", "005930.csv", pd.DataFrame([{"pdno": "005930", "prdt_abrv_name": "삼성전자"}]))
    processed_storage.save(
        "market_reports",
        "005930_20260329.csv",
        pd.DataFrame([{"symbol": "005930", "symbol_name": "삼성전자", "date": "2026-03-29", "final_opinion": "buy"}]),
    )
    service = DashboardDataService(raw_root=test_dir / "raw", processed_root=test_dir / "processed")
    preview = service.build_snapshot().processed_previews[0]

    frame = read_preview_frame(service, preview)

    assert str(frame.iloc[0]["symbol"]).zfill(6) == "005930"


def test_load_indicator_frame_for_symbol_uses_injected_service_context() -> None:
    test_dir = make_test_dir("streamlit_state_indicator")
    raw_storage = CsvStorage(test_dir / "raw")
    processed_storage = CsvStorage(test_dir / "processed")
    raw_storage.save("stock_info", "005930.csv", pd.DataFrame([{"pdno": "005930", "prdt_abrv_name": "삼성전자"}]))
    processed_storage.save(
        "daily_prices_indicators",
        "005930_20260329.csv",
        pd.DataFrame([{"symbol": "005930", "date": "2026-03-29", "close": 70000, "ma_5": 69000, "ma_20": 68000}]),
    )
    service = DashboardDataService(raw_root=test_dir / "raw", processed_root=test_dir / "processed")

    frame = load_indicator_frame_for_symbol(service, "005930")

    assert frame is not None
    assert frame.iloc[0]["close"] == 70000
