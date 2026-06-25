from __future__ import annotations

import pandas as pd

from invest_bot.db.contracts import StockRecord
from invest_bot.db.engine import build_engine, build_session_factory
from invest_bot.db.frame_storage import DbFrameStorage
from invest_bot.db.repositories import SqlAlchemyStockRepository
from invest_bot.jobs.generate_market_report import MarketReportGenerator, MarketReportRequest
from invest_bot.market.storage import CsvStorage
from tests.helpers import init_test_db, make_test_dir


def test_market_report_generator_builds_and_saves_summary_report():
    test_dir = make_test_dir("market_report_generator")
    raw_storage = CsvStorage(test_dir / "raw")
    processed_storage = CsvStorage(test_dir / "processed")
    generator = MarketReportGenerator(raw_storage=raw_storage, processed_storage=processed_storage)

    processed_storage.save(
        "daily_prices_indicators",
        "005930_indicators.csv",
        pd.DataFrame(
            [
                {
                    "date": "2026-04-10",
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
    processed_storage.save(
        "golden_cross_signals",
        "005930_signals.csv",
        pd.DataFrame(
            [
                {
                    "date": "2026-04-10",
                    "signal": "buy",
                    "signal_reason": "ma_5 crossed above ma_20.",
                    "signal_ma_5": 70500,
                    "signal_ma_20": 70000,
                }
            ]
        ),
    )
    raw_storage.save(
        "investor_daily",
        "005930_20260410.csv",
        pd.DataFrame([{"frgn_ntby_qty": "120", "orgn_ntby_qty": "80", "prsn_ntby_qty": "-200"}]),
    )
    raw_storage.save(
        "stock_info",
        "005930.csv",
        pd.DataFrame([{"pdno": "005930", "prdt_abrv_name": "Samsung Electronics"}]),
    )

    request = MarketReportRequest(
        symbol="005930",
        indicator_filename="005930_indicators.csv",
        signal_filename="005930_signals.csv",
        investor_filename="005930_20260410.csv",
    )

    report = generator.generate_report(
        request=request,
        indicator_frame=generator.load_indicator_frame(request),
        signal_frame=generator.load_signal_frame(request),
        investor_frame=generator.load_investor_frame(request),
        stock_info_frame=generator.load_stock_info_frame(request),
    )
    saved = generator.save_report("005930_20260410.csv", report)

    assert saved.path.exists()
    assert report.iloc[0]["symbol"] == "005930"
    assert report.iloc[0]["golden_cross_signal"] == "buy"
    assert report.iloc[0]["rsi_strategy_signal"] == "hold"
    assert "between buy threshold" in report.iloc[0]["rsi_strategy_reason"]
    assert report.iloc[0]["trend_filter_signal"] == "hold"
    assert report.iloc[0]["trend_filter_reason"].startswith("Missing indicators: prev_close")
    assert report.iloc[0]["mean_reversion_signal"] == "hold"
    assert "inside the mean-reversion band" in report.iloc[0]["mean_reversion_reason"]
    assert report.iloc[0]["trend_state"] == "bullish"
    assert report.iloc[0]["rsi_state"] == "strong"
    assert report.iloc[0]["volume_state"] == "active"
    assert report.iloc[0]["investor_flow"] == "supportive"
    assert report.iloc[0]["final_opinion"] == "buy"


def test_market_report_generator_prefers_canonical_symbol_name_over_stock_info_fallback():
    test_dir = make_test_dir("market_report_generator_canonical_name")
    database_url = f"sqlite+pysqlite:///{(test_dir / 'market_report.db').as_posix()}"
    init_test_db(database_url)
    raw_storage = DbFrameStorage(database_url)
    processed_storage = DbFrameStorage(database_url)
    generator = MarketReportGenerator(raw_storage=raw_storage, processed_storage=processed_storage)

    session_factory = build_session_factory(build_engine(database_url))
    SqlAlchemyStockRepository(session_factory).upsert(StockRecord(symbol="000660", symbol_name="SK하이닉스", market="KOSPI"))

    processed_storage.save(
        "daily_prices_indicators",
        "000660_indicators.csv",
        pd.DataFrame(
            [
                {
                    "date": "2026-04-10",
                    "close": 210000,
                    "ma_5": 205000,
                    "ma_20": 200000,
                    "ma_60": 190000,
                    "rsi_14": 58,
                    "volume": 1500,
                    "volume_ma_5": 1200,
                }
            ]
        ),
    )
    processed_storage.save(
        "golden_cross_signals",
        "000660_signals.csv",
        pd.DataFrame([{"date": "2026-04-10", "signal": "buy", "signal_reason": "ma_5 crossed above ma_20."}]),
    )
    raw_storage.save(
        "investor_daily",
        "000660_20260410.csv",
        pd.DataFrame([{"frgn_ntby_qty": "120", "orgn_ntby_qty": "80", "prsn_ntby_qty": "-200"}]),
    )
    raw_storage.save(
        "stock_info",
        "000660.csv",
        pd.DataFrame([{"pdno": "000660", "prdt_abrv_name": "000660", "collection_warning": "fallback"}]),
    )

    request = MarketReportRequest(
        symbol="000660",
        indicator_filename="000660_indicators.csv",
        signal_filename="000660_signals.csv",
        investor_filename="000660_20260410.csv",
    )

    report = generator.generate_report(
        request=request,
        indicator_frame=generator.load_indicator_frame(request),
        signal_frame=generator.load_signal_frame(request),
        investor_frame=generator.load_investor_frame(request),
        stock_info_frame=generator.load_stock_info_frame(request),
    )

    assert report.iloc[0]["symbol_name"] == "SK하이닉스"


def test_market_report_generator_uses_hold_fallback_for_missing_strategy_inputs() -> None:
    test_dir = make_test_dir("market_report_generator_missing_strategy_inputs")
    raw_storage = CsvStorage(test_dir / "raw")
    processed_storage = CsvStorage(test_dir / "processed")
    generator = MarketReportGenerator(raw_storage=raw_storage, processed_storage=processed_storage)

    indicator_frame = pd.DataFrame(
        [
            {
                "date": "2026-04-10",
                "close": 71000,
                "ma_5": 70500,
                "ma_60": 69000,
                "volume": 1500,
                "volume_ma_5": 1200,
            }
        ]
    )
    signal_frame = pd.DataFrame([{"date": "2026-04-10", "signal": "hold", "signal_reason": "n/a"}])
    investor_frame = pd.DataFrame([{"frgn_ntby_qty": "120", "orgn_ntby_qty": "80", "prsn_ntby_qty": "-200"}])
    stock_info_frame = pd.DataFrame([{"pdno": "005930", "prdt_abrv_name": "Samsung Electronics"}])

    report = generator.generate_report(
        request=MarketReportRequest(
            symbol="005930",
            indicator_filename="unused.csv",
            signal_filename="unused.csv",
            investor_filename="unused.csv",
        ),
        indicator_frame=indicator_frame,
        signal_frame=signal_frame,
        investor_frame=investor_frame,
        stock_info_frame=stock_info_frame,
    )

    row = report.iloc[0]
    assert row["rsi_strategy_signal"] == "hold"
    assert row["rsi_strategy_reason"].startswith("Missing indicators: rsi_14")
    assert row["trend_filter_signal"] == "hold"
    assert row["trend_filter_reason"].startswith("Missing indicators: prev_close")
    assert row["mean_reversion_signal"] == "hold"
    assert row["mean_reversion_reason"].startswith("Missing indicators:")
