from __future__ import annotations

import pandas as pd

from invest_bot.dashboard.service import DashboardDataService
from invest_bot.db.contracts import StockRecord
from invest_bot.db.engine import build_engine, build_session_factory
from invest_bot.db.frame_storage import DbFrameStorage
from invest_bot.db.repositories import SqlAlchemyStockRepository
from invest_bot.market.storage import CsvStorage
from tests.helpers import init_test_db, make_test_dir


def test_dashboard_service_builds_streamlit_snapshot_and_test_report() -> None:
    test_dir = make_test_dir("dashboard_service")
    raw_storage = CsvStorage(test_dir / "raw")
    processed_storage = CsvStorage(test_dir / "processed")
    report_dir = test_dir / "reports"
    report_dir.mkdir(parents=True, exist_ok=True)

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
        "market_reports",
        "005930_20260329.csv",
        pd.DataFrame(
            [
                {
                    "symbol": "005930",
                    "symbol_name": "삼성전자",
                    "date": "2026-03-29",
                    "golden_cross_signal": "buy",
                    "golden_cross_reason": "ma_5 crossed above ma_20.",
                    "trend_state": "bullish",
                    "rsi_state": "strong",
                    "volume_state": "active",
                    "investor_flow": "supportive",
                    "summary": "추세는 상승 우세이며 골든크로스 매수 신호가 확인됩니다.",
                    "final_opinion": "buy",
                }
            ]
        ),
    )

    (report_dir / "pytest_results.xml").write_text(
        """
<testsuite tests="2" failures="1" skipped="0" errors="0">
  <testcase classname="tests.test_golden_cross_strategy" name="test_buy_signal" />
  <testcase classname="tests.test_golden_cross_strategy" name="test_sell_signal">
    <failure message="assert buy == sell">assert buy == sell</failure>
  </testcase>
</testsuite>
        """.strip(),
        encoding="utf-8",
    )
    (report_dir / "pytest_command.txt").write_text(
        "python -m pytest tests/test_golden_cross_strategy.py",
        encoding="utf-8",
    )

    service = DashboardDataService(
        raw_root=test_dir / "raw",
        processed_root=test_dir / "processed",
        test_report_path=report_dir / "pytest_results.xml",
    )

    snapshot = service.build_snapshot()
    report = service.load_test_report()

    assert [preview.name for preview in snapshot.raw_previews] == ["daily_prices", "stock_info"]
    assert [preview.name for preview in snapshot.processed_previews] == ["market_reports"]

    raw_preview = snapshot.raw_previews[0]
    assert raw_preview.display_name == "일봉 가격 데이터"
    assert raw_preview.symbol == "005930"
    assert raw_preview.symbol_name == "삼성전자"
    assert raw_preview.recommended_columns[:3] == ["symbol_name", "symbol", "date"]
    assert raw_preview.row_count == 1

    report_preview = snapshot.processed_previews[0]
    assert report_preview.display_name == "시장 상황 요약 리포트"
    assert report_preview.symbol_name == "삼성전자"
    assert "final_opinion" in report_preview.recommended_columns

    assert report is not None
    assert report.total == 2
    assert report.passed == 1
    assert report.failed == 1
    assert report.command == "python -m pytest tests/test_golden_cross_strategy.py"
    assert report.test_cases[1].name == "tests.test_golden_cross_strategy::test_sell_signal"
    assert report.test_cases[1].status == "failed"


def test_dashboard_service_prefers_canonical_symbol_names_over_stock_info_snapshot() -> None:
    test_dir = make_test_dir("dashboard_service_canonical_symbol_names")
    database_url = f"sqlite+pysqlite:///{(test_dir / 'dashboard.db').as_posix()}"
    init_test_db(database_url)
    storage = DbFrameStorage(database_url)

    session_factory = build_session_factory(build_engine(database_url))
    stock_repo = SqlAlchemyStockRepository(session_factory)
    stock_repo.upsert(StockRecord(symbol="000660", symbol_name="SK하이닉스", market="KOSPI"))

    storage.save(
        "stock_info",
        "000660.csv",
        pd.DataFrame([{"pdno": "000660", "prdt_abrv_name": "000660", "collection_warning": "fallback"}]),
    )
    storage.save(
        "daily_prices",
        "000660_20260301_20260329.csv",
        pd.DataFrame([{"date": "20260329", "close": 200000, "volume": 1000}]),
    )

    service = DashboardDataService(dataset_storage=storage)
    snapshot = service.build_snapshot()
    daily_preview = next(preview for preview in snapshot.raw_previews if preview.name == "daily_prices")

    assert daily_preview.symbol == "000660"
    assert daily_preview.symbol_name == "SK하이닉스"
