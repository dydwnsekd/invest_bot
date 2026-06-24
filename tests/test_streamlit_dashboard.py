from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import pytest

from invest_bot.dashboard.service import DashboardDataService, DatasetPreview
from invest_bot.dashboard.streamlit_charts import available_chart_presets, default_chart_preset, prepare_time_series_frame
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
import invest_bot.dashboard.streamlit_reports as streamlit_reports_module
from invest_bot.dashboard.streamlit_reports import (
    filter_report_entries,
    format_report_selection_option,
    get_report_entry_by_key,
    query_report_entries,
    query_report_previews,
    resolve_selected_report_entry,
    resolve_selected_report_key,
    selected_entry_index,
    selected_entry_key_index,
    sort_report_entries,
)
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


def test_prepare_time_series_frame_normalizes_supported_date_columns() -> None:
    frame = pd.DataFrame(
        [
            {"stck_bsop_date": "20260328", "frgn_ntby_qty": 100},
            {"stck_bsop_date": "20260329", "frgn_ntby_qty": 150},
        ]
    )

    normalized = prepare_time_series_frame(frame)

    assert list(normalized.columns) == ["stck_bsop_date", "frgn_ntby_qty", "date"]
    assert normalized["date"].dt.strftime("%Y-%m-%d").tolist() == ["2026-03-28", "2026-03-29"]


def test_available_chart_presets_detects_stock_price_charts() -> None:
    frame = pd.DataFrame(
        [
            {
                "date": "2026-03-28",
                "open": 70000,
                "high": 71000,
                "low": 69500,
                "close": 70800,
                "volume": 1000000,
                "ma_5": 70200,
                "ma_20": 69000,
                "rsi_14": 61.5,
            }
        ]
    )

    presets = available_chart_presets("daily_prices_indicators", frame)

    assert [preset.key for preset in presets] == ["close_ma", "candlestick", "volume", "rsi", "close_only"]
    assert default_chart_preset("daily_prices_indicators", presets) == "close_ma"


def test_available_chart_presets_detects_investor_flow_chart() -> None:
    frame = pd.DataFrame(
        [
            {"stck_bsop_date": "20260328", "frgn_ntby_qty": 100, "orgn_ntby_qty": -50, "prsn_ntby_qty": 20},
            {"stck_bsop_date": "20260329", "frgn_ntby_qty": 120, "orgn_ntby_qty": -30, "prsn_ntby_qty": 10},
        ]
    )

    presets = available_chart_presets("investor_daily", frame)

    assert [preset.key for preset in presets] == ["flow"]
    assert default_chart_preset("investor_daily", presets) == "flow"


def test_query_report_entries_filters_by_symbol_or_name() -> None:
    entries = [
        {"entry_key": "005930:a.csv", "symbol": "005930", "symbol_name": "삼성전자"},
        {"entry_key": "000660:b.csv", "symbol": "000660", "symbol_name": "SK하이닉스"},
    ]

    filtered = query_report_entries(entries, "삼성")
    assert [entry["entry_key"] for entry in filtered] == ["005930:a.csv"]
    assert query_report_entries(entries, "없는종목") == []
    assert query_report_entries(entries, "") == entries


def test_resolve_selected_report_entry_prefers_valid_selection_then_falls_back() -> None:
    entries = [
        {"entry_key": "005930:a.csv", "symbol": "005930", "symbol_name": "삼성전자"},
        {"entry_key": "000660:b.csv", "symbol": "000660", "symbol_name": "SK하이닉스"},
    ]

    assert resolve_selected_report_entry(entries, "000660:b.csv") == entries[1]
    assert resolve_selected_report_entry(entries, "missing") == entries[0]
    assert resolve_selected_report_entry([], "missing") is None


def test_selected_entry_index_matches_resolved_entry() -> None:
    entries = [
        {"entry_key": "005930:a.csv", "symbol": "005930", "symbol_name": "삼성전자"},
        {"entry_key": "000660:b.csv", "symbol": "000660", "symbol_name": "SK하이닉스"},
    ]

    selected = resolve_selected_report_entry(entries, "000660:b.csv")
    assert selected_entry_index(entries, selected) == 1
    assert selected_entry_index(entries, None) == 0


