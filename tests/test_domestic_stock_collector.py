from __future__ import annotations

from datetime import date

import pandas as pd

from invest_bot.config.settings import AppSettings
from invest_bot.db.engine import build_engine, build_session_factory
from invest_bot.db.repositories import SqlAlchemyDailyPriceRepository, SqlAlchemyInvestorDailyRepository
from invest_bot.db.write_path import SqlAlchemyMarketDataWriter
from invest_bot.jobs.collect_market_data import DEFAULT_COLLECTION_LOOKBACK_DAYS, collect_market_data_for_symbols
from invest_bot.market.collector import BatchCollectionResult, MarketDataCollector, MIN_REQUIRED_DAILY_PRICE_ROWS
from invest_bot.market.domestic_stock import DailyPriceRequest, DomesticStockDataCollector, InvestorDailyRequest, StockInfoRequest
from invest_bot.market.storage import CsvStorage
from tests.helpers import init_test_db, make_test_dir


class StubClient:
    def __init__(self, payload):
        self.payload = payload
        self.calls = []

    def get_json(self, api_path, tr_id, params, tr_cont=""):
        self.calls.append(
            {
                "api_path": api_path,
                "tr_id": tr_id,
                "params": params,
                "tr_cont": tr_cont,
            }
        )
        return self.payload


def test_collect_daily_prices_maps_reference_endpoint():
    client = StubClient({"output1": {"symbol": "005930"}, "output2": [{"stck_bsop_date": "20260327"}]})
    collector = DomesticStockDataCollector(client)

    summary, prices = collector.collect_daily_prices(
        DailyPriceRequest(symbol="005930", start_date=date(2026, 3, 1), end_date=date(2026, 3, 27))
    )

    assert client.calls[0]["api_path"].endswith("inquire-daily-itemchartprice")
    assert client.calls[0]["tr_id"] == "FHKST03010100"
    assert client.calls[0]["params"]["FID_INPUT_ISCD"] == "005930"
    assert not summary.empty
    assert not prices.empty


def test_collect_stock_info_maps_reference_endpoint():
    client = StubClient({"output": {"prdt_abrv_name": "삼성전자", "pdno": "005930"}})
    collector = DomesticStockDataCollector(client)

    result = collector.collect_stock_info(StockInfoRequest(symbol="005930"))

    assert client.calls[0]["api_path"].endswith("search-stock-info")
    assert client.calls[0]["tr_id"] == "CTPF1002R"
    assert result.iloc[0]["pdno"] == "005930"


def test_collect_investor_daily_maps_reference_endpoint():
    client = StubClient({"output1": [{"frgn_ntby_qty": "100"}], "output2": {"stck_bsop_date": "20260327"}})
    collector = DomesticStockDataCollector(client)

    detail, summary = collector.collect_investor_daily(
        InvestorDailyRequest(symbol="005930", target_date=date(2026, 3, 27))
    )

    assert client.calls[0]["api_path"].endswith("investor-trade-by-stock-daily")
    assert client.calls[0]["tr_id"] == "FHPTJ04160001"
    assert not detail.empty
    assert not summary.empty


def test_market_data_collector_saves_all_requested_csv_files():
    test_dir = make_test_dir("market_data_collector")
    collector = MarketDataCollector(settings=AppSettings(), storage=CsvStorage(test_dir))

    daily_summary, daily_prices = collector.save_daily_prices(
        "005930",
        date(2026, 3, 1),
        date(2026, 3, 29),
        pd.DataFrame([{"symbol": "005930"}]),
        pd.DataFrame([{"stck_bsop_date": "20260328"}]),
    )
    stock_info = collector.save_stock_info("005930", pd.DataFrame([{"pdno": "005930", "prdt_abrv_name": "삼성전자"}]))
    investor_detail, investor_summary = collector.save_investor_daily(
        "005930",
        date(2026, 3, 29),
        pd.DataFrame([{"frgn_ntby_qty": "100"}]),
        pd.DataFrame([{"stck_bsop_date": "20260329"}]),
    )

    assert daily_summary.path.exists()
    assert daily_prices.path.exists()
    assert stock_info.path.exists()
    assert investor_detail.path.exists()
    assert investor_summary.path.exists()


