from __future__ import annotations

import pandas as pd
import requests

from invest_bot.config.settings import AppSettings
from invest_bot.jobs.discord_report_notifier import (
    DiscordDeliveryResult,
    build_discord_report_message,
    send_discord_report,
)


def test_build_discord_report_message_includes_required_summary_fields() -> None:
    message = build_discord_report_message(_sample_report_row())

    assert "시장 리포트 생성 완료" in message
    assert "종목: 삼성전자 (005930)" in message
    assert "최종 의견: 매수 관점" in message
    assert "요약: 추세는 상승 우세이며 골든크로스 매수 신호가 확인됩니다." in message
    assert "전략 신호: 골든크로스 매수 관점, RSI 관망, 추세 필터 매수 관점, 평균회귀 관망" in message
    assert "전략 근거:" in message
    assert "핵심 지표: 종가 71,000" in message
    assert "5일선 70,500" in message
    assert "RSI14 58.00" in message
    assert "투자자 수급: 수급 우호적 (외국인 +120, 기관 +80, 개인 -200)" in message


def test_send_discord_report_skips_when_webhook_is_missing() -> None:
    result = send_discord_report(_sample_report_row(), settings=AppSettings(discord_webhook_url=""))

    assert result == DiscordDeliveryResult(
        status="skipped",
        channel="discord",
        message=result.message,
        error_detail="Discord webhook URL is not configured.",
    )
    assert "최종 의견: 매수 관점" in result.message


def test_send_discord_report_posts_plain_text_payload_and_returns_sent() -> None:
    session = _RecordingSession()

    result = send_discord_report(
        _sample_report_row(),
        settings=AppSettings(discord_webhook_url="https://discord.example/webhook"),
        session=session,
    )

    assert result.status == "sent"
    assert result.channel == "discord"
    assert result.error_detail == ""
    assert session.calls == [
        {
            "url": "https://discord.example/webhook",
            "json": {"content": result.message},
            "headers": {"Content-Type": "application/json"},
            "timeout": 10,
        }
    ]


def test_send_discord_report_returns_failed_when_transport_raises() -> None:
    session = _FailingSession(requests.HTTPError("500 Server Error"))

    result = send_discord_report(
        _sample_report_row(),
        webhook_url="https://discord.example/webhook",
        session=session,
    )

    assert result.status == "failed"
    assert result.channel == "discord"
    assert result.error_detail == "500 Server Error"
    assert "전략 신호:" in result.message


def _sample_report_row() -> pd.Series:
    return pd.Series(
        {
            "symbol": "005930",
            "symbol_name": "삼성전자",
            "date": "2026-04-10",
            "close": 71000,
            "ma_5": 70500,
            "ma_20": 70000,
            "ma_60": 69000,
            "rsi_14": 58,
            "volume": 1500,
            "volume_ma_5": 1200,
            "golden_cross_signal": "buy",
            "golden_cross_reason": "ma_5 crossed above ma_20.",
            "rsi_strategy_signal": "hold",
            "rsi_strategy_reason": "rsi_14 is 58.00, between buy threshold 30.00 and sell threshold 70.00.",
            "trend_filter_signal": "buy",
            "trend_filter_reason": "close is 71000.00, above ma_60 69000.00 and above prev_close 70500.00.",
            "mean_reversion_signal": "hold",
            "mean_reversion_reason": "close is 71000.00, inside the mean-reversion band.",
            "investor_flow": "supportive",
            "foreign_net": 120,
            "institutional_net": 80,
            "personal_net": -200,
            "summary": "추세는 상승 우세이며 골든크로스 매수 신호가 확인됩니다.",
            "final_opinion": "buy",
        }
    )


class _RecordingResponse:
    def raise_for_status(self) -> None:
        return None


class _RecordingSession:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def post(self, url: str, *, json: dict[str, object], headers: dict[str, str], timeout: int) -> _RecordingResponse:
        self.calls.append(
            {
                "url": url,
                "json": json,
                "headers": headers,
                "timeout": timeout,
            }
        )
        return _RecordingResponse()


class _FailingSession:
    def __init__(self, error: requests.RequestException) -> None:
        self.error = error

    def post(self, url: str, *, json: dict[str, object], headers: dict[str, str], timeout: int) -> _RecordingResponse:
        raise self.error
