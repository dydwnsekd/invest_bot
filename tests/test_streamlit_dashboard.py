from __future__ import annotations

from datetime import date
import tomllib
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import pytest

from invest_bot.dashboard.service import DashboardDataService, DatasetPreview
from invest_bot.dashboard.report_favorites import ReportFavoritesStore
from invest_bot.db.engine import build_engine, build_session_factory
from invest_bot.db.repositories import SqlAlchemyReportFavoriteSymbolRepository
from invest_bot.dashboard.streamlit_charts import (
    aggregate_professional_chart_frame,
    apply_time_window,
    available_chart_presets,
    build_chart,
    build_professional_plotly_chart,
    default_chart_preset,
    is_professional_stock_dataset,
    prepare_time_series_frame,
    resolve_range_state,
)
import invest_bot.dashboard.streamlit_charts as streamlit_charts_module
import invest_bot.dashboard.streamlit_actions as streamlit_actions_module
import invest_bot.dashboard.streamlit_dashboard as streamlit_dashboard_module
import invest_bot.dashboard.streamlit_data as streamlit_data_module
import invest_bot.dashboard.streamlit_interpretations as streamlit_interpretations_module
import invest_bot.dashboard.streamlit_layout as streamlit_layout_module
import invest_bot.dashboard.streamlit_styles as streamlit_styles_module
from invest_bot.dashboard.streamlit_interpretations import (
    build_interpretation_rows,
    build_strategy_reason_rows,
    count_buy_strategy_signals,
    filter_interpretation_entries,
)
from invest_bot.dashboard.streamlit_actions import (
    describe_delivery_problems,
    normalize_delivery_detail,
    require_selected_items,
    run_full_pipeline_action,
    run_market_report_batch_action,
    successful_symbols_from_collection_result,
    summarize_report_delivery_results,
)
from invest_bot.config.settings import AppSettings
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
from invest_bot.dashboard.streamlit_state import load_professional_chart_frame_for_symbol
from tests.helpers import init_test_db, make_test_dir