def test_market_data_collector_can_collect_multiple_symbols_with_stubbed_methods(monkeypatch):
    collector = MarketDataCollector(settings=AppSettings(), storage=CsvStorage(make_test_dir("market_data_batch")))
    sufficient_prices = pd.DataFrame(
        [{"stck_bsop_date": f"202603{index + 1:02d}", "symbol": "stub"} for index in range(MIN_REQUIRED_DAILY_PRICE_ROWS)]
    )

    monkeypatch.setattr(
        collector,
        "collect_daily_prices",
        lambda symbol, start_date, end_date: (
            pd.DataFrame([{"symbol": symbol}]),
            sufficient_prices.assign(symbol=symbol),
        ),
    )
    monkeypatch.setattr(
        collector,
        "collect_stock_info",
        lambda symbol: pd.DataFrame([{"pdno": symbol, "prdt_abrv_name": f"name-{symbol}"}]),
    )
    monkeypatch.setattr(
        collector,
        "collect_investor_daily",
        lambda symbol, target_date: (
            pd.DataFrame([{"frgn_ntby_qty": "100", "symbol": symbol}]),
            pd.DataFrame([{"stck_bsop_date": "20260329", "symbol": symbol}]),
        ),
    )

    results = collector.collect_symbols_batch(
        symbols=["005930", "000660"],
        start_date=date(2026, 3, 1),
        end_date=date(2026, 3, 29),
    )

    assert len(results) == 2
    assert all(isinstance(result, BatchCollectionResult) for result in results)
    assert all(result.status == "success" for result in results)
    assert results[0].symbol == "005930"
    assert results[1].symbol == "000660"


def test_collect_symbol_bundle_fails_when_daily_price_history_is_too_short(monkeypatch):
    collector = MarketDataCollector(settings=AppSettings(), storage=CsvStorage(make_test_dir("market_data_short_history")))

    monkeypatch.setattr(
        collector,
        "collect_daily_prices",
        lambda symbol, start_date, end_date: (
            pd.DataFrame([{"symbol": symbol}]),
            pd.DataFrame([{"stck_bsop_date": "20260328", "symbol": symbol}] * (MIN_REQUIRED_DAILY_PRICE_ROWS - 1)),
        ),
    )

    result = collector.collect_symbol_bundle(
        symbol="005930",
        start_date=date(2026, 3, 1),
        end_date=date(2026, 3, 29),
    )

    assert result.status == "failed"
    assert result.daily_price_rows == MIN_REQUIRED_DAILY_PRICE_ROWS - 1
    assert "At least 60 daily price rows are required" in result.error



def test_collect_market_data_for_symbols_defaults_to_365_days():
    settings = AppSettings()
    captured: dict[str, object] = {}

    class StubCollector:
        def collect_symbols_batch(self, symbols, start_date, end_date):
            captured["symbols"] = symbols
            captured["span_days"] = (end_date - start_date).days
            return []

    summary = collect_market_data_for_symbols(
        symbols=["005930"],
        settings=settings,
        collector=StubCollector(),
    )

    assert DEFAULT_COLLECTION_LOOKBACK_DAYS == 365
    assert summary["days"] == 365
    assert captured["span_days"] == 365

def test_collect_market_data_for_symbols_summarizes_batch_results():
    settings = AppSettings()

    class StubCollector:
        def collect_symbols_batch(self, symbols, start_date, end_date):
            assert symbols == ["005930", "000660"]
            assert start_date <= end_date
            return [
                BatchCollectionResult(
                    symbol="005930",
                    status="success",
                    daily_summary_rows=1,
                    daily_price_rows=20,
                    stock_info_rows=1,
                    investor_daily_rows=1,
                    investor_summary_rows=30,
                    saved_files=["a.csv"],
                ),
                BatchCollectionResult(
                    symbol="000660",
                    status="failed",
                    daily_summary_rows=0,
                    daily_price_rows=0,
                    stock_info_rows=0,
                    investor_daily_rows=0,
                    investor_summary_rows=0,
                    saved_files=[],
                    error="boom",
                ),
            ]

    summary = collect_market_data_for_symbols(
        symbols=["005930", "000660", "005930"],
        days=15,
        settings=settings,
        collector=StubCollector(),
    )

    assert summary["symbol_count"] == 2
    assert summary["symbols"] == ["005930", "000660"]
    assert summary["days"] == 15
    assert summary["successful_symbols"] == ["005930"]
    assert summary["failed_symbols"] == ["000660"]
    assert summary["success_count"] == 1
    assert summary["failed_count"] == 1


