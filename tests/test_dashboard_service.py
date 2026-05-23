from __future__ import annotations

import pandas as pd

from invest_bot.dashboard.service import DashboardDataService
from invest_bot.market.storage import CsvStorage
from tests.helpers import make_test_dir


def test_dashboard_service_renders_saved_raw_processed_and_test_report_data():
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
    raw_storage.save(
        "investor_daily",
        "005930_20260329.csv",
        pd.DataFrame([{"stck_bsop_date": "20260329", "frgn_ntby_qty": 1200, "orgn_ntby_qty": 300, "prsn_ntby_qty": -1500}]),
    )
    processed_storage.save(
        "daily_prices_indicators",
        "005930_20260301_20260329.csv",
        pd.DataFrame([{"date": "20260329", "close": 70000, "ma_5": 69000, "ma_20": 68000, "ma_60": 65000, "rsi_14": 55.2}]),
    )
    processed_storage.save(
        "golden_cross_signals",
        "005930_20260301_20260329.csv",
        pd.DataFrame(
            [
                {
                    "date": "20260329",
                    "close": 70000,
                    "signal": "buy",
                    "signal_reason": "ma_5 crossed above ma_20.",
                    "signal_ma_5": 70500,
                    "signal_ma_20": 70000,
                }
            ]
        ),
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
    html = service.render_html(message="005930 시장 리포트를 생성했습니다.", message_type="success")

    assert "invest_bot dashboard" in html
    assert "tab-button" in html
    assert "tab-panel" in html
    assert "대시보드 개요" in html
    assert "리포트 보드" in html
    assert "전체 파이프라인 실행" in html
    assert "데이터 수집 실행" in html
    assert "지표 계산 실행" in html
    assert "골든크로스 신호 생성" in html
    assert "시장 리포트 생성" in html
    assert "종목코드 또는 종목명" in html
    assert "시장 상황 요약 리포트" in html
    assert "최신 시장 리포트" in html
    assert "005930 시장 리포트를 생성했습니다." in html
    assert "삼성전자" in html
    assert "데이터 설명 보기" in html
    assert "컬럼 설명 보기" in html
    assert "표에 표시할 컬럼 선택" in html
    assert "컬럼 설명" in html
    assert "왜 보는가" in html
    assert "추천 컬럼만" in html
    assert "표시 행 수" in html
    assert "테스트 결과" in html
    assert "전체 테스트" in html
    assert "test_sell_signal" in html
    assert "failed" in html
    assert "골든크로스 신호" in html
    assert "최신 골든크로스 신호" in html
    assert "ma_5 crossed above ma_20." in html
    assert "column-toggle" in html
    assert "action=\"/actions/run-full-pipeline\"" in html
    assert "action=\"/actions/collect-market-data\"" in html
    assert "action=\"/actions/analyze-daily-prices\"" in html
    assert "action=\"/actions/generate-golden-cross-signals\"" in html
    assert "action=\"/actions/generate-market-report\"" in html