def test_apply_custom_style_emits_approved_dark_terminal_theme(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    def _capture_markdown(body: str, *, unsafe_allow_html: bool) -> None:
        captured["body"] = body
        captured["unsafe_allow_html"] = unsafe_allow_html

    monkeypatch.setattr(streamlit_styles_module, "st", SimpleNamespace(markdown=_capture_markdown))

    streamlit_styles_module.apply_custom_style()

    style = str(captured["body"])

    assert captured["unsafe_allow_html"] is True
    assert '--app-bg: #050816;' in style
    assert 'linear-gradient(180deg, #020617 0%, #050816 48%, #0f172a 100%)' in style
    assert '"Pretendard", "Noto Sans KR", "Apple SD Gothic Neo", "Malgun Gothic"' in style
    assert '"Inter", "IBM Plex Sans"' in style
    assert 'font-family: "Material Symbols Rounded", "Material Symbols Outlined", "Material Icons" !important;' in style
    assert 'background: var(--app-success-bg);' in style
    assert 'background: var(--app-danger-bg);' in style
    assert 'background: var(--app-neutral-bg);' in style


def test_streamlit_config_uses_dark_theme_tokens() -> None:
    config_path = Path(__file__).resolve().parents[1] / '.streamlit' / 'config.toml'

    with config_path.open('rb') as stream:
        config = tomllib.load(stream)

    theme = config['theme']
    assert theme['base'] == 'dark'
    assert theme['backgroundColor'] == '#050816'
    assert theme['secondaryBackgroundColor'] == '#111827'
    assert theme['primaryColor'] == '#38bdf8'
    assert theme['textColor'] == '#f8fafc'
    assert theme['borderColor'] == '#475569'



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


def _make_favorites_store(name: str) -> ReportFavoritesStore:
    test_dir = make_test_dir(name)
    database_url = f"sqlite+pysqlite:///{(test_dir / 'favorites.db').as_posix()}"
    init_test_db(database_url)
    repository = SqlAlchemyReportFavoriteSymbolRepository(build_session_factory(build_engine(database_url)))
    return ReportFavoritesStore(repository)


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
    assert _format_display_value(service, "rsi_strategy_signal", "hold") == "관망"
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

    assert list(normalized.columns) == ["date", "frgn_ntby_qty"]
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


def test_is_professional_stock_dataset_requires_supported_dataset_and_normalized_ohlc() -> None:
    raw_daily_prices = pd.DataFrame(
        [
            {
                "stck_bsop_date": "20260328",
                "stck_oprc": 70000,
                "stck_hgpr": 71000,
                "stck_lwpr": 69500,
                "stck_clpr": 70800,
            }
        ]
    )

    incomplete_ohlc = raw_daily_prices.drop(columns=["stck_lwpr"])

    assert is_professional_stock_dataset("daily_prices", raw_daily_prices) is True
    assert is_professional_stock_dataset("daily_prices_indicators", incomplete_ohlc) is False
    assert is_professional_stock_dataset("investor_daily", raw_daily_prices) is False


def test_weekly_aggregation_uses_ohlcv_and_flow_sum_semantics() -> None:
    frame = pd.DataFrame(
        [
            {"date": "2026-03-30", "open": 10, "high": 15, "low": 9, "close": 14, "volume": 100, "frgn_ntby_qty": 5},
            {"date": "2026-03-31", "open": 14, "high": 16, "low": 13, "close": 15, "volume": 150, "frgn_ntby_qty": -2},
            {"date": "2026-04-03", "open": 15, "high": 18, "low": 14, "close": 17, "volume": 120, "frgn_ntby_qty": 7},
            {"date": "2026-04-06", "open": 18, "high": 20, "low": 17, "close": 19, "volume": 200, "frgn_ntby_qty": 3},
        ]
    )

    aggregated = aggregate_professional_chart_frame(frame, "weekly")

    assert aggregated["date"].dt.strftime("%Y-%m-%d").tolist() == ["2026-04-03", "2026-04-06"]
    assert aggregated[["open", "high", "low", "close", "volume", "frgn_ntby_qty"]].to_dict("records") == [
        {"open": 10, "high": 18, "low": 9, "close": 17, "volume": 370, "frgn_ntby_qty": 10},
        {"open": 18, "high": 20, "low": 17, "close": 19, "volume": 200, "frgn_ntby_qty": 3},
    ]


def test_monthly_aggregation_recomputes_ma_and_rsi_from_aggregated_close() -> None:
    month_ends = pd.date_range("2025-01-31", periods=15, freq="ME")
    closes = [10, 12, 11, 13, 15, 14, 16, 18, 17, 19, 18, 20, 22, 21, 23]
    frame = pd.DataFrame(
        [
            {
                "date": month_end,
                "open": close - 1,
                "high": close + 2,
                "low": close - 3,
                "close": close,
                "volume": (index + 1) * 100,
                "ma_5": 999,
                "rsi_14": 999,
            }
            for index, (month_end, close) in enumerate(zip(month_ends, closes, strict=False))
        ]
    )

    aggregated = aggregate_professional_chart_frame(frame, "monthly")
    expected_rsi = streamlit_charts_module.calculate_rsi(pd.Series(closes), period=14).iloc[-1]

    assert aggregated["close"].tolist() == closes
    assert aggregated.loc[4, "ma_5"] == pytest.approx(12.2)
    assert aggregated.loc[14, "rsi_14"] == pytest.approx(expected_rsi)
    assert aggregated.loc[14, "rsi_14"] != 999


def test_calculate_rsi_handles_rising_falling_and_flat_windows() -> None:
    rising = pd.Series(range(1, 17), dtype="float64")
    falling = pd.Series(range(16, 0, -1), dtype="float64")
    flat = pd.Series([10.0] * 16)

    assert streamlit_charts_module.calculate_rsi(rising, period=14).iloc[-1] == pytest.approx(100.0)
    assert streamlit_charts_module.calculate_rsi(falling, period=14).iloc[-1] == pytest.approx(0.0)
    assert streamlit_charts_module.calculate_rsi(flat, period=14).iloc[-1] == pytest.approx(50.0)


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


def test_available_chart_presets_ignores_all_null_flow_columns() -> None:
    frame = pd.DataFrame(
        [
            {"stck_bsop_date": "20260328", "frgn_ntby_qty": None, "orgn_ntby_qty": None, "prsn_ntby_qty": None},
            {"stck_bsop_date": "20260329", "frgn_ntby_qty": None, "orgn_ntby_qty": None, "prsn_ntby_qty": None},
        ]
    )

    assert available_chart_presets("investor_daily", frame) == []


def test_resolve_range_state_initializes_preset_and_range_dates() -> None:
    frame = pd.DataFrame(
        [
            {"date": "2026-01-01", "close": 10},
            {"date": "2026-02-15", "close": 20},
            {"date": "2026-03-31", "close": 30},
        ]
    )
    session_state: dict[str, object] = {}

    state = resolve_range_state(frame, key_prefix="report_chart", session_state=session_state)

    assert state.mode == "preset"
    assert state.preset == "90d"
    assert state.dates == (date(2026, 1, 1), date(2026, 3, 31))
    assert session_state["report_chart_range_mode"] == "preset"
    assert session_state["report_chart_range_preset"] == "90d"
    assert session_state["report_chart_range_dates"] == (date(2026, 1, 1), date(2026, 3, 31))


def test_resolve_range_state_syncs_range_dates_when_preset_changes() -> None:
    frame = pd.DataFrame(
        [
            {"date": "2026-01-01", "close": 10},
            {"date": "2026-02-15", "close": 20},
            {"date": "2026-03-31", "close": 30},
        ]
    )
    session_state = {
        "report_chart_range_mode": "custom",
        "report_chart_range_preset": "90d",
        "report_chart_range_dates": (date(2026, 1, 15), date(2026, 2, 10)),
    }

    state = resolve_range_state(
        frame,
        key_prefix="report_chart",
        session_state=session_state,
        selected_preset="30d",
    )

    assert state.mode == "preset"
    assert state.preset == "30d"
    assert state.dates == (date(2026, 3, 2), date(2026, 3, 31))
    assert session_state["report_chart_range_dates"] == (date(2026, 3, 2), date(2026, 3, 31))


def test_resolve_range_state_makes_direct_dates_authoritative_and_clamps() -> None:
    frame = pd.DataFrame(
        [
            {"date": "2026-01-01", "close": 10},
            {"date": "2026-02-15", "close": 20},
            {"date": "2026-03-31", "close": 30},
        ]
    )
    session_state = {
        "report_chart_range_mode": "preset",
        "report_chart_range_preset": "30d",
        "report_chart_range_dates": (date(2026, 3, 2), date(2026, 3, 31)),
    }

    state = resolve_range_state(
        frame,
        key_prefix="report_chart",
        session_state=session_state,
        selected_dates=(date(2025, 12, 1), date(2026, 2, 20)),
    )

    assert state.mode == "custom"
    assert state.preset == "30d"
    assert state.dates == (date(2026, 1, 1), date(2026, 2, 20))
    assert session_state["report_chart_range_mode"] == "custom"
    assert session_state["report_chart_range_dates"] == (date(2026, 1, 1), date(2026, 2, 20))


def test_apply_time_window_filters_inclusive_range_after_normalization() -> None:
    frame = pd.DataFrame(
        [
            {"date": "2026-01-01", "close": 10},
            {"date": "2026-02-15", "close": 20},
            {"date": "2026-03-31", "close": 30},
        ]
    )

    filtered = apply_time_window(frame, (date(2026, 2, 1), date(2026, 3, 1)))

    assert filtered["date"].dt.strftime("%Y-%m-%d").tolist() == ["2026-02-15"]


def test_build_chart_uses_plotly_library_for_close_ma_when_available(monkeypatch: pytest.MonkeyPatch) -> None:
    class _FakeFigure:
        def __init__(self):
            self.traces = []
            self.layout_updates = []
            self.yaxis_updates = []
            self.hlines = []

        def add_trace(self, trace) -> None:
            self.traces.append(trace)

        def update_layout(self, **kwargs) -> None:
            self.layout_updates.append(kwargs)

        def update_yaxes(self, **kwargs) -> None:
            self.yaxis_updates.append(kwargs)

        def add_hline(self, **kwargs) -> None:
            self.hlines.append(kwargs)

    class _FakeGo:
        Figure = _FakeFigure

        @staticmethod
        def Scatter(**kwargs):
            return ("scatter", kwargs)

        @staticmethod
        def Bar(**kwargs):
            return ("bar", kwargs)

        @staticmethod
        def Candlestick(**kwargs):
            return ("candlestick", kwargs)

    monkeypatch.setattr(streamlit_charts_module, "go", _FakeGo)
    frame = pd.DataFrame(
        [
            {"date": "2026-03-28", "close": 70800, "ma_5": 70200, "ma_20": 69000},
            {"date": "2026-03-29", "close": 71000, "ma_5": 70400, "ma_20": 69200},
        ]
    )

    figure = build_chart(frame, "close_ma", library="plotly")

    assert isinstance(figure, _FakeFigure)
    assert len(figure.traces) == 3
    assert figure.layout_updates[-1]["hovermode"] == "x unified"
    assert figure.layout_updates[-1]["xaxis"]["showspikes"] is True
    assert figure.layout_updates[-1]["yaxis"] == {"title": "가격", "tickformat": ","}


def test_build_professional_plotly_chart_creates_multi_panel_shared_hover(monkeypatch: pytest.MonkeyPatch) -> None:
    class _FakeFigure:
        def __init__(self, **kwargs):
            self.kwargs = kwargs
            self.traces = []
            self.layout_updates = []
            self.yaxis_updates = []
            self.hlines = []

        def add_trace(self, trace, row=None, col=None) -> None:
            self.traces.append((trace, row, col))

        def update_layout(self, **kwargs) -> None:
            self.layout_updates.append(kwargs)

        def update_yaxes(self, **kwargs) -> None:
            self.yaxis_updates.append(kwargs)

        def add_hline(self, **kwargs) -> None:
            self.hlines.append(kwargs)

    class _FakeGo:
        @staticmethod
        def Scatter(**kwargs):
            return ("scatter", kwargs)

        @staticmethod
        def Bar(**kwargs):
            return ("bar", kwargs)

        @staticmethod
        def Candlestick(**kwargs):
            return ("candlestick", kwargs)

    def _fake_make_subplots(**kwargs):
        return _FakeFigure(**kwargs)

    monkeypatch.setattr(streamlit_charts_module, "go", _FakeGo)
    monkeypatch.setattr(streamlit_charts_module, "make_subplots", _fake_make_subplots)
    frame = aggregate_professional_chart_frame(
        pd.DataFrame(
            [
                {"date": f"2025-{month:02d}-28", "open": month * 10 - 1, "high": month * 10 + 2, "low": month * 10 - 3, "close": month * 10, "volume": month * 100, "frgn_ntby_qty": month}
                for month in range(1, 16)
            ]
        ),
        "monthly",
    )

    figure = build_professional_plotly_chart(frame, timeframe="monthly", height=640)

    assert figure.kwargs["shared_xaxes"] is True
    assert figure.kwargs["rows"] == 4
    assert figure.kwargs["vertical_spacing"] == streamlit_charts_module.PROFESSIONAL_CHART_VERTICAL_SPACING
    assert figure.kwargs["row_heights"] == [0.68, 0.32, 0.32, 0.26]
    assert figure.layout_updates[-1]["hovermode"] == "x unified"
    assert figure.layout_updates[-1]["xaxis"]["rangeslider"]["visible"] is False
    assert any(update["title_text"] == "가격" and update["tickformat"] == "," and update["row"] == 1 for update in figure.yaxis_updates)
    candlestick_trace = next(trace[0][1] for trace in figure.traces if trace[0][0] == "candlestick")
    assert "시가: %{customdata[0]:,.0f}" in candlestick_trace["hovertemplate"]
    assert "종가: %{customdata[3]:,.0f}" in candlestick_trace["hovertemplate"]
    assert any(trace[0][0] == "candlestick" and trace[1] == 1 for trace in figure.traces)
    assert any(trace[0][0] == "bar" and trace[1] == 2 for trace in figure.traces)
    assert any(trace[0][0] == "scatter" and trace[1] == 3 for trace in figure.traces)
    assert any(trace[1] == 4 for trace in figure.traces)



def test_build_professional_plotly_chart_skips_fake_zero_volume_when_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    class _FakeFigure:
        def __init__(self, **kwargs):
            self.kwargs = kwargs
            self.traces = []
            self.layout_updates = []
            self.yaxis_updates = []
            self.hlines = []

        def add_trace(self, trace, row=None, col=None) -> None:
            self.traces.append((trace, row, col))

        def update_layout(self, **kwargs) -> None:
            self.layout_updates.append(kwargs)

        def update_yaxes(self, **kwargs) -> None:
            self.yaxis_updates.append(kwargs)

        def add_hline(self, **kwargs) -> None:
            self.hlines.append(kwargs)

    class _FakeGo:
        @staticmethod
        def Scatter(**kwargs):
            return ("scatter", kwargs)

        @staticmethod
        def Bar(**kwargs):
            return ("bar", kwargs)

        @staticmethod
        def Candlestick(**kwargs):
            return ("candlestick", kwargs)

    monkeypatch.setattr(streamlit_charts_module, "go", _FakeGo)
    monkeypatch.setattr(streamlit_charts_module, "make_subplots", lambda **kwargs: _FakeFigure(**kwargs))

    frame = pd.DataFrame(
        [
            {"date": "2026-06-29", "open": 98, "high": 101, "low": 96, "close": 100, "rsi_14": 55.0},
            {"date": "2026-06-30", "open": 105, "high": 112, "low": 104, "close": 110, "rsi_14": 60.0},
        ]
    )

    figure = build_professional_plotly_chart(frame, timeframe="daily", height=560)

    assert figure is not None
    assert not any(trace[0][0] == "bar" and trace[1] == 2 for trace in figure.traces)
    assert figure.kwargs["subplot_titles"][1] == "거래량 없음"
    assert any(update["title_text"] == "거래량 없음" and update["row"] == 2 for update in figure.yaxis_updates)


def test_build_chart_preserves_full_filtered_range_instead_of_retruncating() -> None:
    frame = pd.DataFrame(
        [
            {"date": f"2026-01-{day:02d}", "close": day}
            for day in range(1, 32)
        ]
        + [
            {"date": f"2026-02-{day:02d}", "close": 31 + day}
            for day in range(1, 29)
        ]
        + [
            {"date": f"2026-03-{day:02d}", "close": 59 + day}
            for day in range(1, 32)
        ]
        + [
            {"date": f"2026-04-{day:02d}", "close": 90 + day}
            for day in range(1, 31)
        ]
    )

    chart = build_chart(frame, "close_only", library="plotly")

    assert len(chart.data[0].x) == len(frame)


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


def test_localize_reason_formats_strategy_reason_patterns() -> None:
    assert _localize_reason("rsi_14 is 25.00, at or below buy threshold 30.00.") == "RSI 14가 25.00로 매수 기준 30.00 이하입니다."
    assert _localize_reason("rsi_14 is 75.00, at or above sell threshold 70.00.") == "RSI 14가 75.00로 매도 기준 70.00 이상입니다."
    assert _localize_reason("close is 65000.00, below ma_60 68900.00 and below prev_close 66000.00.") == (
        "종가가 65,000로 60일 이동평균선 68,900와 직전 종가 66,000보다 낮습니다."
    )
    assert _localize_reason("close is 70000.00, showing a mixed signal versus ma_60 68900.00 and prev_close 71500.00.") == (
        "종가가 70,000로 60일 이동평균선 68,900 및 직전 종가 71,500 대비 혼조 신호입니다."
    )
    assert _localize_reason("close is 68000.00, at 0.9600 of ma_20 70800.00, at or below buy ratio 0.9700.") == (
        "종가가 68,000로 20일 이동평균선 70,800 대비 0.9600배이며, 매수 비율 기준 0.9700 이하입니다."
    )
    assert _localize_reason("close is 74000.00, at 1.0400 of ma_20 71150.00, at or above sell ratio 1.0300.") == (
        "종가가 74,000로 20일 이동평균선 71,150 대비 1.0400배이며, 매도 비율 기준 1.0300 이상입니다."
    )


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

    assert [item["label"] for item in items] == ["RSI 전략", "추세 필터 전략", "평균회귀 전략"]
    assert [item["signal_label"] for item in items] == ["관망", "매수 관점", "관망"]
    assert items[0]["reason"] == "RSI 14가 58.00로 매수 기준 30.00과 매도 기준 70.00 사이입니다."
    assert items[1]["reason"] == "종가가 72,000로 60일 이동평균선 68,900와 직전 종가 71,500보다 높습니다."
    assert items[2]["reason"] == "종가가 72,000로 20일 이동평균선 70,200 대비 1.0256배이며, 평균회귀 기준 범위 안에 있습니다."


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

    def radio(self, *args, **kwargs):
        assert self.owner is not None
        return self.owner.radio(*args, **kwargs)

    def date_input(self, *args, **kwargs):
        assert self.owner is not None
        return self.owner.date_input(*args, **kwargs)


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
        self.success_messages: list[str] = []
        self.error_messages: list[str] = []
        self.markdown_calls: list[str] = []
        self.caption_calls: list[str] = []
        self.metric_calls: list[tuple[str, object]] = []
        self.selectbox_labels: list[str] = []
        self.multiselect_labels: list[str] = []
        self.button_labels: list[str] = []
        self.expander_labels: list[str] = []
        self.tab_labels: list[str] = []
        self.dataframe_calls = 0
        self.radio_labels: list[str] = []
        self.date_input_labels: list[str] = []
        self.altair_chart_calls: list[object] = []
        self.plotly_chart_calls: list[object] = []

    def markdown(self, body: str, *args, **kwargs) -> None:
        self.markdown_calls.append(body)

    def set_page_config(self, **kwargs) -> None:
        return None

    def text_input(self, *args, **kwargs) -> str:
        return self.query

    def columns(self, spec, **kwargs):
        count = spec if isinstance(spec, int) else len(spec)
        return [_FakeMetricColumn(self) for _ in range(count)]

    def warning(self, message: str) -> None:
        self.warning_messages.append(message)

    def info(self, message: str) -> None:
        self.info_messages.append(message)

    def success(self, message: str) -> None:
        self.success_messages.append(message)

    def error(self, message: str) -> None:
        self.error_messages.append(message)

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

    def radio(self, label: str, options: list[str], index: int = 0, key: str | None = None, **kwargs):
        self.radio_labels.append(label)
        value = self.session_state.get(key, options[index]) if key is not None else options[index]
        if key is not None:
            self.session_state[key] = value
        return value

    def date_input(self, label: str, value, key: str | None = None, **kwargs):
        self.date_input_labels.append(label)
        resolved = self.session_state.get(key, value) if key is not None else value
        if key is not None:
            self.session_state[key] = resolved
        return resolved

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

    def altair_chart(self, chart, *args, **kwargs) -> None:
        self.altair_chart_calls.append(chart)

    def plotly_chart(self, chart, *args, **kwargs) -> None:
        self.plotly_chart_calls.append(chart)

    def rerun(self) -> None:
        return None


def test_render_chart_selector_adds_period_controls_and_uses_plotly_renderer(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_st = _FakeStreamlit()
    monkeypatch.setattr(streamlit_charts_module, "st", fake_st)
    monkeypatch.setattr(streamlit_charts_module, "go", object())
    monkeypatch.setattr(streamlit_charts_module, "make_subplots", object())
    monkeypatch.setattr(streamlit_charts_module, "preferred_chart_library", lambda: "plotly")
    captured_chart_kwargs: dict[str, object] = {}

    def _fake_build_professional_plotly_chart(*args, **kwargs):
        captured_chart_kwargs.update(kwargs)
        return {"engine": "plotly"}

    monkeypatch.setattr(streamlit_charts_module, "build_professional_plotly_chart", _fake_build_professional_plotly_chart)

    frame = pd.DataFrame(
        [
            {"date": "2026-01-01", "open": 9, "high": 11, "low": 8, "close": 10, "volume": 100},
            {"date": "2026-02-15", "open": 19, "high": 21, "low": 18, "close": 20, "volume": 120},
            {"date": "2026-03-31", "open": 29, "high": 31, "low": 28, "close": 30, "volume": 140},
        ]
    )

    streamlit_charts_module.render_chart_selector(
        frame,
        dataset_name="daily_prices_indicators",
        key_prefix="report_chart",
        height=280,
    )

    assert "차트 유형" not in fake_st.selectbox_labels
    assert "조회 기간 방식" in fake_st.radio_labels
    assert "빠른 조회 기간" in fake_st.radio_labels
    assert "봉 기준" in fake_st.radio_labels
    assert "직접 조회 기간" in fake_st.date_input_labels
    assert fake_st.plotly_chart_calls == [{"engine": "plotly"}]
    assert captured_chart_kwargs["height"] == streamlit_charts_module.PROFESSIONAL_CHART_MIN_HEIGHT
    assert fake_st.session_state["report_chart_range_dates"] == (date(2026, 1, 1), date(2026, 3, 31))
    assert fake_st.session_state["report_chart_range_dates_widget_2026-01-01_2026-03-31"] == (date(2026, 1, 1), date(2026, 3, 31))


def test_render_chart_selector_shows_no_flow_caption_for_professional_chart_without_flow(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_st = _FakeStreamlit()
    monkeypatch.setattr(streamlit_charts_module, "st", fake_st)
    monkeypatch.setattr(streamlit_charts_module, "go", object())
    monkeypatch.setattr(streamlit_charts_module, "make_subplots", object())
    monkeypatch.setattr(streamlit_charts_module, "preferred_chart_library", lambda: "plotly")
    monkeypatch.setattr(streamlit_charts_module, "build_professional_plotly_chart", lambda *args, **kwargs: {"engine": "plotly"})
    frame = pd.DataFrame(
        [
            {"date": "2026-01-01", "open": 9, "high": 11, "low": 8, "close": 10, "volume": 100},
            {"date": "2026-01-02", "open": 10, "high": 12, "low": 9, "close": 11, "volume": 110},
        ]
    )

    streamlit_charts_module.render_chart_selector(
        frame,
        dataset_name="daily_prices_indicators",
        key_prefix="report_chart",
        height=280,
    )

    assert "수급 데이터 없음" in fake_st.caption_calls


def test_render_chart_selector_treats_all_null_flow_columns_as_no_flow(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_st = _FakeStreamlit()
    monkeypatch.setattr(streamlit_charts_module, "st", fake_st)
    monkeypatch.setattr(streamlit_charts_module, "go", object())
    monkeypatch.setattr(streamlit_charts_module, "make_subplots", object())
    monkeypatch.setattr(streamlit_charts_module, "preferred_chart_library", lambda: "plotly")
    monkeypatch.setattr(streamlit_charts_module, "build_professional_plotly_chart", lambda *args, **kwargs: {"engine": "plotly"})
    frame = pd.DataFrame(
        [
            {"date": "2026-01-01", "open": 9, "high": 11, "low": 8, "close": 10, "frgn_ntby_qty": None, "orgn_ntby_qty": None, "prsn_ntby_qty": None},
            {"date": "2026-01-02", "open": 10, "high": 12, "low": 9, "close": 11, "frgn_ntby_qty": None, "orgn_ntby_qty": None, "prsn_ntby_qty": None},
        ]
    )

    streamlit_charts_module.render_chart_selector(
        frame,
        dataset_name="daily_prices_indicators",
        key_prefix="report_chart",
        height=280,
    )

    assert "수급 데이터 없음" in fake_st.caption_calls


def test_render_chart_selector_keeps_generic_fallback_unchanged_for_non_stock_dataset(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_st = _FakeStreamlit()
    monkeypatch.setattr(streamlit_charts_module, "st", fake_st)
    monkeypatch.setattr(streamlit_charts_module, "go", object())
    monkeypatch.setattr(streamlit_charts_module, "make_subplots", object())
    monkeypatch.setattr(streamlit_charts_module, "preferred_chart_library", lambda: "plotly")
    monkeypatch.setattr(streamlit_charts_module, "build_chart", lambda *args, **kwargs: {"engine": "legacy"})
    frame = pd.DataFrame(
        [
            {"date": "2026-01-01", "close": 10, "ma_5": 9, "ma_20": 8},
            {"date": "2026-02-15", "close": 20, "ma_5": 19, "ma_20": 18},
        ]
    )

    streamlit_charts_module.render_chart_selector(
        frame,
        dataset_name="investor_daily",
        key_prefix="investor_chart",
        height=280,
    )

    assert "차트 유형" in fake_st.selectbox_labels
    assert "봉 기준" not in fake_st.radio_labels


def test_render_range_controls_resets_stale_date_widget_state_when_preset_changes(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_st = _FakeStreamlit()
    fake_st.session_state.update(
        {
            "report_chart_range_mode": "custom",
            "report_chart_range_preset": "90d",
            "report_chart_range_dates": (date(2026, 1, 15), date(2026, 2, 10)),
            "report_chart_range_mode_widget": "preset",
            "report_chart_range_preset_widget": "30d",
            "report_chart_range_dates_widget": (date(2026, 1, 15), date(2026, 2, 10)),
        }
    )
    monkeypatch.setattr(streamlit_charts_module, "st", fake_st)
    frame = pd.DataFrame(
        [
            {"date": "2026-01-01", "close": 10},
            {"date": "2026-02-15", "close": 20},
            {"date": "2026-03-31", "close": 30},
        ]
    )

    selected_preset, selected_dates = streamlit_charts_module.render_range_controls(frame, key_prefix="report_chart")

    assert (selected_preset, selected_dates) == ("30d", None)
    assert fake_st.session_state["report_chart_range_dates_widget"] == (date(2026, 1, 15), date(2026, 2, 10))
    assert fake_st.session_state["report_chart_range_dates_widget_2026-03-02_2026-03-31"] == (date(2026, 3, 2), date(2026, 3, 31))

    streamlit_charts_module.resolve_range_state(
        frame,
        key_prefix="report_chart",
        selected_preset=selected_preset,
        selected_dates=selected_dates,
    )
    second_selected_preset, second_selected_dates = streamlit_charts_module.render_range_controls(frame, key_prefix="report_chart")

    assert (second_selected_preset, second_selected_dates) == (None, None)
    assert fake_st.session_state["report_chart_range_dates"] == (date(2026, 3, 2), date(2026, 3, 31))


def test_render_range_controls_allows_direct_custom_date_range(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_st = _FakeStreamlit()
    fake_st.session_state.update(
        {
            "report_chart_range_mode_widget": "custom",
            "report_chart_range_dates_widget_2026-01-01_2026-03-31": (date(2026, 1, 15), date(2026, 2, 10)),
        }
    )
    monkeypatch.setattr(streamlit_charts_module, "st", fake_st)
    frame = pd.DataFrame(
        [
            {"date": "2026-01-01", "close": 10},
            {"date": "2026-02-15", "close": 20},
            {"date": "2026-03-31", "close": 30},
        ]
    )

    selected_preset, selected_dates = streamlit_charts_module.render_range_controls(frame, key_prefix="report_chart")

    assert (selected_preset, selected_dates) == (None, (date(2026, 1, 15), date(2026, 2, 10)))
    assert "조회 기간 방식" in fake_st.radio_labels
    assert "빠른 조회 기간" in fake_st.radio_labels
    assert "직접 조회 기간" in fake_st.date_input_labels

    range_state = streamlit_charts_module.resolve_range_state(
        frame,
        key_prefix="report_chart",
        selected_preset=selected_preset,
        selected_dates=selected_dates,
    )

    assert range_state.mode == "custom"
    assert range_state.dates == (date(2026, 1, 15), date(2026, 2, 10))


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
        favorites_store=_make_favorites_store("reports_selected"),
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
        favorites_store=_make_favorites_store("reports_no_match"),
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
    monkeypatch.setattr(streamlit_reports_module, "load_professional_chart_frame_for_symbol", lambda *_args, **_kwargs: None)
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
    store = _make_favorites_store("report_card_toggle")

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
    professional_calls: list[str] = []

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
    professional_frame = pd.DataFrame(
        [{"date": "2026-06-24", "open": 90, "high": 110, "low": 85, "close": 100, "ma_5": 90, "ma_20": 80, "rsi_14": 60}]
    )

    def fake_load_indicator(symbol: str):
        return pd.DataFrame([{"date": "2026-06-24", "close": 100, "ma_5": 90, "ma_20": 80, "rsi_14": 60}])

    def fake_load_professional(_service, symbol: str):
        professional_calls.append(symbol)
        return professional_frame

    monkeypatch.setattr(streamlit_reports_module, "load_professional_chart_frame_for_symbol", fake_load_professional)

    streamlit_reports_module.render_market_report_card(
        preview,
        DashboardDataService(),
        frame=frame,
        read_preview_frame=lambda _: frame,
        load_indicator_frame_for_symbol=fake_load_indicator,
    )

    assert professional_calls == ["005930"]
    assert chart_calls == [("daily_prices_indicators", "report_005930_005930_20260624.csv")]


def test_render_dataset_detail_uses_professional_chart_frame_for_stock_dataset(monkeypatch: pytest.MonkeyPatch) -> None:
    preview = _make_dataset_preview("daily_prices", "005930", "삼성전자", "005930_prices.csv")
    fallback_frame = pd.DataFrame([{"date": "2026-06-24", "symbol_name": "삼성전자", "close": 100}])
    professional_frame = pd.DataFrame(
        [{"date": "2026-06-24", "open": 90, "high": 110, "low": 85, "close": 100, "volume": 1000}]
    )
    fake_st = _FakeStreamlit(toggle_values={f"toggle_chart_{preview.name}_{preview.symbol}_{preview.path.name}": True})
    monkeypatch.setattr(streamlit_data_module, "st", fake_st)

    professional_calls: list[str] = []
    rendered_frames: list[pd.DataFrame] = []

    monkeypatch.setattr(
        streamlit_data_module,
        "load_professional_chart_frame_for_symbol",
        lambda _service, symbol: professional_calls.append(symbol) or professional_frame,
    )
    monkeypatch.setattr(
        streamlit_data_module,
        "render_chart_selector",
        lambda frame, dataset_name, key_prefix, height: rendered_frames.append(frame),
    )

    streamlit_data_module.render_dataset_detail(preview, fallback_frame, DashboardDataService())

    assert professional_calls == ["005930"]
    assert rendered_frames == [professional_frame]


def test_render_dataset_detail_keeps_investor_daily_generic_and_skips_professional_helper(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    preview = _make_dataset_preview("investor_daily", "005930", "삼성전자", "005930_investor.csv")
    frame = pd.DataFrame([{"date": "2026-06-24", "frgn_ntby_qty": 100, "orgn_ntby_qty": -20}])
    fake_st = _FakeStreamlit(toggle_values={f"toggle_chart_{preview.name}_{preview.symbol}_{preview.path.name}": True})
    monkeypatch.setattr(streamlit_data_module, "st", fake_st)

    helper_calls: list[str] = []
    rendered_frames: list[pd.DataFrame] = []

    monkeypatch.setattr(
        streamlit_data_module,
        "load_professional_chart_frame_for_symbol",
        lambda _service, symbol: helper_calls.append(symbol) or frame,
    )
    monkeypatch.setattr(
        streamlit_data_module,
        "render_chart_selector",
        lambda frame, dataset_name, key_prefix, height: rendered_frames.append(frame),
    )

    streamlit_data_module.render_dataset_detail(preview, frame, DashboardDataService())

    assert helper_calls == []
    assert rendered_frames == [frame]



def test_load_professional_chart_frame_for_symbol_prefers_indicators_and_merges_investor_flow() -> None:
    service = DashboardDataService(
        dataset_storage=_FakeDatasetStorage(
            {
                ("daily_prices_indicators", "005930"): (
                    "005930_20260630.csv",
                    pd.DataFrame(
                        [
                            {"date": "2026-06-29", "open": 98, "high": 101, "low": 96, "close": 100, "ma_5": 95},
                            {"date": "2026-06-30", "open": 105, "high": 112, "low": 104, "close": 110, "ma_5": 97},
                        ]
                    ),
                ),
                ("investor_daily", "005930"): (
                    "005930_20260630.csv",
                    pd.DataFrame(
                        [
                            {"stck_bsop_date": "20260629", "frgn_ntby_qty": 10, "orgn_ntby_qty": -3, "prsn_ntby_qty": -7},
                            {"stck_bsop_date": "20260630", "frgn_ntby_qty": 12, "orgn_ntby_qty": -4, "prsn_ntby_qty": -8},
                        ]
                    ),
                ),
            }
        )
    )

    frame = load_professional_chart_frame_for_symbol(service, "005930")

    assert frame is not None
    assert frame["date"].dt.strftime("%Y-%m-%d").tolist() == ["2026-06-29", "2026-06-30"]
    assert frame[["frgn_ntby_qty", "orgn_ntby_qty", "prsn_ntby_qty"]].to_dict("records") == [
        {"frgn_ntby_qty": 10, "orgn_ntby_qty": -3, "prsn_ntby_qty": -7},
        {"frgn_ntby_qty": 12, "orgn_ntby_qty": -4, "prsn_ntby_qty": -8},
    ]


def test_load_professional_chart_frame_for_symbol_backfills_volume_from_daily_prices_when_indicator_base_lacks_it() -> None:
    service = DashboardDataService(
        dataset_storage=_FakeDatasetStorage(
            {
                ("daily_prices_indicators", "005930"): (
                    "005930_20260630.csv",
                    pd.DataFrame(
                        [
                            {"date": "2026-06-29", "open": 98, "high": 101, "low": 96, "close": 100, "ma_5": 95},
                            {"date": "2026-06-30", "open": 105, "high": 112, "low": 104, "close": 110, "ma_5": 97},
                        ]
                    ),
                ),
                ("daily_prices", "005930"): (
                    "005930_20260601_20260630.csv",
                    pd.DataFrame(
                        [
                            {
                                "stck_bsop_date": "20260629",
                                "stck_oprc": "98",
                                "stck_hgpr": "101",
                                "stck_lwpr": "96",
                                "stck_clpr": "100",
                                "acml_vol": "12345",
                            },
                            {
                                "stck_bsop_date": "20260630",
                                "stck_oprc": "105",
                                "stck_hgpr": "112",
                                "stck_lwpr": "104",
                                "stck_clpr": "110",
                                "acml_vol": "23456",
                            },
                        ]
                    ),
                ),
            }
        )
    )

    frame = load_professional_chart_frame_for_symbol(service, "005930")

    assert frame is not None
    assert frame["volume"].tolist() == [12345, 23456]


def test_load_professional_chart_frame_for_symbol_falls_back_to_normalized_daily_prices_when_indicator_base_lacks_ohlc() -> None:
    service = DashboardDataService(
        dataset_storage=_FakeDatasetStorage(
            {
                ("daily_prices_indicators", "005930"): (
                    "005930_20260630.csv",
                    pd.DataFrame([{"date": "2026-06-30", "close": 110, "ma_5": 97}]),
                ),
                ("daily_prices", "005930"): (
                    "005930_20260601_20260630.csv",
                    pd.DataFrame(
                        [
                            {
                                "stck_bsop_date": "20260630",
                                "stck_oprc": "101",
                                "stck_hgpr": "115",
                                "stck_lwpr": "99",
                                "stck_clpr": "110",
                                "acml_vol": "12345",
                            }
                        ]
                    ),
                ),
                ("investor_daily", "005930"): (
                    "005930_20260630.csv",
                    pd.DataFrame([{"stck_bsop_date": "20260630", "foreign_net": 25}]),
                ),
            }
        )
    )

    frame = load_professional_chart_frame_for_symbol(service, "005930")

    assert frame is not None
    assert frame["date"].dt.strftime("%Y-%m-%d").tolist() == ["2026-06-30"]
    assert frame.loc[0, "open"] == 101
    assert frame.loc[0, "high"] == 115
    assert frame.loc[0, "low"] == 99
    assert frame.loc[0, "close"] == 110
    assert frame.loc[0, "volume"] == 12345
    assert frame.loc[0, "foreign_net"] == 25


def test_load_professional_chart_frame_for_symbol_returns_base_without_flow_columns_when_investor_missing() -> None:
    service = DashboardDataService(
        dataset_storage=_FakeDatasetStorage(
            {
                ("daily_prices_indicators", "005930"): (
                    "005930_20260630.csv",
                    pd.DataFrame([{"date": "2026-06-30", "open": 105, "high": 112, "low": 104, "close": 110, "ma_5": 97}]),
                ),
            }
        )
    )

    frame = load_professional_chart_frame_for_symbol(service, "005930")

    assert frame is not None
    assert "frgn_ntby_qty" not in frame.columns
    assert "orgn_ntby_qty" not in frame.columns
    assert "prsn_ntby_qty" not in frame.columns
    assert frame.columns.tolist() == ["date", "open", "high", "low", "close", "ma_5"]


def test_load_professional_chart_frame_for_symbol_treats_all_null_flow_columns_as_absent() -> None:
    service = DashboardDataService(
        dataset_storage=_FakeDatasetStorage(
            {
                ("daily_prices_indicators", "005930"): (
                    "005930_20260630.csv",
                    pd.DataFrame([{"date": "2026-06-30", "open": 105, "high": 112, "low": 104, "close": 110, "ma_5": 97}]),
                ),
                ("investor_daily", "005930"): (
                    "005930_20260630.csv",
                    pd.DataFrame([{"stck_bsop_date": "20260630", "frgn_ntby_qty": None, "orgn_ntby_qty": None, "prsn_ntby_qty": None}]),
                ),
            }
        )
    )

    frame = load_professional_chart_frame_for_symbol(service, "005930")

    assert frame is not None
    assert "frgn_ntby_qty" not in frame.columns
    assert "orgn_ntby_qty" not in frame.columns
    assert "prsn_ntby_qty" not in frame.columns


def test_load_professional_chart_frame_for_symbol_returns_none_when_indicator_lacks_ohlc_and_daily_prices_missing() -> None:
    service = DashboardDataService(
        dataset_storage=_FakeDatasetStorage(
            {
                ("daily_prices_indicators", "005930"): (
                    "005930_20260630.csv",
                    pd.DataFrame([{"date": "2026-06-30", "close": 110, "ma_5": 97}]),
                ),
            }
        )
    )

    assert load_professional_chart_frame_for_symbol(service, "005930") is None


def test_refresh_favorite_symbols_bootstraps_missing_data_and_runs_pipeline() -> None:
    service = DashboardDataService(dataset_storage=_FakeDatasetStorage({}))
    collect_calls: list[tuple[str, date, date]] = []
    analyzed: list[str] = []
    signaled: list[str] = []
    reported: list[str] = []

    result = refresh_favorite_symbols_if_needed(
        service,
        {"005930"},
        today=date(2026, 6, 29),
        collect_callback=lambda symbol, start_date, end_date: collect_calls.append((symbol, start_date, end_date)) or True,
        analyze_callback=lambda symbol: analyzed.append(symbol),
        signal_callback=lambda symbol: signaled.append(symbol),
        report_callback=lambda symbol: reported.append(symbol),
    )

    assert collect_calls == [("005930", date(2025, 6, 29), date(2026, 6, 29))]
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
    collect_calls: list[tuple[str, date, date]] = []
    pipeline_calls: list[str] = []

    result = refresh_favorite_symbols_if_needed(
        service,
        {"005930"},
        today=date(2026, 6, 29),
        collect_callback=lambda symbol, start_date, end_date: collect_calls.append((symbol, start_date, end_date)) or True,
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
    collect_calls: list[tuple[str, date, date]] = []
    pipeline_calls: list[str] = []

    result = refresh_favorite_symbols_if_needed(
        service,
        {"005930"},
        today=date(2026, 6, 29),
        collect_callback=lambda symbol, start_date, end_date: collect_calls.append((symbol, start_date, end_date)) or True,
        analyze_callback=lambda symbol: pipeline_calls.append(f"analyze:{symbol}"),
        signal_callback=lambda symbol: pipeline_calls.append(f"signal:{symbol}"),
        report_callback=lambda symbol: pipeline_calls.append(f"report:{symbol}"),
    )

    assert collect_calls == [("005930", date(2026, 6, 28), date(2026, 6, 29))]
    assert pipeline_calls == ["analyze:005930", "signal:005930", "report:005930"]
    assert result["collected_symbols"] == ["005930"]
    assert result["pipeline_symbols"] == ["005930"]

def test_render_watchlist_tab_shows_info_when_no_favorites(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_st = _FakeStreamlit()
    monkeypatch.setattr(streamlit_watchlist_module, "st", fake_st)
    snapshot = SimpleNamespace(processed_previews=[_make_report_preview("005930", "삼성전자", "005930_20260624.csv")])
    store = _make_favorites_store("watchlist_no_favorites")

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
    store = _make_favorites_store("watchlist_selected")
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
        settings=AppSettings(),
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
    monkeypatch.setattr(streamlit_reports_module, "load_professional_chart_frame_for_symbol", lambda *_args, **_kwargs: None)

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
        favorites_store=_make_favorites_store("reports_metrics"),
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
        from invest_bot.config.settings import AppSettings
        from invest_bot.dashboard.streamlit_actions import render_actions_tab
        from invest_bot.market.symbol_lookup import SymbolEntry

        render_actions_tab(
            SimpleNamespace(list_entries=lambda: [SymbolEntry(symbol="005930", symbol_name="삼성전자")]),
            schedule_status=None,
            settings=AppSettings(),
            render_schedule_status_panel=lambda _: None,
        )

    def render_reports_smoke() -> None:
        from types import SimpleNamespace
        import pandas as pd
        from pathlib import Path
        from invest_bot.dashboard.service import DashboardDataService
        from invest_bot.dashboard.report_favorites import ReportFavoritesStore
        import invest_bot.dashboard.streamlit_reports as streamlit_reports_module
        from invest_bot.dashboard.streamlit_reports import render_reports_tab
        from invest_bot.dashboard.service import DatasetPreview
        from invest_bot.db.engine import build_engine, build_session_factory
        from invest_bot.db.repositories import SqlAlchemyReportFavoriteSymbolRepository
        from tests.helpers import init_test_db, make_test_dir

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
        test_dir = make_test_dir("reports_smoke_apptest")
        database_url = f"sqlite+pysqlite:///{(test_dir / 'favorites.db').as_posix()}"
        init_test_db(database_url)
        favorites_store = ReportFavoritesStore(
            SqlAlchemyReportFavoriteSymbolRepository(build_session_factory(build_engine(database_url)))
        )
        streamlit_reports_module.load_professional_chart_frame_for_symbol = lambda *_args, **_kwargs: None
        render_reports_tab(
            SimpleNamespace(processed_previews=[preview]),
            DashboardDataService(),
            read_preview_frame=lambda _: frame,
            load_indicator_frame_for_symbol=lambda _: frame,
            favorites_store=favorites_store,
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


def test_summarize_report_delivery_results_returns_warning_for_partial_delivery() -> None:
    items = [ResolvedSymbol(raw_input="005930", symbol="005930", symbol_name="삼성전자")]

    message, message_type = summarize_report_delivery_results(
        [
            {
                "symbol": "005930",
                "delivery": {
                    "status": "skipped",
                    "channel": "discord",
                    "message": "payload",
                    "error_detail": "Discord webhook URL is not configured.",
                },
            }
        ],
        selected_items=items,
        action_name="시장 리포트 생성",
    )

    assert message_type == "warning"
    assert message == "시장 리포트 생성 완료(1건). Discord 전송 경고: 삼성전자 (005930) skipped(웹훅 미설정)"


def test_describe_delivery_problems_formats_failed_and_skipped_symbols() -> None:
    items = [
        ResolvedSymbol(raw_input="005930", symbol="005930", symbol_name="삼성전자"),
        ResolvedSymbol(raw_input="000660", symbol="000660", symbol_name="SK하이닉스"),
    ]

    problems = describe_delivery_problems(
        [
            {"symbol": "005930", "delivery": {"status": "skipped", "error_detail": "Discord webhook URL is not configured."}},
            {"symbol": "000660", "delivery": {"status": "failed", "error_detail": "HTTP 500"}},
        ],
        selected_items=items,
    )

    assert problems == [
        "삼성전자 (005930) skipped(웹훅 미설정)",
        "SK하이닉스 (000660) failed(HTTP 500)",
    ]


def test_normalize_delivery_detail_translates_missing_webhook_warning() -> None:
    assert normalize_delivery_detail("skipped", "Discord webhook URL is not configured.") == "웹훅 미설정"
    assert normalize_delivery_detail("failed", "HTTP 500") == "HTTP 500"


def test_run_market_report_batch_action_sets_warning_message_for_delivery_issue(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_st = _FakeStreamlit()
    monkeypatch.setattr(streamlit_actions_module, "st", fake_st)
    monkeypatch.setattr(
        streamlit_actions_module,
        "generate_market_report_for_symbol",
        lambda symbol, **kwargs: {
            "symbol": symbol,
            "delivery": {
                "status": "skipped",
                "channel": "discord",
                "message": "payload",
                "error_detail": "Discord webhook URL is not configured.",
            },
        },
    )

    run_market_report_batch_action(
        [ResolvedSymbol(raw_input="005930", symbol="005930", symbol_name="삼성전자")],
        settings=AppSettings(),
    )

    assert fake_st.session_state["action_message_type"] == "warning"
    assert "Discord 전송 경고" in fake_st.session_state["action_message"]


def test_run_full_pipeline_action_sets_warning_message_for_partial_delivery(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_st = _FakeStreamlit()
    monkeypatch.setattr(streamlit_actions_module, "st", fake_st)
    monkeypatch.setattr(
        streamlit_actions_module,
        "collect_market_data_for_symbols",
        lambda symbols, days: {
            "successful_symbols": ["005930"],
            "failed_count": 0,
            "symbol_count": 1,
        },
    )
    monkeypatch.setattr(streamlit_actions_module, "generate_indicators_for_symbol", lambda symbol: None)
    monkeypatch.setattr(streamlit_actions_module, "generate_golden_cross_signals_for_symbol", lambda symbol: None)
    monkeypatch.setattr(
        streamlit_actions_module,
        "generate_market_report_for_symbol",
        lambda symbol, **kwargs: {
            "symbol": symbol,
            "delivery": {
                "status": "failed",
                "channel": "discord",
                "message": "payload",
                "error_detail": "HTTP 500",
            },
        },
    )

    run_full_pipeline_action(
        [ResolvedSymbol(raw_input="005930", symbol="005930", symbol_name="삼성전자")],
        30,
        settings=AppSettings(),
    )

    assert fake_st.session_state["action_message_type"] == "warning"
    assert "전체 파이프라인 완료(1건). Discord 전송 경고: 삼성전자 (005930) failed(HTTP 500)" == fake_st.session_state["action_message"]


def test_run_full_pipeline_action_stops_when_collection_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_st = _FakeStreamlit()
    called: list[str] = []
    monkeypatch.setattr(streamlit_actions_module, "st", fake_st)
    monkeypatch.setattr(
        streamlit_actions_module,
        "collect_market_data_for_symbols",
        lambda symbols, days: {
            "successful_symbols": [],
            "failed_count": 1,
            "symbol_count": 1,
        },
    )
    monkeypatch.setattr(streamlit_actions_module, "generate_indicators_for_symbol", lambda symbol: called.append("indicators"))
    monkeypatch.setattr(streamlit_actions_module, "generate_golden_cross_signals_for_symbol", lambda symbol: called.append("signals"))
    monkeypatch.setattr(streamlit_actions_module, "generate_market_report_for_symbol", lambda symbol, **kwargs: called.append("report"))

    run_full_pipeline_action(
        [ResolvedSymbol(raw_input="005930", symbol="005930", symbol_name="삼성전자")],
        30,
        settings=AppSettings(),
    )

    assert called == []
    assert fake_st.session_state["action_message_type"] == "error"
    assert "리포트를 갱신하지 않았습니다" in fake_st.session_state["action_message"]


def test_render_action_feedback_uses_warning_channel(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_st = _FakeStreamlit()
    fake_st.session_state["action_message"] = "경고 메시지"
    fake_st.session_state["action_message_type"] = "warning"
    monkeypatch.setattr(streamlit_layout_module, "st", fake_st)

    streamlit_layout_module.render_action_feedback()

    assert fake_st.warning_messages == ["경고 메시지"]
    assert fake_st.info_messages == []


def test_streamlit_dashboard_main_builds_settings_once_and_injects_them(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_st = _FakeStreamlit()
    fake_st.session_state["selected_tab"] = "작업 실행"
    settings = AppSettings(discord_webhook_url="https://discord.example/webhook")
    captured: dict[str, object] = {}

    monkeypatch.setattr(streamlit_dashboard_module, "st", fake_st)
    monkeypatch.setattr(streamlit_dashboard_module, "_apply_custom_style", lambda: None)
    monkeypatch.setattr(streamlit_dashboard_module, "_render_sidebar", lambda *args, **kwargs: None)
    monkeypatch.setattr(streamlit_dashboard_module, "_render_header", lambda: None)
    monkeypatch.setattr(streamlit_dashboard_module, "_render_action_feedback", lambda: None)
    monkeypatch.setattr(streamlit_dashboard_module, "_load_optional_schedule_status", lambda: None)
    monkeypatch.setattr(streamlit_dashboard_module, "_read_preview_frame", lambda service, preview: None)
    monkeypatch.setattr(streamlit_dashboard_module, "_load_indicator_frame_for_symbol", lambda service, symbol: None)
    monkeypatch.setattr(streamlit_dashboard_module, "_render_schedule_status_panel", lambda *args, **kwargs: None)
    monkeypatch.setattr(streamlit_dashboard_module, "SymbolLookup", lambda: SimpleNamespace())
    monkeypatch.setattr(
        streamlit_dashboard_module.AppSettings,
        "from_file",
        classmethod(lambda cls: settings),
    )

    class _FakeService:
        def __init__(self, *, settings):
            captured["service_settings"] = settings

        def build_snapshot(self):
            return SimpleNamespace()

        def load_test_report(self):
            return None

    monkeypatch.setattr(streamlit_dashboard_module, "DashboardDataService", _FakeService)
    monkeypatch.setattr(
        streamlit_dashboard_module,
        "_render_actions_tab",
        lambda symbol_lookup, schedule_status, *, settings, render_schedule_status_panel: captured.update(
            {
                "actions_settings": settings,
                "symbol_lookup": symbol_lookup,
            }
        ),
    )

    streamlit_dashboard_module.main()

    assert captured["service_settings"] is settings
    assert captured["actions_settings"] is settings


def test_interpretation_rows_show_stock_and_strategy_labels() -> None:
    service = DashboardDataService()
    entries = [
        {
            "symbol": "005930",
            "symbol_name": "삼성전자",
            "frame": pd.DataFrame(
                [
                    {
                        "date": "2026-06-24",
                        "final_opinion": "buy",
                        "trend_state": "bullish",
                        "golden_cross_signal": "buy",
                        "rsi_strategy_signal": "hold",
                        "trend_filter_signal": "buy",
                        "mean_reversion_signal": "hold",
                        "rsi_state": "strong",
                        "volume_state": "active",
                        "investor_flow": "supportive",
                        "summary": "raw summary",
                    }
                ]
            ),
        }
    ]

    rows = build_interpretation_rows(entries, service)

    assert rows == [
        {
            "종목": "삼성전자 (005930)",
            "날짜": "2026-06-24",
            "최종 의견": "매수 관점",
            "추세": "상승 우세",
            "골든크로스": "매수 관점",
            "RSI 전략": "관망",
            "추세필터": "매수 관점",
            "평균회귀": "관망",
            "수급": "수급 우호적",
            "한 줄 해석": "추세는 상승 우세이고, 골든크로스 신호는 매수 관점이며, RSI 상태는 강한 흐름, 거래량은 거래 활발, 수급은 수급 우호적입니다.",
        }
    ]
    assert count_buy_strategy_signals(rows[0]) == 2


def test_interpretation_filter_matches_any_strategy_signal_label() -> None:
    entries = [
        {
            "display_opinion": "관망",
            "frame": pd.DataFrame([{"golden_cross_signal": "hold", "rsi_strategy_signal": "buy"}]),
        },
        {
            "display_opinion": "매수 관점",
            "frame": pd.DataFrame([{"golden_cross_signal": "hold", "rsi_strategy_signal": "hold"}]),
        },
    ]

    by_strategy = filter_interpretation_entries(entries, strategy_filter="매수 관점")
    by_opinion = filter_interpretation_entries(entries, opinion_filter="매수 관점")

    assert by_strategy == [entries[0]]
    assert by_opinion == [entries[1]]


def test_strategy_reason_rows_include_localized_reason() -> None:
    service = DashboardDataService()
    entries = [
        {
            "symbol": "005930",
            "symbol_name": "삼성전자",
            "frame": pd.DataFrame(
                [
                    {
                        "golden_cross_signal": "buy",
                        "golden_cross_reason": "ma_5 crossed above ma_20.",
                    }
                ]
            ),
        }
    ]

    rows = build_strategy_reason_rows(entries, service)

    assert rows[0] == {
        "종목": "삼성전자 (005930)",
        "전략": "골든크로스",
        "판단": "매수 관점",
        "근거": "5일 이동평균선이 20일 이동평균선을 상향 돌파했습니다.",
    }


def test_render_interpretations_tab_renders_overview_table(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_st = _FakeStreamlit()
    monkeypatch.setattr(streamlit_interpretations_module, "st", fake_st)
    previews = [_make_report_preview("005930", "삼성전자", "005930_20260624.csv")]
    frame = pd.DataFrame(
        [
            {
                "date": "2026-06-24",
                "symbol_name": "삼성전자",
                "final_opinion": "buy",
                "trend_state": "bullish",
                "golden_cross_signal": "buy",
                "rsi_strategy_signal": "hold",
                "trend_filter_signal": "buy",
                "mean_reversion_signal": "hold",
                "rsi_state": "strong",
                "volume_state": "active",
                "investor_flow": "supportive",
                "summary": "a",
            }
        ]
    )

    streamlit_interpretations_module.render_interpretations_tab(
        SimpleNamespace(processed_previews=previews),
        DashboardDataService(),
        read_preview_frame=lambda preview: frame,
    )

    assert "해석 모아보기" in "".join(fake_st.markdown_calls)
    assert "표시 종목" in [label for label, _ in fake_st.metric_calls]
    assert fake_st.dataframe_calls == 2
