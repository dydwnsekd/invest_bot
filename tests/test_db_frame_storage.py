from __future__ import annotations

from datetime import date, datetime

import pandas as pd
import pytest
from sqlalchemy import inspect

from invest_bot.dashboard.service import DashboardDataService
from invest_bot.db.contracts import StockRecord
from invest_bot.db.engine import build_session_factory
from invest_bot.db.engine import build_engine
from invest_bot.db.frame_storage import DbFrameStorage
from invest_bot.db.repositories import SqlAlchemyStockRepository, frame_to_json
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


def test_db_frame_storage_resolves_latest_date_from_unsorted_price_frame() -> None:
    test_dir = make_test_dir("db_frame_storage_unsorted_as_of")
    database_url = make_db_url(test_dir)
    init_test_db(database_url)
    storage = DbFrameStorage(database_url)

    storage.save(
        "daily_prices",
        "005930_20260701_20260710.csv",
        pd.DataFrame(
            [
                {"symbol": "005930", "stck_bsop_date": "20260710", "stck_clpr": "72000"},
                {"symbol": "005930", "stck_bsop_date": "20260709", "stck_clpr": "71000"},
                {"symbol": "005930", "stck_bsop_date": "20260701", "stck_clpr": "70000"},
            ]
        ),
    )
    storage.save(
        "daily_prices",
        "005930_20260703.csv",
        pd.DataFrame([{"symbol": "005930", "stck_bsop_date": "20260703", "stck_clpr": "69000"}]),
    )

    assert storage.latest_filename("daily_prices", "005930") == "005930_20260701_20260710.csv"


