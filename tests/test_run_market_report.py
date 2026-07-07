from __future__ import annotations

from pathlib import Path

import pandas as pd

from invest_bot.config.settings import AppSettings
from invest_bot.jobs.discord_report_notifier import DiscordDeliveryResult
from invest_bot.jobs.generate_market_report import MarketReportGenerator
from invest_bot.jobs.run_market_report import generate_market_report_for_symbol
from invest_bot.market.storage import CsvStorage
from tests.helpers import make_test_dir


def test_generate_market_report_for_symbol_keeps_manual_default_path_without_delivery() -> None:
    generator = _make_generator("market_report_run_default")
    captured_rows: list[dict[str, object]] = []

    result = generate_market_report_for_symbol(
        "005930",
        generator=generator,
        notifier=lambda row: captured_rows.append(row) or DiscordDeliveryResult(status="sent", message="unexpected"),
    )

    assert result["symbol"] == "005930"
    assert result["rows"] == 1
    assert result["delivery"] is None
    assert captured_rows == []
    assert Path(str(result["saved_path"])).exists()


def test_generate_market_report_for_symbol_sends_report_row_when_discord_delivery_is_enabled() -> None:
    generator = _make_generator("market_report_run_discord")
    captured_rows: list[dict[str, object]] = []

    result = generate_market_report_for_symbol(
        "005930",
        generator=generator,
        delivery_target="discord",
        notifier=lambda row: captured_rows.append(row) or DiscordDeliveryResult(status="sent", message="sent ok"),
    )

    assert len(captured_rows) == 1
    assert captured_rows[0]["symbol"] == "005930"
    assert captured_rows[0]["final_opinion"] == "buy"
    assert result["delivery"] == {
        "status": "sent",
        "channel": "discord",
        "message": "sent ok",
        "error_detail": "",
    }


def test_generate_market_report_for_symbol_returns_skipped_delivery_when_webhook_is_missing() -> None:
    generator = _make_generator("market_report_run_skipped")

    result = generate_market_report_for_symbol(
        "005930",
        generator=generator,
        delivery_target="discord",
        settings=AppSettings(discord_webhook_url=""),
    )

    assert result["rows"] == 1
    assert result["delivery"] == {
        "status": "skipped",
        "channel": "discord",
        "message": result["delivery"]["message"],
        "error_detail": "Discord webhook URL is not configured.",
    }


def test_generate_market_report_for_symbol_preserves_saved_report_when_delivery_fails() -> None:
    generator = _make_generator("market_report_run_failed")

    result = generate_market_report_for_symbol(
        "005930",
        generator=generator,
        delivery_target="discord",
        notifier=lambda row: DiscordDeliveryResult(status="failed", message="warn", error_detail="HTTP 500"),
    )

    assert Path(str(result["saved_path"])).exists()
    assert result["rows"] == 1
    assert result["delivery"] == {
        "status": "failed",
        "channel": "discord",
        "message": "warn",
        "error_detail": "HTTP 500",
    }


def _make_generator(name: str) -> MarketReportGenerator:
    test_dir = make_test_dir(name)
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
        pd.DataFrame([{"pdno": "005930", "prdt_abrv_name": "삼성전자"}]),
    )
    return generator
