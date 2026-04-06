from __future__ import annotations

import pandas as pd

from invest_bot.dashboard.service import DashboardDataService
from invest_bot.market.storage import CsvStorage
from tests.helpers import make_test_dir


def test_dashboard_service_renders_saved_raw_and_processed_data():
    test_dir = make_test_dir("dashboard_service")
    raw_storage = CsvStorage(test_dir / "raw")
    processed_storage = CsvStorage(test_dir / "processed")

    raw_storage.save(
        "stock_info",
        "005930.csv",
        pd.DataFrame([{"pdno": "005930", "prdt_abrv_name": "삼성전자"}]),
    )
    raw_storage.save(
        "daily_prices",
        "005930_20260301_20260329.csv",
        pd.DataFrame([{"date": "20260329", "close": 70000, "volume": 1000}]),
    )
    processed_storage.save(
        "daily_prices_indicators",
        "005930_20260301_20260329.csv",
        pd.DataFrame([{"date": "20260329", "close": 70000, "ma_5": 69000, "rsi_14": 55.2}]),
    )

    service = DashboardDataService(raw_root=test_dir / "raw", processed_root=test_dir / "processed")
    html = service.render_html()

    assert "invest_bot dashboard" in html
    assert "일봉 가격 데이터" in html
    assert "기본 지표 계산 결과" in html
    assert "삼성전자" in html
    assert "종목명" in html
    assert "컬럼 설명" in html
    assert "왜 보는가" in html
    assert "추천 컬럼만" in html
    assert "표시 행 수" in html
    assert "column-toggle" in html
