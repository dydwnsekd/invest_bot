from __future__ import annotations

import pandas as pd
from sqlalchemy import inspect

from invest_bot.dashboard.service import DashboardDataService
from invest_bot.db.engine import build_engine
from invest_bot.db.frame_storage import DbFrameStorage
from invest_bot.jobs.analyze_daily_prices import generate_indicators_for_symbol
from invest_bot.jobs.generate_backtest import BacktestRequest, GoldenCrossBacktestGenerator
from invest_bot.jobs.generate_golden_cross_signals import GoldenCrossSignalGenerator
from invest_bot.jobs.generate_market_report import MarketReportGenerator, MarketReportRequest
from invest_bot.market.analysis import DailyPriceAnalyzer
from tests.helpers import init_test_db, make_test_dir


def make_db_url(test_dir) -> str:
    return f"sqlite+pysqlite:///{(test_dir / 'dataset-storage.db').as_posix()}"


def test_db_frame_storage_round_trips_latest_dataset_snapshots() -> None:
    test_dir = make_test_dir("db_frame_storage")
    database_url = make_db_url(test_dir)
    init_test_db(database_url)
    storage = DbFrameStorage(database_url)

    frame = pd.DataFrame([{"symbol": "005930", "value": 1}, {"symbol": "005930", "value": 2}])
    saved = storage.save("market_reports", "005930_20260612.csv", frame)

    loaded = storage.load("market_reports", "005930_20260612.csv")

    assert saved.rows == 2
    assert storage.latest_filename("market_reports", "005930") == "005930_20260612.csv"
    assert loaded.to_dict(orient="records") == frame.to_dict(orient="records")


def test_db_backed_analysis_and_dashboard_flow() -> None:
    test_dir = make_test_dir("db_backed_analysis_flow")
    database_url = make_db_url(test_dir)
    init_test_db(database_url)
    storage = DbFrameStorage(database_url)

    storage.save(
        "daily_prices",
        "005930_20260301_20260329.csv",
        pd.DataFrame(
            [
                {"stck_bsop_date": "20260301", "stck_clpr": "70000", "acml_vol": "1000"},
                {"stck_bsop_date": "20260302", "stck_clpr": "71000", "acml_vol": "1100"},
                {"stck_bsop_date": "20260303", "stck_clpr": "72000", "acml_vol": "1200"},
                {"stck_bsop_date": "20260304", "stck_clpr": "73000", "acml_vol": "1300"},
                {"stck_bsop_date": "20260305", "stck_clpr": "74000", "acml_vol": "1400"},
            ]
        ),
    )
    storage.save(
        "stock_info",
        "005930.csv",
        pd.DataFrame([{"pdno": "005930", "prdt_abrv_name": "삼성전자"}]),
    )
    storage.save(
        "investor_daily",
        "005930_20260305.csv",
        pd.DataFrame([{"stck_bsop_date": "20260305", "frgn_ntby_qty": "100", "orgn_ntby_qty": "50", "prsn_ntby_qty": "-150"}]),
    )

    analysis_result = generate_indicators_for_symbol(
        "005930",
        analyzer=DailyPriceAnalyzer(raw_storage=storage, processed_storage=storage),
    )
    assert analysis_result["indicator_rows"] == 5

    signal_generator = GoldenCrossSignalGenerator(processed_storage=storage)
    signal_frame = signal_generator.generate_signals(
        pd.DataFrame(
            [
                {"date": "2026-03-04", "close": 100, "ma_5": 98.0, "ma_20": 100.0},
                {"date": "2026-03-05", "close": 101, "ma_5": 101.0, "ma_20": 100.0},
            ]
        )
    )
    signal_generator.save_signals("005930_20260305.csv", signal_frame)

    report_generator = MarketReportGenerator(raw_storage=storage, processed_storage=storage)
    storage.save(
        "daily_prices_indicators",
        "005930_20260305.csv",
        pd.DataFrame(
            [
                {
                    "date": "2026-03-05",
                    "close": 71000,
                    "ma_5": 70500,
                    "ma_20": 70000,
                    "ma_60": 69000,
                    "rsi_14": 58,
                    "volume": 1500,
                    "volume_ma_5": 1200,
                }
            ]
        ),
    )
    request = MarketReportRequest(
        symbol="005930",
        indicator_filename="005930_20260305.csv",
        signal_filename="005930_20260305.csv",
        investor_filename="005930_20260305.csv",
    )
    report = report_generator.generate_report(
        request=request,
        indicator_frame=report_generator.load_indicator_frame(request),
        signal_frame=report_generator.load_signal_frame(request),
        investor_frame=report_generator.load_investor_frame(request),
        stock_info_frame=report_generator.load_stock_info_frame(request),
    )
    report_generator.save_report("005930_20260305.csv", report)

    backtest_generator = GoldenCrossBacktestGenerator(processed_storage=storage)
    backtest = backtest_generator.run_backtest(
        "005930",
        backtest_generator.load_signal_frame(BacktestRequest(symbol="005930", source_filename="005930_20260305.csv")),
    )
    backtest_generator.save_trades("005930_20260305.csv", backtest.trades)
    backtest_generator.save_summary("005930_20260305.csv", backtest.summary)

    service = DashboardDataService(dataset_storage=storage)
    snapshot = service.build_snapshot()

    assert any(preview.name == "daily_prices" for preview in snapshot.raw_previews)
    assert any(preview.name == "market_reports" for preview in snapshot.processed_previews)


def test_db_frame_storage_constructor_does_not_create_schema() -> None:
    test_dir = make_test_dir("db_frame_storage_no_schema")
    database_url = make_db_url(test_dir)

    DbFrameStorage(database_url)

    engine = build_engine(database_url)
    try:
        inspector = inspect(engine)
        assert "dataset_frames" not in inspector.get_table_names()
    finally:
        engine.dispose()