def test_format_report_selection_option_includes_name_symbol_opinion_and_date() -> None:
    entries = [
        {
            "entry_key": "005930:a.csv",
            "symbol": "005930",
            "symbol_name": "삼성전자",
            "display_opinion": "매수 관점",
            "date": "2026-06-24",
        }
    ]

    assert format_report_selection_option(entries, "005930:a.csv") == "삼성전자 (005930) · 매수 관점 · 2026-06-24"
    assert format_report_selection_option(entries, "missing") == "missing"


class _FakeMetricColumn:
    def metric(self, *args, **kwargs) -> None:
        return None


class _FakeContext:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None


class _FakeStreamlit:
    def __init__(self, *, query: str = "", selected_value: str | None = None):
        self.query = query
        self.selected_value = selected_value
        self.session_state: dict[str, object] = {}
        self.warning_messages: list[str] = []
        self.info_messages: list[str] = []

    def markdown(self, *args, **kwargs) -> None:
        return None

    def text_input(self, *args, **kwargs) -> str:
        return self.query

    def columns(self, spec, **kwargs):
        count = spec if isinstance(spec, int) else len(spec)
        return [_FakeMetricColumn() for _ in range(count)]

    def warning(self, message: str) -> None:
        self.warning_messages.append(message)

    def info(self, message: str) -> None:
        self.info_messages.append(message)

    def selectbox(self, label: str, options: list[str], index: int = 0, format_func=None, key: str | None = None):
        value = self.selected_value if self.selected_value in options else options[index]
        if key is not None:
            self.session_state[key] = value
        return value

    def caption(self, *args, **kwargs) -> None:
        return None

    def container(self, **kwargs):
        return _FakeContext()

    def toggle(self, *args, **kwargs) -> bool:
        return False

    def dataframe(self, *args, **kwargs) -> None:
        return None


def _make_report_preview(symbol: str, symbol_name: str, filename: str) -> DatasetPreview:
    return DatasetPreview(
        name="market_reports",
        display_name="시장 상황 요약 리포트",
        path=Path(filename),
        row_count=1,
        columns=["date", "symbol_name", "final_opinion", "summary", "trend_state", "golden_cross_signal", "rsi_state", "investor_flow"],
        summary="summary",
        purpose="purpose",
        first_look="first_look",
        symbol=symbol,
        symbol_name=symbol_name,
        recommended_columns=["date", "symbol_name", "final_opinion"],
    )


