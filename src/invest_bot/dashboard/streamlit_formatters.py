from __future__ import annotations

import re

import pandas as pd

from invest_bot.dashboard.service import DashboardDataService
from invest_bot.market.symbol_lookup import ResolvedSymbol, SymbolEntry


NUMERIC_COLUMNS = {
    "close",
    "open",
    "high",
    "low",
    "volume",
    "turnover",
    "ma_5",
    "ma_20",
    "ma_60",
    "volume_ma_5",
    "rsi_14",
    "signal_prev_ma_5",
    "signal_prev_ma_20",
    "signal_ma_5",
    "signal_ma_20",
    "foreign_net",
    "institutional_net",
    "personal_net",
    "frgn_ntby_qty",
    "orgn_ntby_qty",
    "prsn_ntby_qty",
    "stck_prpr",
    "prdy_vrss",
    "prdy_ctrt",
    "row_count",
}

STATE_COLUMNS = {
    "signal",
    "golden_cross_signal",
    "final_opinion",
    "trend_state",
    "rsi_state",
    "volume_state",
    "investor_flow",
}

POSITIVE_STATE_VALUES = {"buy", "bullish", "supportive", "active", "strong"}
NEGATIVE_STATE_VALUES = {"sell", "bearish", "weak", "overbought"}
NEUTRAL_STATE_VALUES = {"hold", "watch", "neutral", "normal", "quiet", "oversold", "mixed", "unknown"}


def format_frame_for_display(frame: pd.DataFrame, service: DashboardDataService) -> pd.DataFrame:
    display = frame.copy()
    for column in display.columns:
        display[column] = display[column].map(lambda value: format_display_value(service, column, value))
    return display


def format_display_value(service: DashboardDataService, column: str, value: object) -> object:
    if pd.isna(value):
        return value
    if column == "symbol_name":
        return str(value).strip()
    if column == "symbol":
        return str(value)
    if column in STATE_COLUMNS:
        return state_label(service, str(value))
    if column in {"summary"}:
        return localize_report_summary(service, str(value))
    if column in {
        "signal_reason",
        "golden_cross_reason",
        "rsi_strategy_reason",
        "trend_filter_reason",
        "mean_reversion_reason",
    }:
        return localize_reason(str(value))
    if column in NUMERIC_COLUMNS:
        return format_number(value)
    return value


def state_label(service: DashboardDataService, value: str) -> str:
    return service.STATE_LABELS.get(value, value)


def state_tone(value: str) -> str:
    normalized = str(value).strip().lower()
    if normalized in POSITIVE_STATE_VALUES:
        return "positive"
    if normalized in NEGATIVE_STATE_VALUES:
        return "negative"
    if normalized in NEUTRAL_STATE_VALUES:
        return "neutral"
    return "neutral"


def state_text_color(value: str) -> str:
    tone = state_tone(value)
    if tone == "positive":
        return "#15803d"
    if tone == "negative":
        return "#b91c1c"
    return "#111827"


def format_symbol_display(symbol: str, symbol_name: str) -> str:
    code = str(symbol).strip()
    name = str(symbol_name).strip()
    if name and code:
        return f"{name} ({code})"
    return name or code


def format_symbol_option(entry: SymbolEntry | ResolvedSymbol) -> str:
    return format_symbol_display(entry.symbol, entry.symbol_name)


def default_selected_symbols(available_symbols: list[str], persisted_selection: list[str]) -> list[str]:
    persisted = [symbol for symbol in persisted_selection if symbol in available_symbols]
    if persisted:
        return persisted
    if "005930" in available_symbols:
        return ["005930"]
    return available_symbols[:1]


def default_single_symbol(available_symbols: list[str], persisted_symbol: str) -> str:
    if persisted_symbol in available_symbols:
        return persisted_symbol
    if "005930" in available_symbols:
        return "005930"
    return available_symbols[0] if available_symbols else ""


