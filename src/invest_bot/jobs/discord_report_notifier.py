from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Mapping

import pandas as pd
import requests

from invest_bot.config.settings import AppSettings


STATE_LABELS = {
    "buy": "매수 관점",
    "sell": "매도 관점",
    "hold": "관망",
    "watch": "관심 관찰",
    "bullish": "상승 우세",
    "bearish": "하락 우세",
    "neutral": "중립",
    "unknown": "정보 부족",
    "overbought": "과열 가능성",
    "oversold": "과매도 가능성",
    "strong": "강한 흐름",
    "weak": "약한 흐름",
    "active": "거래 활발",
    "normal": "거래 보통",
    "quiet": "거래 한산",
    "supportive": "수급 우호적",
    "mixed": "수급 혼조",
}


@dataclass(slots=True)
class DiscordDeliveryResult:
    status: Literal["sent", "skipped", "failed"]
    channel: Literal["discord"] = "discord"
    message: str = ""
    error_detail: str = ""


def send_discord_report(
    report_row: Mapping[str, object] | pd.Series,
    *,
    settings: AppSettings | None = None,
    webhook_url: str | None = None,
    session: requests.Session | object | None = None,
    timeout: int = 10,
) -> DiscordDeliveryResult:
    message = build_discord_report_message(report_row)
    resolved_webhook_url = (webhook_url or (settings.discord_webhook_url if settings is not None else "")).strip()
    if not resolved_webhook_url:
        return DiscordDeliveryResult(
            status="skipped",
            message=message,
            error_detail="Discord webhook URL is not configured.",
        )

    request_session = session or requests.Session()
    try:
        response = request_session.post(
            resolved_webhook_url,
            json={"content": message},
            headers={"Content-Type": "application/json"},
            timeout=timeout,
        )
        response.raise_for_status()
    except requests.RequestException as error:
        return DiscordDeliveryResult(
            status="failed",
            message=message,
            error_detail=str(error),
        )

    return DiscordDeliveryResult(status="sent", message=message)


def build_discord_report_message(report_row: Mapping[str, object] | pd.Series) -> str:
    row = _normalize_row(report_row)
    symbol = _text(row.get("symbol"))
    symbol_name = _text(row.get("symbol_name"))
    date = _text(row.get("date"))
    symbol_label = f"{symbol_name} ({symbol})" if symbol_name and symbol else symbol_name or symbol or "-"

    lines = [
        "시장 리포트 생성 완료",
        f"종목: {symbol_label}",
        f"기준일: {date or '-'}",
        f"최종 의견: {_state_label(row.get('final_opinion'))}",
        f"요약: {_text(row.get('summary')) or '-'}",
        (
            "전략 신호: "
            f"골든크로스 {_state_label(row.get('golden_cross_signal'))}, "
            f"RSI {_state_label(row.get('rsi_strategy_signal'))}, "
            f"추세 필터 {_state_label(row.get('trend_filter_signal'))}, "
            f"평균회귀 {_state_label(row.get('mean_reversion_signal'))}"
        ),
        (
            "전략 근거: "
            f"골든크로스={_text(row.get('golden_cross_reason')) or '-'} / "
            f"RSI={_text(row.get('rsi_strategy_reason')) or '-'} / "
            f"추세 필터={_text(row.get('trend_filter_reason')) or '-'} / "
            f"평균회귀={_text(row.get('mean_reversion_reason')) or '-'}"
        ),
        (
            "핵심 지표: "
            f"종가 {_number(row.get('close'))}, "
            f"5일선 {_number(row.get('ma_5'))}, "
            f"20일선 {_number(row.get('ma_20'))}, "
            f"60일선 {_number(row.get('ma_60'))}, "
            f"RSI14 {_number(row.get('rsi_14'), digits=2)}, "
            f"거래량 {_number(row.get('volume'))}, "
            f"5일 평균 거래량 {_number(row.get('volume_ma_5'))}"
        ),
        (
            "투자자 수급: "
            f"{_state_label(row.get('investor_flow'))} "
            f"(외국인 {_signed_number(row.get('foreign_net'))}, "
            f"기관 {_signed_number(row.get('institutional_net'))}, "
            f"개인 {_signed_number(row.get('personal_net'))})"
        ),
    ]
    return "\n".join(lines)


def _normalize_row(report_row: Mapping[str, object] | pd.Series) -> Mapping[str, object]:
    if isinstance(report_row, pd.Series):
        return report_row.to_dict()
    return report_row


def _state_label(value: object) -> str:
    raw = _text(value).strip().lower()
    return STATE_LABELS.get(raw, raw or "-")


def _text(value: object) -> str:
    if value is None or pd.isna(value):
        return ""
    if isinstance(value, pd.Timestamp):
        return value.strftime("%Y-%m-%d")
    return str(value).strip()


def _number(value: object, *, digits: int = 0) -> str:
    if value is None or pd.isna(value):
        return "-"
    number = float(value)
    if digits == 0 and number.is_integer():
        return f"{int(number):,}"
    return f"{number:,.{digits}f}"


def _signed_number(value: object) -> str:
    if value is None or pd.isna(value):
        return "-"
    number = float(value)
    if number.is_integer():
        rendered = f"{int(abs(number)):,}"
    else:
        rendered = f"{abs(number):,.2f}"
    sign = "+" if number > 0 else "-" if number < 0 else "±"
    return f"{sign}{rendered}"