def test_collect_symbol_bundle_falls_back_when_stock_info_endpoint_fails(monkeypatch):
    collector = MarketDataCollector(settings=AppSettings(), storage=CsvStorage(make_test_dir("market_data_stock_info_fallback")))
    sufficient_prices = pd.DataFrame(
        [{"stck_bsop_date": f"202603{index + 1:02d}", "symbol": "stub"} for index in range(MIN_REQUIRED_DAILY_PRICE_ROWS)]
    )

    monkeypatch.setattr(
        collector,
        "collect_daily_prices",
        lambda symbol, start_date, end_date: (
            pd.DataFrame([{"symbol": symbol}]),
            sufficient_prices.assign(symbol=symbol),
        ),
    )
    monkeypatch.setattr(
        collector,
        "collect_stock_info",
        lambda symbol: (_ for _ in ()).throw(RuntimeError("stock info endpoint failed")),
    )
    monkeypatch.setattr(
        collector,
        "collect_investor_daily",
        lambda symbol, target_date: (
            pd.DataFrame([{"frgn_ntby_qty": "100", "symbol": symbol}]),
            pd.DataFrame([{"stck_bsop_date": "20260329", "symbol": symbol}]),
        ),
    )

    result = collector.collect_symbol_bundle(
        symbol="005930",
        start_date=date(2026, 3, 1),
        end_date=date(2026, 3, 29),
    )

    assert result.status == "success"
    assert result.stock_info_rows == 1
    assert "stock info endpoint failed" in result.error
    assert not any(path.endswith("/stock_info/005930.csv") for path in result.saved_files)


def test_market_data_collector_does_not_build_db_writer_when_db_write_is_disabled():
    collector = MarketDataCollector(settings=AppSettings())

    assert collector.db_writer is None


def _stub_successful_bundle_collection(monkeypatch, collector: MarketDataCollector) -> None:
    sufficient_prices = pd.DataFrame(
        [{"stck_bsop_date": value} for value in pd.date_range("2026-01-01", periods=60).strftime("%Y%m%d")]
    )
    monkeypatch.setattr(
        collector,
        "collect_daily_prices",
        lambda symbol, start_date, end_date: (pd.DataFrame([{"symbol": symbol}]), sufficient_prices),
    )
    monkeypatch.setattr(
        collector,
        "collect_stock_info",
        lambda symbol: pd.DataFrame([{"pdno": symbol, "prdt_abrv_name": "삼성전자"}]),
    )
    monkeypatch.setattr(
        collector,
        "collect_investor_daily",
        lambda symbol, target_date: (
            pd.DataFrame([{"frgn_ntby_qty": "100"}]),
            pd.DataFrame([{"stck_bsop_date": "20260329", "frgn_ntby_qty": "100"}]),
        ),
    )