def localize_reason(reason: str) -> str:
    text = reason.strip()
    if not text:
        return ""
    if match := re.fullmatch(r"(?P<short>[\w_]+)\s+crossed\s+above\s+(?P<long>[\w_]+)\.?", text, flags=re.IGNORECASE):
        return f"{humanize_indicator_name(match.group('short'))}이 {humanize_indicator_name(match.group('long'))}을 상향 돌파했습니다."
    if match := re.fullmatch(r"(?P<short>[\w_]+)\s+crossed\s+below\s+(?P<long>[\w_]+)\.?", text, flags=re.IGNORECASE):
        return f"{humanize_indicator_name(match.group('short'))}이 {humanize_indicator_name(match.group('long'))}을 하향 이탈했습니다."
    if match := re.fullmatch(
        r"(?P<short>[\w_]+)\s+and\s+(?P<long>[\w_]+)\s+did\s+not\s+cross\.?",
        text,
        flags=re.IGNORECASE,
    ):
        return f"{humanize_indicator_name(match.group('short'))}과 {humanize_indicator_name(match.group('long'))}의 교차는 아직 확인되지 않았습니다."

    if match := re.fullmatch(
        r"(?P<indicator>[\w_]+)\s+is\s+(?P<value>-?\d+(?:\.\d+)?),\s+at or below buy threshold\s+(?P<threshold>-?\d+(?:\.\d+)?)\.",
        text,
        flags=re.IGNORECASE,
    ):
        return f"{humanize_indicator_name(match.group('indicator'))}가 {match.group('value')}로 매수 기준 {match.group('threshold')} 이하입니다."
    if match := re.fullmatch(
        r"(?P<indicator>[\w_]+)\s+is\s+(?P<value>-?\d+(?:\.\d+)?),\s+at or above sell threshold\s+(?P<threshold>-?\d+(?:\.\d+)?)\.",
        text,
        flags=re.IGNORECASE,
    ):
        return f"{humanize_indicator_name(match.group('indicator'))}가 {match.group('value')}로 매도 기준 {match.group('threshold')} 이상입니다."
    if match := re.fullmatch(
        r"(?P<indicator>[\w_]+)\s+is\s+(?P<value>-?\d+(?:\.\d+)?),\s+between buy threshold\s+(?P<buy>-?\d+(?:\.\d+)?)\s+and sell threshold\s+(?P<sell>-?\d+(?:\.\d+)?)\.",
        text,
        flags=re.IGNORECASE,
    ):
        return f"{humanize_indicator_name(match.group('indicator'))}가 {match.group('value')}로 매수 기준 {match.group('buy')}과 매도 기준 {match.group('sell')} 사이입니다."
    if match := re.fullmatch(
        r"(?P<close>[\w_]+)\s+is\s+(?P<close_value>-?\d+(?:\.\d+)?),\s+above\s+(?P<baseline>[\w_]+)\s+(?P<baseline_value>-?\d+(?:\.\d+)?)\s+and above\s+(?P<previous>[\w_]+)\s+(?P<previous_value>-?\d+(?:\.\d+)?)\.",
        text,
        flags=re.IGNORECASE,
    ):
        return (
            f"{humanize_indicator_name(match.group('close'))}가 {format_number(match.group('close_value'))}로 "
            f"{humanize_indicator_name(match.group('baseline'))} {format_number(match.group('baseline_value'))}와 "
            f"{humanize_indicator_name(match.group('previous'))} {format_number(match.group('previous_value'))}보다 높습니다."
        )
    if match := re.fullmatch(
        r"(?P<close>[\w_]+)\s+is\s+(?P<close_value>-?\d+(?:\.\d+)?),\s+below\s+(?P<baseline>[\w_]+)\s+(?P<baseline_value>-?\d+(?:\.\d+)?)\s+and below\s+(?P<previous>[\w_]+)\s+(?P<previous_value>-?\d+(?:\.\d+)?)\.",
        text,
        flags=re.IGNORECASE,
    ):
        return (
            f"{humanize_indicator_name(match.group('close'))}가 {format_number(match.group('close_value'))}로 "
            f"{humanize_indicator_name(match.group('baseline'))} {format_number(match.group('baseline_value'))}와 "
            f"{humanize_indicator_name(match.group('previous'))} {format_number(match.group('previous_value'))}보다 낮습니다."
        )
    if match := re.fullmatch(
        r"(?P<close>[\w_]+)\s+is\s+(?P<close_value>-?\d+(?:\.\d+)?),\s+showing a mixed signal versus\s+(?P<baseline>[\w_]+)\s+(?P<baseline_value>-?\d+(?:\.\d+)?)\s+and\s+(?P<previous>[\w_]+)\s+(?P<previous_value>-?\d+(?:\.\d+)?)\.",
        text,
        flags=re.IGNORECASE,
    ):
        return (
            f"{humanize_indicator_name(match.group('close'))}가 {format_number(match.group('close_value'))}로 "
            f"{humanize_indicator_name(match.group('baseline'))} {format_number(match.group('baseline_value'))} 및 "
            f"{humanize_indicator_name(match.group('previous'))} {format_number(match.group('previous_value'))} 대비 혼조 신호입니다."
        )
    if match := re.fullmatch(
        r"(?P<close>[\w_]+)\s+is\s+(?P<close_value>-?\d+(?:\.\d+)?),\s+at\s+(?P<ratio>-?\d+(?:\.\d+)?)\s+of\s+(?P<baseline>[\w_]+)\s+(?P<baseline_value>-?\d+(?:\.\d+)?),\s+at or below buy ratio\s+(?P<threshold>-?\d+(?:\.\d+)?)\.",
        text,
        flags=re.IGNORECASE,
    ):
        return (
            f"{humanize_indicator_name(match.group('close'))}가 {format_number(match.group('close_value'))}로 "
            f"{humanize_indicator_name(match.group('baseline'))} {format_number(match.group('baseline_value'))} 대비 {match.group('ratio')}배이며, "
            f"매수 비율 기준 {match.group('threshold')} 이하입니다."
        )
    if match := re.fullmatch(
        r"(?P<close>[\w_]+)\s+is\s+(?P<close_value>-?\d+(?:\.\d+)?),\s+at\s+(?P<ratio>-?\d+(?:\.\d+)?)\s+of\s+(?P<baseline>[\w_]+)\s+(?P<baseline_value>-?\d+(?:\.\d+)?),\s+at or above sell ratio\s+(?P<threshold>-?\d+(?:\.\d+)?)\.",
        text,
        flags=re.IGNORECASE,
    ):
        return (
            f"{humanize_indicator_name(match.group('close'))}가 {format_number(match.group('close_value'))}로 "
            f"{humanize_indicator_name(match.group('baseline'))} {format_number(match.group('baseline_value'))} 대비 {match.group('ratio')}배이며, "
            f"매도 비율 기준 {match.group('threshold')} 이상입니다."
        )
    if match := re.fullmatch(
        r"(?P<close>[\w_]+)\s+is\s+(?P<close_value>-?\d+(?:\.\d+)?),\s+at\s+(?P<ratio>-?\d+(?:\.\d+)?)\s+of\s+(?P<baseline>[\w_]+)\s+(?P<baseline_value>-?\d+(?:\.\d+)?),\s+inside the mean-reversion band\.",
        text,
        flags=re.IGNORECASE,
    ):
        return (
            f"{humanize_indicator_name(match.group('close'))}가 {format_number(match.group('close_value'))}로 "
            f"{humanize_indicator_name(match.group('baseline'))} {format_number(match.group('baseline_value'))} 대비 {match.group('ratio')}배이며, "
            "평균회귀 기준 범위 안에 있습니다."
        )
    replacements = {
        "Not enough data to detect a crossover.": "교차 여부를 판단할 데이터가 아직 충분하지 않습니다.",
        "At least two rows are required to detect a crossover.": "교차 여부를 판단하려면 최소 두 시점의 데이터가 필요합니다.",
    }
    if text in replacements:
        return replacements[text]
    if text.startswith("Missing indicators:"):
        missing = text.removeprefix("Missing indicators:").strip()
        return f"판단에 필요한 지표가 부족합니다: {missing}"
    return text


