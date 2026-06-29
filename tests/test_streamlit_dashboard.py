from __future__ import annotations

from datetime import date
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import pytest

from invest_bot.dashboard.service import DashboardDataService, DatasetPreview
from invest_bot.dashboard.report_favorites import ReportFavoritesStore
from invest_bot.dashboard.streamlit_charts import available_chart_presets, default_chart_preset, prepare_time_series_frame
import invest_bot.dashboard.streamlit_actions as streamlit_actions_module
import invest_bot.dashboard.streamlit_data as streamlit_data_module
from invest_bot.dashboard.streamlit_actions import (
    require_selected_items,
    successful_symbols_from_collection_result,
)
from invest_bot.dashboard.streamlit_formatters import (
    default_selected_symbols as _default_selected_symbols,
    default_single_symbol as _default_single_symbol,
    format_display_value as _format_display_value,
    format_symbol_display as _format_symbol_display,
    format_symbol_option as _format_symbol_option,
    localize_reason as _localize_reason,
    localize_report_summary as _localize_report_summary,
    localize_report_summary_from_row as _localize_report_summary_from_row,
    state_text_color as _state_text_color,
)
import invest_bot.dashboard.streamlit_reports as streamlit_reports_module
import invest_bot.dashboard.streamlit_watchlist as streamlit_watchlist_module
from invest_bot.dashboard.streamlit_reports import (
    build_strategy_summary_items,
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
from invest_bot.dashboard.streamlit_watchlist import refresh_favorite_symbols_if_needed, render_watchlist_tab
from invest_bot.market.symbol_lookup import ResolvedSymbol, SymbolEntry
from tests.helpers import make_test_dir


class _FakeDatasetStorage:
    def __init__(self, frames: dict[tuple[str, str], tuple[str, pd.DataFrame]]):
        self.frames = frames

    def latest_filename(self, dataset: str, symbol: str) -> str | None:
        item = self.frames.get((dataset, symbol))
        return item[0] if item is not None else None

    def load(self, dataset: str, filename: str) -> pd.DataFrame:
        for (current_dataset, _symbol), (current_filename, frame) in self.frames.items():
            if current_dataset == dataset and current_filename == filename:
                return frame
        raise FileNotFoundError(filename)


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

    with pytest.raises(ValueError, match="자동완성 목록에서 종목을 하나 이상 선택해 주세요."):
        require_selected_items([])


def test_successful_symbols_from_collection_result_prefers_explicit_success_list() -> None:
    assert successful_symbols_from_collection_result({"successful_symbols": ["005930", "000660"]}) == ["005930", "000660"]
    assert successful_symbols_from_collection_result({"symbols": ["005930"]}) == []


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


def test_format_report_selection_option_marks_favorite_entries() -> None:
    entries = [
        {
            "entry_key": "005930:a.csv",
            "symbol": "005930",
            "symbol_name": "삼성전자",
            "display_opinion": "매수 관점",
            "date": "2026-06-24",
            "is_favorite": True,
        }
    ]

    assert format_report_selection_option(entries, "005930:a.csv") == "★ 삼성전자 (005930) · 매수 관점 · 2026-06-24"


def test_build_strategy_summary_items_formats_three_strategy_rows() -> None:
    service = DashboardDataService()
    row = pd.Series(
        {
            "rsi_strategy_signal": "hold",
            "rsi_strategy_reason": "rsi_14 is 58.00, between buy threshold 30.00 and sell threshold 70.00.",
            "trend_filter_signal": "buy",
            "trend_filter_reason": "close is 72000.00, above ma_60 68900.00 and above prev_close 71500.00.",
            "mean_reversion_signal": "hold",
            "mean_reversion_reason": "close is 72000.00, at 1.0256 of ma_20 70200.00, inside the mean-reversion band.",
        }
    )

    items = build_strategy_summary_items(service, row)

    assert [item["label"] for item in items] == ["RSI", "Trend Filter", "Mean Reversion"]
    assert [item["signal_label"] for item in items] == ["관망", "매수 관점", "관망"]
    assert items[1]["reason"].startswith("close is 72000.00")


class _FakeMetricColumn:
    def __init__(self, owner=None):
        self.owner = owner

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None

    def metric(self, label: str, value=None, *args, **kwargs) -> None:
        assert self.owner is not None
        self.owner.metric_calls.append((label, value))

    def toggle(self, *args, **kwargs) -> bool:
        assert self.owner is not None
        return self.owner.toggle(*args, **kwargs)

    def selectbox(self, *args, **kwargs):
        assert self.owner is not None
        return self.owner.selectbox(*args, **kwargs)

    def button(self, *args, **kwargs) -> bool:
        assert self.owner is not None
        return self.owner.button(*args, **kwargs)

    def markdown(self, *args, **kwargs) -> None:
        assert self.owner is not None
        return self.owner.markdown(*args, **kwargs)

    def caption(self, *args, **kwargs) -> None:
        assert self.owner is not None
        return self.owner.caption(*args, **kwargs)

    def multiselect(self, *args, **kwargs):
        assert self.owner is not None
        return self.owner.multiselect(*args, **kwargs)

    def number_input(self, *args, **kwargs):
        assert self.owner is not None
        return self.owner.number_input(*args, **kwargs)

    def slider(self, *args, **kwargs):
        assert self.owner is not None
        return self.owner.slider(*args, **kwargs)


class _FakeContext:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None




class _FakeSessionState(dict):
    def __getattr__(self, name: str):
        try:
            return self[name]
        except KeyError as error:
            raise AttributeError(name) from error

    def __setattr__(self, name: str, value) -> None:
        self[name] = value


class _FakeStreamlit:
    def __init__(
        self,
        *,
        query: str = "",
        selected_value: str | None = None,
        multiselect_values: list[str] | None = None,
        toggle_values: dict[str, bool] | None = None,
        button_values: dict[str, bool] | None = None,
    ):
        self.query = query
        self.selected_value = selected_value
        self.multiselect_values = multiselect_values
        self.toggle_values = toggle_values or {}
        self.button_values = button_values or {}
        self.session_state = _FakeSessionState()
        self.warning_messages: list[str] = []
        self.info_messages: list[str] = []
        self.markdown_calls: list[str] = []
        self.caption_calls: list[str] = []
        self.metric_calls: list[tuple[str, object]] = []
        self.selectbox_labels: list[str] = []
        self.multiselect_labels: list[str] = []
        self.button_labels: list[str] = []
        self.expander_labels: list[str] = []
        self.tab_labels: list[str] = []
        self.dataframe_calls = 0

    def markdown(self, body: str, *args, **kwargs) -> None:
        self.markdown_calls.append(body)

    def text_input(self, *args, **kwargs) -> str:
        return self.query

    def columns(self, spec, **kwargs):
        count = spec if isinstance(spec, int) else len(spec)
        return [_FakeMetricColumn(self) for _ in range(count)]

    def warning(self, message: str) -> None:
        self.warning_messages.append(message)

    def info(self, message: str) -> None:
        self.info_messages.append(message)

    def selectbox(self, label: str, options: list[str], index: int = 0, format_func=None, key: str | None = None, **kwargs):
        self.selectbox_labels.append(label)
        value = self.selected_value if self.selected_value in options else options[index]
        if key is not None:
            self.session_state[key] = value
        return value

    def multiselect(self, label: str, options: list[str], default=None, key: str | None = None, **kwargs):
        self.multiselect_labels.append(label)
        value = self.multiselect_values if self.multiselect_values is not None else (default or [])
        if key is not None:
            self.session_state[key] = value
        return value

    def number_input(self, label: str, value=0, **kwargs):
        return value

    def slider(self, label: str, value=0, key: str | None = None, **kwargs):
        if key is not None:
            self.session_state[key] = value
        return value

    def caption(self, body: str, *args, **kwargs) -> None:
        self.caption_calls.append(body)

    def container(self, **kwargs):
        return _FakeContext()

    def expander(self, label: str, **kwargs):
        self.expander_labels.append(label)
        return _FakeContext()

    def tabs(self, labels):
        self.tab_labels.extend(labels)
        return [_FakeContext() for _ in labels]

    def toggle(self, label: str, value: bool = False, key: str | None = None, **kwargs) -> bool:
        result = self.toggle_values.get(key or label, value)
        if key is not None:
            self.session_state[key] = result
        return result

    def button(self, label: str, key: str | None = None, **kwargs) -> bool:
        self.button_labels.append(label)
        return self.button_values.get(key or label, False)

    def dataframe(self, *args, **kwargs) -> None:
        self.dataframe_calls += 1

    def rerun(self) -> None:
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


def test_build_report_entries_marks_favorite_symbols() -> None:
    previews = [_make_report_preview("005930", "삼성전자", "005930_20260624.csv")]
    frames = {
        "005930": pd.DataFrame([{"date": "2026-06-24", "symbol_name": "삼성전자", "final_opinion": "buy", "summary": "a", "trend_state": "bullish", "golden_cross_signal": "buy", "rsi_state": "strong", "investor_flow": "supportive"}]),
    }

    entries = streamlit_reports_module.build_report_entries(
        previews,
        DashboardDataService(),
        read_preview_frame=lambda preview: frames[preview.symbol],
        favorite_symbols={"005930"},
    )

    assert entries[0]["is_favorite"] is True


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


def test_filter_report_entries_can_limit_to_favorites_only() -> None:
    entries = [
        {"symbol": "005930", "symbol_name": "삼성전자", "display_opinion": "매수 관점", "display_trend": "상승 우세", "display_signal": "매수 관점", "is_favorite": True},
        {"symbol": "000660", "symbol_name": "SK하이닉스", "display_opinion": "관망", "display_trend": "중립", "display_signal": "관망", "is_favorite": False},
    ]

    filtered = filter_report_entries(entries, query="", opinion_filter="전체", trend_filter="전체", signal_filter="전체", favorites_only=True)

    assert [entry["symbol"] for entry in filtered] == ["005930"]


def test_sort_report_entries_can_prioritize_favorites() -> None:
    entries = [
        {"symbol": "000660", "symbol_name": "SK하이닉스", "date": "2026-06-24", "is_favorite": False},
        {"symbol": "005930", "symbol_name": "삼성전자", "date": "2026-06-23", "is_favorite": True},
    ]

    sorted_entries = sort_report_entries(entries, "즐겨찾기 우선")

    assert [entry["symbol"] for entry in sorted_entries] == ["005930", "000660"]


def test_resolve_selected_report_key_keeps_current_selection_when_still_visible() -> None:
    entries = [
        {"entry_key": "005930:a.csv", "symbol": "005930", "symbol_name": "삼성전자", "is_favorite": True},
        {"entry_key": "000660:b.csv", "symbol": "000660", "symbol_name": "SK하이닉스", "is_favorite": False},
    ]

    assert resolve_selected_report_key(entries, "000660:b.csv") == "000660:b.csv"


def test_render_market_report_card_toggles_favorite_store(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_st = _FakeStreamlit(button_values={"favorite_report_005930_005930_20260624.csv": True})
    monkeypatch.setattr(streamlit_reports_module, "st", fake_st)
    monkeypatch.setattr(streamlit_reports_module, "render_chart_selector", lambda *args, **kwargs: None)
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
    store_path = make_test_dir("report_card_toggle") / "favorites.json"
    store = ReportFavoritesStore(store_path)

    streamlit_reports_module.render_market_report_card(
        preview,
        DashboardDataService(),
        frame=frame,
        read_preview_frame=lambda _: frame,
        load_indicator_frame_for_symbol=lambda symbol: frame,
        favorites_store=store,
        is_favorite=False,
    )

    assert store.load_symbols() == {"005930"}
    assert "즐겨찾기 추가 완료" in str(fake_st.session_state["action_message"])


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



def test_refresh_favorite_symbols_bootstraps_missing_data_and_runs_pipeline() -> None:
    service = DashboardDataService(dataset_storage=_FakeDatasetStorage({}))
    collect_calls: list[tuple[list[str], int]] = []
    analyzed: list[str] = []
    signaled: list[str] = []
    reported: list[str] = []

    result = refresh_favorite_symbols_if_needed(
        service,
        {"005930"},
        today=date(2026, 6, 29),
        collect_callback=lambda symbols, days: (
            collect_calls.append((symbols, days))
            or {"successful_symbols": ["005930"], "failed_count": 0}
        ),
        analyze_callback=lambda symbol: analyzed.append(symbol),
        signal_callback=lambda symbol: signaled.append(symbol),
        report_callback=lambda symbol: reported.append(symbol),
    )

    assert collect_calls == [(["005930"], 365)]
    assert analyzed == ["005930"]
    assert signaled == ["005930"]
    assert reported == ["005930"]
    assert result["collected_symbols"] == ["005930"]
    assert result["pipeline_symbols"] == ["005930"]


def test_refresh_favorite_symbols_skips_when_current_and_report_ready() -> None:
    storage = _FakeDatasetStorage(
        {
            ("daily_prices", "005930"): (
                "005930_20250629_20260629.csv",
                pd.DataFrame([{"stck_bsop_date": "20260629", "stck_clpr": "1000"}]),
            ),
            ("investor_daily_summary", "005930"): (
                "005930_20260629.csv",
                pd.DataFrame([{"stck_bsop_date": "20260629", "frgn_ntby_qty": "100"}]),
            ),
            ("market_reports", "005930"): (
                "005930_20260629.csv",
                pd.DataFrame([{"date": "2026-06-29", "final_opinion": "buy"}]),
            ),
        }
    )
    service = DashboardDataService(dataset_storage=storage)
    collect_calls: list[tuple[list[str], int]] = []
    pipeline_calls: list[str] = []

    result = refresh_favorite_symbols_if_needed(
        service,
        {"005930"},
        today=date(2026, 6, 29),
        collect_callback=lambda symbols, days: (collect_calls.append((symbols, days)) or {"successful_symbols": symbols}),
        analyze_callback=lambda symbol: pipeline_calls.append(f"analyze:{symbol}"),
        signal_callback=lambda symbol: pipeline_calls.append(f"signal:{symbol}"),
        report_callback=lambda symbol: pipeline_calls.append(f"report:{symbol}"),
    )

    assert collect_calls == []
    assert pipeline_calls == []
    assert result == {"collected_symbols": [], "pipeline_symbols": []}


def test_refresh_favorite_symbols_recollects_stale_data_and_rebuilds_report() -> None:
    storage = _FakeDatasetStorage(
        {
            ("daily_prices", "005930"): (
                "005930_20250601_20260627.csv",
                pd.DataFrame([{"stck_bsop_date": "20260627", "stck_clpr": "1000"}]),
            ),
            ("investor_daily_summary", "005930"): (
                "005930_20260627.csv",
                pd.DataFrame([{"stck_bsop_date": "20260627", "frgn_ntby_qty": "100"}]),
            ),
            ("market_reports", "005930"): (
                "005930_20260627.csv",
                pd.DataFrame([{"date": "2026-06-27", "final_opinion": "buy"}]),
            ),
        }
    )
    service = DashboardDataService(dataset_storage=storage)
    collect_calls: list[tuple[list[str], int]] = []
    pipeline_calls: list[str] = []

    result = refresh_favorite_symbols_if_needed(
        service,
        {"005930"},
        today=date(2026, 6, 29),
        collect_callback=lambda symbols, days: (collect_calls.append((symbols, days)) or {"successful_symbols": ["005930"]}),
        analyze_callback=lambda symbol: pipeline_calls.append(f"analyze:{symbol}"),
        signal_callback=lambda symbol: pipeline_calls.append(f"signal:{symbol}"),
        report_callback=lambda symbol: pipeline_calls.append(f"report:{symbol}"),
    )

    assert collect_calls == [(["005930"], 365)]
    assert pipeline_calls == ["analyze:005930", "signal:005930", "report:005930"]
    assert result["collected_symbols"] == ["005930"]
    assert result["pipeline_symbols"] == ["005930"]

def test_render_watchlist_tab_shows_info_when_no_favorites(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_st = _FakeStreamlit()
    monkeypatch.setattr(streamlit_watchlist_module, "st", fake_st)
    snapshot = SimpleNamespace(processed_previews=[_make_report_preview("005930", "삼성전자", "005930_20260624.csv")])
    store = ReportFavoritesStore(make_test_dir("watchlist_no_favorites") / "favorites.json")

    render_watchlist_tab(
        snapshot,
        DashboardDataService(),
        read_preview_frame=lambda preview: pd.DataFrame(),
        load_indicator_frame_for_symbol=lambda symbol: None,
        favorites_store=store,
    )

    assert fake_st.info_messages == ["아직 저장된 관심종목이 없습니다. `리포트 해석` 탭에서 관심종목을 추가해 보세요."]


def test_render_watchlist_tab_renders_only_one_selected_favorite(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_st = _FakeStreamlit(selected_value="005930:005930_20260624.csv")
    monkeypatch.setattr(streamlit_watchlist_module, "st", fake_st)
    monkeypatch.setattr(
        streamlit_watchlist_module,
        "refresh_favorite_symbols_if_needed",
        lambda *args, **kwargs: {"collected_symbols": [], "pipeline_symbols": []},
    )

    captured: list[str] = []

    def fake_render_market_report_card(preview, service, **kwargs) -> None:
        captured.append(preview.symbol)

    monkeypatch.setattr(streamlit_watchlist_module, "render_market_report_card", fake_render_market_report_card)

    previews = [
        _make_report_preview("005930", "삼성전자", "005930_20260624.csv"),
        _make_report_preview("000660", "SK하이닉스", "000660_20260624.csv"),
    ]
    frames = {
        "005930": pd.DataFrame([{"date": "2026-06-24", "symbol_name": "삼성전자", "final_opinion": "buy", "summary": "a", "trend_state": "bullish", "golden_cross_signal": "buy", "rsi_state": "strong", "investor_flow": "supportive"}]),
        "000660": pd.DataFrame([{"date": "2026-06-24", "symbol_name": "SK하이닉스", "final_opinion": "hold", "summary": "b", "trend_state": "neutral", "golden_cross_signal": "hold", "rsi_state": "neutral", "investor_flow": "mixed"}]),
    }
    snapshot = SimpleNamespace(processed_previews=previews)
    store = ReportFavoritesStore(make_test_dir("watchlist_selected") / "favorites.json")
    store.add("005930")
    store.add("000660")

    render_watchlist_tab(
        snapshot,
        DashboardDataService(),
        read_preview_frame=lambda preview: frames[preview.symbol],
        load_indicator_frame_for_symbol=lambda symbol: frames[symbol],
        favorites_store=store,
    )

    assert captured == ["005930"]


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


def _make_dataset_preview(name: str, symbol: str, symbol_name: str, filename: str, *, columns: list[str] | None = None) -> DatasetPreview:
    return DatasetPreview(
        name=name,
        display_name=DashboardDataService.DATASET_GUIDES.get(name).title if name in DashboardDataService.DATASET_GUIDES else name,
        path=Path(filename),
        row_count=3,
        columns=columns or ["date", "symbol_name", "close"],
        summary="summary",
        purpose="purpose",
        first_look="first_look",
        symbol=symbol,
        symbol_name=symbol_name,
        recommended_columns=["date", "symbol_name", "close"],
    )


def test_state_text_color_uses_green_red_black_contract() -> None:
    assert _state_text_color("buy") == "#15803d"
    assert _state_text_color("sell") == "#b91c1c"
    assert _state_text_color("hold") == "#111827"


def test_render_actions_tab_removes_actions_guide_and_keeps_primary_controls_visible(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_st = _FakeStreamlit(multiselect_values=["005930"], selected_value="005930")
    monkeypatch.setattr(streamlit_actions_module, "st", fake_st)

    symbol_lookup = SimpleNamespace(
        list_entries=lambda: [
            SymbolEntry(symbol="005930", symbol_name="삼성전자"),
            SymbolEntry(symbol="000660", symbol_name="SK하이닉스"),
        ]
    )

    streamlit_actions_module.render_actions_tab(
        symbol_lookup,
        schedule_status=None,
        render_schedule_status_panel=lambda _: None,
    )

    joined_markdown = "\n".join(fake_st.markdown_calls)
    assert "배치 실행" in joined_markdown
    assert "실행 가이드" not in joined_markdown
    assert fake_st.multiselect_labels == ["종목 선택"]
    assert "한 종목 선택" not in fake_st.selectbox_labels
    assert {"데이터 수집", "전체 파이프라인", "지표 계산", "신호 생성", "리포트 생성"}.issubset(set(fake_st.button_labels))


def test_render_reports_tab_removes_top_metrics_strip_and_keeps_single_report_flow(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_st = _FakeStreamlit()
    monkeypatch.setattr(streamlit_reports_module, "st", fake_st)

    previews = [_make_report_preview("005930", "삼성전자", "005930_20260624.csv")]
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
    snapshot = SimpleNamespace(processed_previews=previews)

    streamlit_reports_module.render_reports_tab(
        snapshot,
        DashboardDataService(),
        read_preview_frame=lambda preview: frame,
        load_indicator_frame_for_symbol=lambda symbol: frame,
    )

    metric_labels = [label for label, _ in fake_st.metric_calls]
    assert "전체 리포트" not in metric_labels
    assert "현재 후보" not in metric_labels
    assert "즐겨찾기" not in metric_labels
    assert "리포트 선택" in fake_st.selectbox_labels


def test_render_data_tab_escapes_symbol_and_summary_html(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_st = _FakeStreamlit(selected_value="005930")
    monkeypatch.setattr(streamlit_data_module, "st", fake_st)
    monkeypatch.setattr(streamlit_data_module, "render_chart_selector", lambda *args, **kwargs: None)

    preview = _make_dataset_preview("daily_prices", "005930", "<b>삼성전자</b>", "005930_prices.csv")
    preview.summary = "<script>alert(1)</script>"
    preview.purpose = "<i>purpose</i>"
    preview.first_look = "<u>first</u>"
    snapshot = SimpleNamespace(raw_previews=[preview], processed_previews=[])
    frame = pd.DataFrame([
        {"date": "2026-06-24", "symbol_name": "<b>삼성전자</b>", "close": 100},
    ])

    streamlit_data_module.render_data_tab(
        snapshot,
        DashboardDataService(),
        read_preview_frame=lambda _: frame,
    )

    joined_markdown = "\n".join(fake_st.markdown_calls)
    assert "&lt;b&gt;삼성전자&lt;/b&gt;" in joined_markdown
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in joined_markdown
    assert "&lt;i&gt;purpose&lt;/i&gt;" in joined_markdown
    assert "&lt;u&gt;first&lt;/u&gt;" in joined_markdown


def test_render_data_tab_is_symbol_first_and_detail_is_not_table_first(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_st = _FakeStreamlit(selected_value="005930")
    monkeypatch.setattr(streamlit_data_module, "st", fake_st)
    monkeypatch.setattr(streamlit_data_module, "render_chart_selector", lambda *args, **kwargs: None)

    raw_preview = _make_dataset_preview("daily_prices", "005930", "삼성전자", "005930_prices.csv")
    processed_preview = _make_dataset_preview("market_reports", "005930", "삼성전자", "005930_report.csv", columns=["date", "symbol_name", "final_opinion", "summary"])
    snapshot = SimpleNamespace(raw_previews=[raw_preview], processed_previews=[processed_preview])
    frames = {
        "daily_prices": pd.DataFrame([
            {"date": "2026-06-24", "symbol_name": "삼성전자", "close": 100},
            {"date": "2026-06-25", "symbol_name": "삼성전자", "close": 110},
        ]),
        "market_reports": pd.DataFrame([
            {"date": "2026-06-25", "symbol_name": "삼성전자", "final_opinion": "buy", "summary": "a"},
        ]),
    }

    streamlit_data_module.render_data_tab(
        snapshot,
        DashboardDataService(),
        read_preview_frame=lambda preview: frames[preview.name],
    )

    joined_markdown = "\n".join(fake_st.markdown_calls)
    assert "조회할 종목" in fake_st.selectbox_labels
    assert "원본 데이터" not in fake_st.tab_labels
    assert "분석 데이터" not in fake_st.tab_labels
    assert "빠른 미리보기" in joined_markdown
    assert "차트 · 전체 표 · 컬럼 설명 자세히 보기" in fake_st.expander_labels
    assert fake_st.dataframe_calls >= 2


def test_streamlit_apptest_smoke_for_actions_reports_and_data_tabs() -> None:
    AppTest = pytest.importorskip("streamlit.testing.v1").AppTest

    def render_actions_smoke() -> None:
        from types import SimpleNamespace
        from invest_bot.dashboard.streamlit_actions import render_actions_tab
        from invest_bot.market.symbol_lookup import SymbolEntry

        render_actions_tab(
            SimpleNamespace(list_entries=lambda: [SymbolEntry(symbol="005930", symbol_name="삼성전자")]),
            schedule_status=None,
            render_schedule_status_panel=lambda _: None,
        )

    def render_reports_smoke() -> None:
        from types import SimpleNamespace
        import pandas as pd
        from pathlib import Path
        from invest_bot.dashboard.service import DashboardDataService
        from invest_bot.dashboard.streamlit_reports import render_reports_tab
        from invest_bot.dashboard.service import DatasetPreview

        preview = DatasetPreview(
            name="market_reports",
            display_name="시장 상황 요약 리포트",
            path=Path("005930_20260624.csv"),
            row_count=1,
            columns=["date", "symbol_name", "final_opinion", "summary", "trend_state", "golden_cross_signal", "rsi_state", "investor_flow"],
            summary="summary",
            purpose="purpose",
            first_look="first_look",
            symbol="005930",
            symbol_name="삼성전자",
            recommended_columns=["date", "symbol_name", "final_opinion"],
        )
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
        render_reports_tab(
            SimpleNamespace(processed_previews=[preview]),
            DashboardDataService(),
            read_preview_frame=lambda _: frame,
            load_indicator_frame_for_symbol=lambda _: frame,
        )

    def render_data_smoke() -> None:
        from types import SimpleNamespace
        import pandas as pd
        from pathlib import Path
        from invest_bot.dashboard.service import DashboardDataService, DatasetPreview
        from invest_bot.dashboard.streamlit_data import render_data_tab

        preview = DatasetPreview(
            name="daily_prices",
            display_name="일봉 가격 데이터",
            path=Path("005930_prices.csv"),
            row_count=2,
            columns=["date", "symbol_name", "close"],
            summary="summary",
            purpose="purpose",
            first_look="first_look",
            symbol="005930",
            symbol_name="삼성전자",
            recommended_columns=["date", "symbol_name", "close"],
        )
        frame = pd.DataFrame([
            {"date": "2026-06-24", "symbol_name": "삼성전자", "close": 100},
            {"date": "2026-06-25", "symbol_name": "삼성전자", "close": 110},
        ])
        render_data_tab(
            SimpleNamespace(raw_previews=[preview], processed_previews=[]),
            DashboardDataService(),
            read_preview_frame=lambda _: frame,
        )

    actions_app = AppTest.from_function(render_actions_smoke)
    actions_app.run()
    assert not actions_app.exception

    reports_app = AppTest.from_function(render_reports_smoke)
    reports_app.run()
    assert not reports_app.exception

    data_app = AppTest.from_function(render_data_smoke)
    data_app.run()
    assert not data_app.exception
