from __future__ import annotations

import os
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd
from sqlalchemy import Engine, event

from invest_bot.dashboard.service import DashboardDataService
from invest_bot.db.contracts import DatasetFrameRecord, StockRecord
from invest_bot.db.engine import build_engine, build_session_factory
from invest_bot.db.frame_storage import DbFrameStorage
from invest_bot.db.repositories import SqlAlchemyStockRepository, frame_to_json
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
                    "rsi_strategy_signal": "hold",
                    "rsi_strategy_reason": "rsi_14 is 58.00, between buy threshold 30.00 and sell threshold 70.00.",
                    "trend_filter_signal": "buy",
                    "trend_filter_reason": "close is 72000.00, above ma_60 68900.00 and above prev_close 71500.00.",
                    "mean_reversion_signal": "hold",
                    "mean_reversion_reason": "close is 72000.00, at 1.0256 of ma_20 70200.00, inside the mean-reversion band.",
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
    assert "rsi_strategy_signal" in report_preview.recommended_columns
    assert "trend_filter_signal" in report_preview.recommended_columns
    assert "mean_reversion_signal" in report_preview.recommended_columns

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


def test_dashboard_service_describes_strategy_fields_in_market_report_metadata() -> None:
    service = DashboardDataService()

    guide = service.DATASET_GUIDES["market_reports"]
    assert "rsi_strategy_signal" in guide.recommended_columns
    assert "trend_filter_signal" in guide.recommended_columns
    assert "mean_reversion_signal" in guide.recommended_columns

    assert service.COLUMN_META["rsi_strategy_signal"].label == "RSI 전략 판단"
    assert service.COLUMN_META["trend_filter_signal"].label == "추세 필터 전략 판단"
    assert service.COLUMN_META["mean_reversion_signal"].label == "평균회귀 전략 판단"


def test_dashboard_service_build_snapshot_batches_latest_record_lookup_once() -> None:
    created_at = datetime(2026, 9, 13, tzinfo=UTC)
    stored_frame = pd.DataFrame([{"symbol": "005930", "date": "2026-09-13", "close": 100}])
    records = [
        DatasetFrameRecord(
            dataset="daily_prices",
            filename="005930_daily_prices.csv",
            frame_json=frame_to_json(stored_frame),
            row_count=1,
            created_at=created_at,
            symbol="005930",
        ),
        DatasetFrameRecord(
            dataset="market_reports",
            filename="005930_market_reports.csv",
            frame_json=frame_to_json(stored_frame),
            row_count=1,
            created_at=created_at,
            symbol="005930",
        ),
    ]

    class _CountingRepository:
        def __init__(self) -> None:
            self.list_latest_calls: list[tuple[str, ...]] = []

        def list_latest(self, datasets):
            requested = tuple(datasets)
            self.list_latest_calls.append(requested)
            return [record for record in records if record.dataset in requested]

    class _CountingStorage:
        def __init__(self) -> None:
            self.repository = _CountingRepository()
            self.root_dir = Path("/virtual/dashboard")
            self.database_url = ""
            self.load_calls = 0

        def load(self, dataset: str, filename: str) -> pd.DataFrame:
            self.load_calls += 1
            return stored_frame.copy()

    storage = _CountingStorage()
    service = DashboardDataService(dataset_storage=storage)
    service._load_symbol_name_map = lambda: {"005930": "삼성전자"}  # type: ignore[method-assign]

    snapshot = service.build_snapshot()

    assert [preview.name for preview in snapshot.raw_previews] == ["daily_prices"]
    assert [preview.name for preview in snapshot.processed_previews] == ["market_reports"]
    assert storage.repository.list_latest_calls == [
        (*service.RAW_DATASETS, *service.PROCESSED_DATASETS)
    ]
    assert storage.load_calls == 0


def test_dashboard_snapshot_avoids_per_frame_sql_reads(tmp_path) -> None:
    database_url = f"sqlite:///{tmp_path / 'snapshot.db'}"
    init_test_db(database_url)
    storage = DbFrameStorage(database_url)
    datasets = (*DashboardDataService.RAW_DATASETS, *DashboardDataService.PROCESSED_DATASETS)
    for dataset in datasets:
        for symbol in ("005930", "000660"):
            storage.save(dataset, f"{symbol}_{dataset}.csv", pd.DataFrame([
                {"symbol": symbol, "date": "2026-09-19", "close": 100},
            ]))
    selects = []

    def count_selects(connection, cursor, statement, parameters, context, executemany):
        if statement.lstrip().upper().startswith("SELECT"):
            selects.append(statement)

    event.listen(Engine, "before_cursor_execute", count_selects)
    try:
        snapshot = DashboardDataService(dataset_storage=storage).build_snapshot()
    finally:
        event.remove(Engine, "before_cursor_execute", count_selects)

    previews = snapshot.raw_previews + snapshot.processed_previews
    assert {(preview.name, preview.symbol) for preview in previews} == {
        (dataset, symbol) for dataset in datasets for symbol in ("005930", "000660")
    }
    # One symbol map read plus the repository's per-dataset SELECTs; no frame reloads.
    assert len(selects) <= len(datasets) + 1


def test_dashboard_service_lists_all_backtest_history_artifacts_newest_first() -> None:
    test_dir = make_test_dir("dashboard_service_backtest_history")
    processed_storage = CsvStorage(test_dir / "processed")
    older = processed_storage.save(
        "backtest_summaries",
        "005930_golden-cross_20260720T010203Z_backtest_summary.csv",
        pd.DataFrame([{"run_id": "005930_golden-cross_20260720T010203Z", "symbol": "005930"}]),
    )
    newer = processed_storage.save(
        "backtest_summaries",
        "005930_golden-cross_20260721T020304Z_backtest_summary.csv",
        pd.DataFrame([{"run_id": "005930_golden-cross_20260721T020304Z", "symbol": "005930"}]),
    )
    os.utime(older.path, (datetime(2026, 7, 20).timestamp(), datetime(2026, 7, 20).timestamp()))
    os.utime(newer.path, (datetime(2026, 7, 21).timestamp(), datetime(2026, 7, 21).timestamp()))

    service = DashboardDataService(raw_root=test_dir / "raw", processed_root=test_dir / "processed")
    previews = service.list_backtest_history_previews()

    assert [preview.path.name for preview in previews] == [newer.path.name, older.path.name]
    assert all(preview.name == "backtest_summaries" for preview in previews)
    assert service.load_preview_frame(previews[0]).iloc[0]["run_id"] == "005930_golden-cross_20260721T020304Z"