def localize_report_summary(service: DashboardDataService, summary: str) -> str:
    text = summary.strip()
    if not text:
        return ""
    pattern = re.compile(
        r"Trend is (?P<trend>[^,]+),\s*golden cross signal is (?P<signal>[^,]+),\s*RSI state is (?P<rsi>[^,]+),\s*volume is (?P<volume>[^,]+),\s*and investor flow is (?P<flow>[^.]+)\.?",
        flags=re.IGNORECASE,
    )
    if match := pattern.fullmatch(text):
        return compose_localized_report_summary(
            service,
            trend_state=match.group("trend").strip(),
            signal=match.group("signal").strip(),
            rsi_state=match.group("rsi").strip(),
            volume_state=match.group("volume").strip(),
            investor_flow=match.group("flow").strip(),
        )
    return text


def localize_report_summary_from_row(service: DashboardDataService, row: pd.Series) -> str:
    summary = str(row.get("summary", "")).strip()
    trend_state = str(row.get("trend_state", "")).strip()
    signal = str(row.get("golden_cross_signal", "")).strip()
    rsi_state = str(row.get("rsi_state", "")).strip()
    volume_state = str(row.get("volume_state", "")).strip()
    investor_flow = str(row.get("investor_flow", "")).strip()
    if all((trend_state, signal, rsi_state, volume_state, investor_flow)):
        return compose_localized_report_summary(
            service,
            trend_state=trend_state,
            signal=signal,
            rsi_state=rsi_state,
            volume_state=volume_state,
            investor_flow=investor_flow,
        )
    return localize_report_summary(service, summary)


def compose_localized_report_summary(
    service: DashboardDataService,
    *,
    trend_state: str,
    signal: str,
    rsi_state: str,
    volume_state: str,
    investor_flow: str,
) -> str:
    return (
        f"추세는 {state_label(service, trend_state)}이고, 골든크로스 신호는 {state_label(service, signal)}이며, "
        f"RSI 상태는 {state_label(service, rsi_state)}, 거래량은 {state_label(service, volume_state)}, "
        f"수급은 {state_label(service, investor_flow)}입니다."
    )


def humanize_indicator_name(value: str) -> str:
    mapping = {
        "ma_5": "5일 이동평균선",
        "ma_20": "20일 이동평균선",
        "ma_60": "60일 이동평균선",
        "close": "종가",
        "prev_close": "직전 종가",
        "rsi_14": "RSI 14",
    }
    return mapping.get(value.strip().lower(), value.strip())


def format_number(value: object) -> str:
    if value is None or pd.isna(value):
        return "-"
    number = float(value)
    if number.is_integer():
        return f"{int(number):,}"
    return f"{number:,.2f}"


def compact_datetime(value: str) -> str:
    if not value:
        return "-"
    try:
        parsed = pd.to_datetime(value)
    except Exception:  # noqa: BLE001
        return value
    if pd.isna(parsed):
        return value
    return parsed.strftime("%Y-%m-%d %H:%M")
