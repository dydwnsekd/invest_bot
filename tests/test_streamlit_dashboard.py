from __future__ import annotations

import pandas as pd
import pytest

from invest_bot.dashboard.service import DashboardDataService
from invest_bot.dashboard.streamlit_actions import require_selected_items, require_single_selected_item
from invest_bot.dashboard.streamlit_formatters import (
    default_selected_symbols as _default_selected_symbols,
    default_single_symbol as _default_single_symbol,
    format_display_value as _format_display_value,
    format_symbol_display as _format_symbol_display,
    format_symbol_option as _format_symbol_option,
    localize_reason as _localize_reason,
    localize_report_summary as _localize_report_summary,
    localize_report_summary_from_row as _localize_report_summary_from_row,
)
from invest_bot.dashboard.streamlit_reports import filter_report_entries, sort_report_entries
from invest_bot.market.symbol_lookup import ResolvedSymbol, SymbolEntry


def test_format_symbol_display_prefers_name_and_code() -> None:
    assert _format_symbol_display("005930", "삼성전자") == "삼성전자 (005930)"
    assert _format_symbol_display("005930", "") == "005930"
    assert _format_symbol_display("", "삼성전자") == "삼성전자"


def test_format_symbol_option_uses_name_and_code() -> None:
    assert _format_symbol_option(SymbolEntry(symbol="005930", symbol_name="삼성전자")) == "삼성전자 (005930)"


def test_default_selected_symbols_prefers_persisted_then_fallback() -> None:
    assert _default_selected_symbols(["005930", "000660"], ["000660"]) == ["000660"]
    assert _default_selected_symbols(["005930", "000660"], ["035420"]) == ["005930"]
    assert _default_selected_symbols(["000660"], []) == ["000660"]


def test_default_single_symbol_prefers_persisted_then_fallback() -> None:
    assert _default_single_symbol(["005930", "000660"], "000660") == "000660"
    assert _default_single_symbol(["005930", "000660"], "035420") == "005930"
    assert _default_single_symbol(["000660"], "") == "000660"


def test_selection_guards_raise_clear_messages() -> None:
    selected = ResolvedSymbol(raw_input="005930", symbol="005930", symbol_name="삼성전자")

    assert require_selected_items([selected]) == [selected]
    assert require_single_selected_item(selected) == selected

    with pytest.raises(ValueError, match="자동완성 목록에서 종목을 하나 이상 선택해 주세요."):
        require_selected_items([])

    with pytest.raises(ValueError, match="단일 작업을 실행하려면 대상 종목을 하나 선택해 주세요."):
        require_single_selected_item(None)


def test_localize_reason_translates_known_english_patterns() -> None:
    assert _localize_reason("ma_5 crossed above ma_20.") == "5일 이동평균선이 20일 이동평균선을 상향 돌파했습니다."
    assert _localize_reason("ma_5 crossed below ma_20.") == "5일 이동평균선이 20일 이동평균선을 하향 이탈했습니다."
    assert _localize_reason("Missing indicators: ma_5, ma_20") == "판단에 필요한 지표가 부족합니다: ma_5, ma_20"
    assert _localize_reason("ma_5 and ma_20 did not cross.") == "5일 이동평균선과 20일 이동평균선의 교차는 아직 확인되지 않았습니다."


def test_localize_report_summary_translates_generated_market_report_summary() -> None:
    service = DashboardDataService()

    localized = _localize_report_summary(
        service,
        "Trend is bullish, golden cross signal is buy, RSI state is strong, volume is active, and investor flow is supportive.",
    )

    assert localized == "추세는 상승 우세이고, 골든크로스 신호는 매수 관점이며, RSI 상태는 강한 흐름, 거래량은 거래 활발, 수급은 수급 우호적입니다."


def test_localize_report_summary_from_row_prefers_states_over_raw_summary_text() -> None:
    service = DashboardDataService()
    row = pd.Series(
        {
            "summary": "Unexpected wording that should not leak to the UI.",
            "trend_state": "bullish",
            "golden_cross_signal": "buy",
            "rsi_state": "strong",
            "volume_state": "active",
            "investor_flow": "supportive",
        }
    )

    localized = _localize_report_summary_from_row(service, row)

    assert localized == "추세는 상승 우세이고, 골든크로스 신호는 매수 관점이며, RSI 상태는 강한 흐름, 거래량은 거래 활발, 수급은 수급 우호적입니다."


def test_format_display_value_formats_state_text_and_numbers() -> None:
    service = DashboardDataService()

    assert _format_display_value(service, "final_opinion", "buy") == "매수 관점"
    assert _format_display_value(service, "close", 100000) == "100,000"
    assert _format_display_value(service, "summary", "Trend is bullish, golden cross signal is buy, RSI state is strong, volume is active, and investor flow is supportive.") == (
        "추세는 상승 우세이고, 골든크로스 신호는 매수 관점이며, RSI 상태는 강한 흐름, 거래량은 거래 활발, 수급은 수급 우호적입니다."
    )


def test_report_filter_and_sort_behaviour_is_preserved() -> None:
    entries = [
        {
            "symbol": "005930",
            "symbol_name": "삼성전자",
            "date": "2026-06-10",
            "final_opinion": "buy",
            "display_opinion": "매수 관점",
            "display_trend": "상승 우세",
            "display_signal": "매수 관점",
        },
        {
            "symbol": "000660",
            "symbol_name": "SK하이닉스",
            "date": "2026-06-09",
            "final_opinion": "hold",
            "display_opinion": "관망",
            "display_trend": "중립",
            "display_signal": "관망",
        },
    ]

    filtered = filter_report_entries(entries, query="삼성", opinion_filter="전체", trend_filter="전체", signal_filter="전체")
    assert [entry["symbol"] for entry in filtered] == ["005930"]

    sorted_entries = sort_report_entries(entries, "매수 관점 우선")
    assert [entry["symbol"] for entry in sorted_entries] == ["005930", "000660"]
