from __future__ import annotations

from datetime import date

import pandas as pd

from invest_bot.config.settings import AppSettings
from invest_bot.db.contracts import StockRecord
from invest_bot.db.engine import build_engine, build_session_factory
from invest_bot.db.repositories import (
    SqlAlchemyDailyPriceRepository,
    SqlAlchemyInvestorDailyRepository,
    SqlAlchemyStockRepository,
)
from invest_bot.db.write_path import SqlAlchemyMarketDataWriter
from invest_bot.market.collector import MarketDataCollector
from invest_bot.market.storage import CsvStorage
from tests.helpers import init_test_db, make_test_dir


def make_db_url(test_dir) -> str:
    return f"sqlite+pysqlite:///{(test_dir / 'market-data.db').as_posix()}"


def test_market_data_collector_dual_writes_csv_and_db():
    test_dir = make_test_dir("db_write_dual_write")
    database_url = make_db_url(test_dir)
    init_test_db(database_url)
    writer = SqlAlchemyMarketDataWriter(database_url)
    collector = MarketDataCollector(settings=AppSettings(), storage=CsvStorage(test_dir / "raw"), db_writer=writer)
    session_factory = build_session_factory(build_engine(database_url))
    stock_repo = SqlAlchemyStockRepository(session_factory)
    stock_repo.upsert(StockRecord(symbol="005930", symbol_name="삼성전자", market="KOSPI"))

    collector.save_stock_info("5930", pd.DataFrame([{"pdno": "005930", "prdt_abrv_name": "삼성전자", "prdt_type_cd": "KOSPI"}]))
    collector.save_daily_prices(
        "5930",
        date(2026, 3, 1),
        date(2026, 3, 2),
        pd.DataFrame([{"symbol": "005930"}]),
        pd.DataFrame(
            [
                {
                    "stck_bsop_date": "20260302",
                    "stck_oprc": "1000",
                    "stck_hgpr": "1100",
                    "stck_lwpr": "900",
                    "stck_clpr": "1050",
                    "acml_vol": "12345",
                }
            ]
        ),
    )
    collector.save_investor_daily(
        "5930",
        date(2026, 3, 2),
        pd.DataFrame([{"investor": "foreign", "net_volume": "100"}]),
        pd.DataFrame([{"stck_bsop_date": "20260302", "frgn_ntby_qty": "100", "orgn_ntby_qty": "50", "prsn_ntby_qty": "-150"}]),
    )

    assert (test_dir / "raw" / "stock_info" / "5930.csv").exists()
    assert (test_dir / "raw" / "daily_prices" / "5930_20260301_20260302.csv").exists()
    assert (test_dir / "raw" / "investor_daily_summary" / "5930_20260302.csv").exists()

    daily_repo = SqlAlchemyDailyPriceRepository(session_factory)
    investor_repo = SqlAlchemyInvestorDailyRepository(session_factory)

    stock = stock_repo.get_by_symbol("5930")
    assert stock is not None
    assert stock.symbol == "005930"
    assert stock.symbol_name == "삼성전자"

    prices = daily_repo.list_for_symbol("005930")
    assert len(prices) == 1
    assert prices[0].close_price == 1050.0
    assert daily_repo.latest_trade_date("005930") == date(2026, 3, 2)

    investor_rows = investor_repo.list_for_symbol("005930")
    assert len(investor_rows) == 1
    assert investor_rows[0].foreign_net_qty == 100.0
    assert investor_rows[0].institutional_net_qty == 50.0
    assert investor_rows[0].personal_net_qty == -150.0
    assert investor_repo.latest_trade_date("005930") == date(2026, 3, 2)


def test_market_data_collector_skips_persisting_fallback_stock_info() -> None:
    test_dir = make_test_dir("db_write_skip_fallback_stock_info")
    database_url = make_db_url(test_dir)
    init_test_db(database_url)
    writer = SqlAlchemyMarketDataWriter(database_url)
    collector = MarketDataCollector(settings=AppSettings(), storage=CsvStorage(test_dir / "raw"), db_writer=writer)

    collector.save_stock_info(
        "000660",
        pd.DataFrame([{"pdno": "000660", "prdt_abrv_name": "000660", "collection_warning": "api timeout"}]),
    )

    assert not (test_dir / "raw" / "stock_info" / "000660.csv").exists()


def test_db_writer_reuses_same_trade_date_without_duplicates():
    test_dir = make_test_dir("db_write_dedup")
    database_url = make_db_url(test_dir)
    init_test_db(database_url)
    writer = SqlAlchemyMarketDataWriter(database_url)

    writer.save_daily_prices(
        "005930",
        date(2026, 3, 1),
        date(2026, 3, 2),
        pd.DataFrame(),
        pd.DataFrame([{"stck_bsop_date": "20260302", "stck_clpr": "1000"}]),
    )
    writer.save_daily_prices(
        "005930",
        date(2026, 3, 1),
        date(2026, 3, 2),
        pd.DataFrame(),
        pd.DataFrame([{"stck_bsop_date": "20260302", "stck_clpr": "1010"}]),
    )
    writer.save_investor_daily(
        "005930",
        date(2026, 3, 2),
        pd.DataFrame([{"source": "first"}]),
        pd.DataFrame([{"stck_bsop_date": "20260302", "frgn_ntby_qty": "100"}]),
    )
    writer.save_investor_daily(
        "005930",
        date(2026, 3, 2),
        pd.DataFrame([{"source": "second"}]),
        pd.DataFrame([{"stck_bsop_date": "20260302", "frgn_ntby_qty": "120"}]),
    )

    session_factory = build_session_factory(build_engine(database_url))
    daily_repo = SqlAlchemyDailyPriceRepository(session_factory)
    investor_repo = SqlAlchemyInvestorDailyRepository(session_factory)

    prices = daily_repo.list_for_symbol("005930")
    assert len(prices) == 1
    assert prices[0].close_price == 1010.0

    investor_rows = investor_repo.list_for_symbol("005930")
    assert len(investor_rows) == 1
    assert investor_rows[0].foreign_net_qty == 120.0
    assert 'second' in investor_rows[0].raw_payload