def test_collect_symbol_bundle_reports_files_saved_before_later_failure_and_retries_cleanly(monkeypatch):
    test_dir = make_test_dir("market_data_partial_save")
    database_url = f"sqlite+pysqlite:///{(test_dir / 'partial-save.db').as_posix()}"
    init_test_db(database_url)
    collector = MarketDataCollector(
        settings=AppSettings(),
        storage=CsvStorage(test_dir),
        db_writer=SqlAlchemyMarketDataWriter(database_url),
    )
    _stub_successful_bundle_collection(monkeypatch, collector)
    original_save_investor_daily = collector.save_investor_daily
    attempts = 0

    def fail_once(*args, **kwargs):
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise RuntimeError("investor persistence failed")
        return original_save_investor_daily(*args, **kwargs)

    monkeypatch.setattr(collector, "save_investor_daily", fail_once)

    first = collector.collect_symbol_bundle("005930", date(2026, 3, 1), date(2026, 3, 29))
    second = collector.collect_symbol_bundle("005930", date(2026, 3, 1), date(2026, 3, 29))

    assert first.status == "failed"
    assert first.daily_summary_rows == 1
    assert first.daily_price_rows == MIN_REQUIRED_DAILY_PRICE_ROWS
    assert first.stock_info_rows == 1
    assert first.investor_daily_rows == 1
    assert first.investor_summary_rows == 1
    assert len(first.saved_files) == 3
    assert all(pd.read_csv(path).shape[0] > 0 for path in first.saved_files)
    assert "investor persistence failed" in first.error

    assert second.status == "success"
    assert len(second.saved_files) == 5
    assert len(set(second.saved_files)) == 5
    assert all(pd.read_csv(path).shape[0] > 0 for path in second.saved_files)
    session_factory = build_session_factory(build_engine(database_url))
    assert len(SqlAlchemyDailyPriceRepository(session_factory).list_for_symbol("005930")) == 60
    assert len(SqlAlchemyInvestorDailyRepository(session_factory).list_for_symbol("005930")) == 1


def test_collect_symbol_bundle_reports_first_snapshot_when_second_snapshot_fails(monkeypatch):
    test_dir = make_test_dir("market_data_second_snapshot_failure")
    collector = MarketDataCollector(settings=AppSettings(), storage=CsvStorage(test_dir))
    _stub_successful_bundle_collection(monkeypatch, collector)
    original_save = collector.storage.save
    failed_once = False

    def fail_second_snapshot(dataset, filename, frame):
        nonlocal failed_once
        if dataset == "daily_prices" and not failed_once:
            failed_once = True
            raise RuntimeError("second snapshot failed")
        return original_save(dataset, filename, frame)

    monkeypatch.setattr(collector.storage, "save", fail_second_snapshot)

    first = collector.collect_symbol_bundle("005930", date(2026, 3, 1), date(2026, 3, 29))
    second = collector.collect_symbol_bundle("005930", date(2026, 3, 1), date(2026, 3, 29))

    assert first.status == "failed"
    assert len(first.saved_files) == 1
    assert "/daily_prices_summary/" in first.saved_files[0]
    assert pd.read_csv(first.saved_files[0]).shape[0] == 1
    assert "second snapshot failed" in first.error
    assert second.status == "success"
    assert len(second.saved_files) == 5
    assert len(set(second.saved_files)) == 5


def test_collect_symbol_bundle_reports_snapshots_when_db_dual_write_fails(monkeypatch):
    test_dir = make_test_dir("market_data_db_dual_write_failure")
    database_url = f"sqlite+pysqlite:///{(test_dir / 'dual-write.db').as_posix()}"
    init_test_db(database_url)
    writer = SqlAlchemyMarketDataWriter(database_url)
    collector = MarketDataCollector(settings=AppSettings(), storage=CsvStorage(test_dir), db_writer=writer)
    _stub_successful_bundle_collection(monkeypatch, collector)
    original_db_save = writer.save_daily_prices
    attempts = 0

    def fail_db_once(*args, **kwargs):
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise RuntimeError("db dual-write failed")
        return original_db_save(*args, **kwargs)

    monkeypatch.setattr(writer, "save_daily_prices", fail_db_once)

    first = collector.collect_symbol_bundle("005930", date(2026, 3, 1), date(2026, 3, 29))
    second = collector.collect_symbol_bundle("005930", date(2026, 3, 1), date(2026, 3, 29))

    assert first.status == "failed"
    assert len(first.saved_files) == 2
    assert all(pd.read_csv(path).shape[0] > 0 for path in first.saved_files)
    assert "db dual-write failed" in first.error
    assert second.status == "success"
    assert len(second.saved_files) == 5
    assert len(set(second.saved_files)) == 5
    session_factory = build_session_factory(build_engine(database_url))
    assert len(SqlAlchemyDailyPriceRepository(session_factory).list_for_symbol("005930")) == 60
    assert len(SqlAlchemyInvestorDailyRepository(session_factory).list_for_symbol("005930")) == 1
