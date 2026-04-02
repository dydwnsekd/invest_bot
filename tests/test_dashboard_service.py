from __future__ import annotations

from pathlib import Path

import pandas as pd

from invest_bot.dashboard.service import DashboardDataService
from invest_bot.market.storage import CsvStorage
from tests.helpers import make_test_dir


def test_dashboard_service_renders_saved_raw_and_processed_data():
    test_dir = make_test_dir("dashboard_service")
    raw_storage = CsvStorage(test_dir / "raw")
    processed_storage = CsvStorage(test_dir / "processed")

    raw_storage.save(
        "daily_prices",
        "005930_20260301_20260329.csv",
        pd.DataFrame([{"date": "20260329", "close": 70000, "volume": 1000}]),
    )
    processed_storage.save(
        "daily_prices_indicators",
        "005930_20260301_20260329.csv",
        pd.DataFrame([{"date": "20260329", "ma_5": 69000, "rsi_14": 55.2}]),
    )

    service = DashboardDataService(raw_root=test_dir / "raw", processed_root=test_dir / "processed")
    html = service.render_html()

    assert "invest_bot dashboard" in html
    assert "daily_prices" in html
    assert "daily_prices_indicators" in html
