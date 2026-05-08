from __future__ import annotations

import pandas as pd

from invest_bot.jobs.generate_market_report import MarketReportGenerator, MarketReportRequest
from invest_bot.market.storage import CsvStorage
from tests.helpers import make_test_dir


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
    assert report.iloc[0]["trend_state"] == "bullish"
    assert report.iloc[0]["rsi_state"] == "strong"
    assert report.iloc[0]["volume_state"] == "active"
    assert report.iloc[0]["investor_flow"] == "supportive"
    assert report.iloc[0]["final_opinion"] == "buy"