def test_render_reports_tab_renders_only_one_selected_report(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_st = _FakeStreamlit()
    monkeypatch.setattr(streamlit_reports_module, "st", fake_st)

    captured: list[str] = []

    def fake_render_market_report_card(preview, service, **kwargs) -> None:
        captured.append(preview.symbol)

    monkeypatch.setattr(streamlit_reports_module, "render_market_report_card", fake_render_market_report_card)

    previews = [
        _make_report_preview("005930", "삼성전자", "005930_20260624.csv"),
        _make_report_preview("000660", "SK하이닉스", "000660_20260624.csv"),
    ]
    frames = {
        "005930": pd.DataFrame([{"date": "2026-06-24", "symbol_name": "삼성전자", "final_opinion": "buy", "summary": "a", "trend_state": "bullish", "golden_cross_signal": "buy", "rsi_state": "strong", "investor_flow": "supportive"}]),
        "000660": pd.DataFrame([{"date": "2026-06-24", "symbol_name": "SK하이닉스", "final_opinion": "hold", "summary": "b", "trend_state": "neutral", "golden_cross_signal": "hold", "rsi_state": "neutral", "investor_flow": "mixed"}]),
    }
    snapshot = SimpleNamespace(processed_previews=previews)

    streamlit_reports_module.render_reports_tab(
        snapshot,
        DashboardDataService(),
        read_preview_frame=lambda preview: frames[preview.symbol],
        load_indicator_frame_for_symbol=lambda symbol: frames[symbol],
    )

    assert captured == ["005930"]


def test_render_reports_tab_shows_warning_and_skips_body_when_query_has_no_match(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_st = _FakeStreamlit(query="없는종목")
    monkeypatch.setattr(streamlit_reports_module, "st", fake_st)

    captured: list[str] = []

    def fake_render_market_report_card(preview, service, **kwargs) -> None:
        captured.append(preview.symbol)

    monkeypatch.setattr(streamlit_reports_module, "render_market_report_card", fake_render_market_report_card)

    previews = [_make_report_preview("005930", "삼성전자", "005930_20260624.csv")]
    frames = {
        "005930": pd.DataFrame([{"date": "2026-06-24", "symbol_name": "삼성전자", "final_opinion": "buy", "summary": "a", "trend_state": "bullish", "golden_cross_signal": "buy", "rsi_state": "strong", "investor_flow": "supportive"}]),
    }
    snapshot = SimpleNamespace(processed_previews=previews)

    streamlit_reports_module.render_reports_tab(
        snapshot,
        DashboardDataService(),
        read_preview_frame=lambda preview: frames[preview.symbol],
        load_indicator_frame_for_symbol=lambda symbol: frames[symbol],
    )

    assert captured == []
    assert fake_st.warning_messages == ["현재 검색 조건에 맞는 리포트가 없습니다."]


def test_render_market_report_card_keeps_chart_for_selected_symbol(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_st = _FakeStreamlit()
    monkeypatch.setattr(streamlit_reports_module, "st", fake_st)

    chart_calls: list[tuple[str, str]] = []

    def fake_render_chart_selector(frame, dataset_name: str, key_prefix: str, height: int) -> None:
        chart_calls.append((dataset_name, key_prefix))

    monkeypatch.setattr(streamlit_reports_module, "render_chart_selector", fake_render_chart_selector)

    preview = _make_report_preview("005930", "삼성전자", "005930_20260624.csv")
    frame = pd.DataFrame([{
        "date": "2026-06-24",
        "symbol_name": "삼성전자",
        "final_opinion": "buy",
        "summary": "a",
        "trend_state": "bullish",
        "golden_cross_signal": "buy",
        "rsi_state": "strong",
        "investor_flow": "supportive",
        "close": 100,
        "ma_5": 90,
        "ma_20": 80,
        "rsi_14": 60,
        "golden_cross_reason": "ma_5 crossed above ma_20.",
    }])
    loaded_symbols: list[str] = []

    def fake_load_indicator(symbol: str):
        loaded_symbols.append(symbol)
        return pd.DataFrame([{"date": "2026-06-24", "close": 100, "ma_5": 90, "ma_20": 80, "rsi_14": 60}])

    streamlit_reports_module.render_market_report_card(
        preview,
        DashboardDataService(),
        frame=frame,
        read_preview_frame=lambda _: frame,
        load_indicator_frame_for_symbol=fake_load_indicator,
    )

    assert loaded_symbols == ["005930"]
    assert chart_calls == [("daily_prices_indicators", "report_005930_005930_20260624.csv")]


def test_query_report_previews_filters_before_frame_loading() -> None:
    previews = [
        _make_report_preview("005930", "삼성전자", "005930_20260624.csv"),
        _make_report_preview("000660", "SK하이닉스", "000660_20260624.csv"),
    ]

    filtered = query_report_previews(previews, "삼성")
    assert [preview.symbol for preview in filtered] == ["005930"]
    assert query_report_previews(previews, "없는종목") == []


def test_resolve_selected_report_key_prefers_valid_key_then_falls_back() -> None:
    entries = [
        {"entry_key": "005930:a.csv", "symbol": "005930", "symbol_name": "삼성전자"},
        {"entry_key": "000660:b.csv", "symbol": "000660", "symbol_name": "SK하이닉스"},
    ]

    assert resolve_selected_report_key(entries, "000660:b.csv") == "000660:b.csv"
    assert resolve_selected_report_key(entries, "missing") == "005930:a.csv"
    assert resolve_selected_report_key([], "missing") is None


def test_get_report_entry_by_key_and_selected_entry_key_index_work_together() -> None:
    entries = [
        {"entry_key": "005930:a.csv", "symbol": "005930", "symbol_name": "삼성전자"},
        {"entry_key": "000660:b.csv", "symbol": "000660", "symbol_name": "SK하이닉스"},
    ]

    assert get_report_entry_by_key(entries, "000660:b.csv") == entries[1]
    assert selected_entry_key_index(entries, "000660:b.csv") == 1
    assert selected_entry_key_index(entries, None) == 0