def test_db_backed_analysis_and_dashboard_flow() -> None:
    test_dir = make_test_dir("db_backed_analysis_flow")
    database_url = make_db_url(test_dir)
    init_test_db(database_url)
    storage = DbFrameStorage(database_url)
    session_factory = build_session_factory(build_engine(database_url))
    SqlAlchemyStockRepository(session_factory).upsert(StockRecord(symbol="005930", symbol_name="삼성전자", market="KOSPI"))

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

    backtest_indicator_filename = "005930_backtest_indicators.csv"
    storage.save(
        "daily_prices_indicators", backtest_indicator_filename,
        signal_frame.loc[:, ["date", "close", "ma_5", "ma_20"]],
    )
    backtest_generator = GoldenCrossBacktestGenerator(processed_storage=storage)
    backtest = backtest_generator.run_backtest(
        "005930",
        backtest_generator.load_signal_frame(BacktestRequest(
            symbol="005930", source_filename="005930_20260305.csv", indicator_filename=backtest_indicator_filename,
        )),
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


@pytest.mark.parametrize("values", [
    pd.Series([20261002, None], dtype="Int64"),
    pd.Series([20261002.0, None], dtype="Float64"),
    pd.Series([20261002]),
    pd.Series([20261002.0]),
    pd.Series(["20261002"]),
    pd.Series(["20261002.0"]),
])
def test_snapshot_as_of_date_accepts_compact_date_representations(values):
    frame = pd.DataFrame({"stck_bsop_date": values})

    assert DbFrameStorage._resolve_as_of_date(frame) == date(2026, 10, 2)


@pytest.mark.parametrize("value", [
    20261002.5, "20261002.5", 2026102, "2026102", 202610020,
    "202610020", 2026, "2026", True, False, float("nan"), float("inf"),
    float("-inf"), None, pd.NA, pd.NaT, "", "bad-date", "20261301",
    "20260230", "2026-02-30", "NaN", "Infinity", "-Infinity",
])
def test_snapshot_as_of_date_rejects_invalid_values_without_epoch_fallback(value):
    assert DbFrameStorage._resolve_as_of_date(pd.DataFrame({"date": [value]})) is None


def test_snapshot_as_of_date_preserves_mixed_dates_and_input_with_repeated_index():
    frame = pd.DataFrame({
        "date": pd.Series([
            "invalid", "20261001.0", 20261002, 20261002.0, "2026-10-03",
            "2026/10/04", date(2026, 10, 5), datetime(2026, 10, 6, 12),
            pd.Timestamp("2026-10-07"), "20261008", 20261009.5, None,
        ], dtype=object),
        "value": range(12),
    }).iloc[::-1]
    frame.index = [7] * len(frame)
    before = frame.copy(deep=True)

    assert DbFrameStorage._resolve_as_of_date(frame) == date(2026, 10, 8)
    pd.testing.assert_frame_equal(frame, before)


@pytest.mark.parametrize("latest", [
    "2026-10-12", "2026/10/12", date(2026, 10, 12),
    datetime(2026, 10, 12, 12), pd.Timestamp("2026-10-12"),
])
def test_snapshot_as_of_date_retains_each_valid_type_in_mixed_column(latest):
    frame = pd.DataFrame({"date": pd.Series([
        "20261001", "bad", 20261002, 20261003.0, "20261004.0", latest,
    ], dtype=object)})

    assert DbFrameStorage._resolve_as_of_date(frame) == date(2026, 10, 12)


def test_snapshot_as_of_date_compares_local_days_without_utc_conversion():
    frame = pd.DataFrame({"date": pd.Series([
        pd.Timestamp("2026-10-03T00:30:00+14:00"),
        "2026-10-02T23:30:00-12:00",
        datetime.fromisoformat("2026-10-02T12:00:00+09:00"),
        date(2026, 10, 1),
    ], dtype=object)})

    assert DbFrameStorage._resolve_as_of_date(frame) == date(2026, 10, 3)


@pytest.mark.parametrize(("columns", "expected"), [
    ({"date": ["bad", 20261002], "trade_date": [20261010, 20261009],
      "stck_bsop_date": [20261020, 20261019]}, date(2026, 10, 2)),
    ({"date": [None, "bad"], "trade_date": [20261003, 20261002],
      "stck_bsop_date": [20261020, 20261019]}, date(2026, 10, 3)),
    ({"date": [None, "bad"], "trade_date": [20261003.5, "20260230"],
      "stck_bsop_date": [20261004.0, 20261002.0]}, date(2026, 10, 4)),
    ({"value": [1, 2]}, None),
    ({"date": [None, "bad"], "trade_date": [None, "20261301"],
      "stck_bsop_date": [float("inf"), 20261004.5]}, None),
    ({"date": []}, None),
])
def test_snapshot_as_of_date_keeps_column_precedence_and_invalid_column_fallback(columns, expected):
    assert DbFrameStorage._resolve_as_of_date(pd.DataFrame(columns)) == expected


@pytest.mark.parametrize("values", [
    pd.Series([20261002]), pd.Series([20261002.0]), pd.Series(["20261002"]),
    pd.Series(["20261002.0"]), pd.Series([20261002, None], dtype="Int64"),
    pd.Series([20261002.0, None], dtype="Float64"),
])
def test_numeric_snapshot_dates_round_trip_payload_and_choose_latest_in_sqlite(tmp_path, values):
    database_url = f"sqlite:///{tmp_path / 'numeric-date.db'}"
    init_test_db(database_url)
    storage = DbFrameStorage(database_url)
    frame = pd.DataFrame({"stck_bsop_date": values})
    before = frame.copy(deep=True)

    storage.save("daily_prices", "005930_newer.csv", frame)
    storage.save("daily_prices", "005930_older.csv", pd.DataFrame({"date": ["2026-10-01"]}))
    storage.save("daily_prices", "005930_invalid.csv", pd.DataFrame({"date": ["20261003.5"]}))

    record = storage.repository.load("daily_prices", "005930_newer.csv")
    assert record is not None
    assert record.as_of_date == date(2026, 10, 2)
    assert record.frame_json == frame_to_json(before)
    assert record.row_count == len(before)
    pd.testing.assert_frame_equal(frame, before)
    pd.testing.assert_frame_equal(storage.load("daily_prices", "005930_newer.csv"), before)
    invalid = storage.repository.load("daily_prices", "005930_invalid.csv")
    assert invalid is not None and invalid.as_of_date is None
    assert storage.latest_filename("daily_prices", "005930") == "005930_newer.csv"
    assert storage.repository.list_latest(("daily_prices",))[0].filename == "005930_newer.csv"
