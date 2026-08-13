from __future__ import annotations

from contextlib import nullcontext
from functools import partial

import streamlit as st

from invest_bot.config.settings import AppSettings
from invest_bot.dashboard.report_favorites import ReportFavoritesStore
from invest_bot.dashboard.service import DashboardDataService
from invest_bot.dashboard.streamlit_actions import render_actions_tab as _render_actions_tab
from invest_bot.dashboard.streamlit_backtest import render_backtest_tab as _render_backtest_tab
from invest_bot.dashboard.streamlit_data import render_data_tab as _render_data_tab
from invest_bot.dashboard.streamlit_glossary import render_glossary_tab as _render_glossary_tab
from invest_bot.dashboard.streamlit_layout import (
    read_tab_from_query_params as _read_tab_from_query_params,
    render_action_feedback as _render_action_feedback,
    render_header as _render_header,
    render_sidebar as _render_sidebar,
    resolve_tab_name as _resolve_tab_name,
    sync_tab_to_query_params as _sync_tab_to_query_params,
)
from invest_bot.dashboard.streamlit_overview import (
    render_overview_tab as _render_overview_tab,
    render_schedule_status_panel as _render_schedule_status_panel,
)
from invest_bot.dashboard.streamlit_reports import render_reports_tab as _render_reports_tab
from invest_bot.dashboard.streamlit_state import (
    load_indicator_frame_for_symbol as _load_indicator_frame_for_symbol,
    load_optional_schedule_status as _load_optional_schedule_status,
    read_preview_frame as _read_preview_frame,
)
from invest_bot.dashboard.streamlit_styles import apply_custom_style as _apply_custom_style
from invest_bot.dashboard.streamlit_tests import render_test_tab as _render_test_tab
from invest_bot.dashboard.streamlit_watchlist import (
    refresh_favorite_symbols_if_needed as _refresh_favorite_symbols_if_needed,
    render_watchlist_tab as _render_watchlist_tab,
)
from invest_bot.market.symbol_lookup import SymbolLookup


APP_TITLE = "invest_bot admin"

def main() -> None:
    st.set_page_config(
        page_title=APP_TITLE,
        page_icon="📈",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    _apply_custom_style()

    settings = AppSettings.from_file()
    service = DashboardDataService(settings=settings)
    symbol_lookup = SymbolLookup()
    schedule_status = _load_optional_schedule_status()
    read_preview_frame = partial(_read_preview_frame, service)
    load_indicator_frame_for_symbol = partial(_load_indicator_frame_for_symbol, service)

    snapshot = service.build_snapshot()
    test_report = service.load_test_report()

    if "selected_tab" not in st.session_state:
        st.session_state.selected_tab = _read_tab_from_query_params()
    if "action_message" not in st.session_state:
        st.session_state.action_message = None
    if "action_message_type" not in st.session_state:
        st.session_state.action_message_type = "info"

    _render_sidebar(service, schedule_status)
    st.session_state.selected_tab = _resolve_tab_name(st.session_state.get("selected_tab"))
    _sync_tab_to_query_params(st.session_state.selected_tab)
    _render_header(st.session_state.selected_tab)
    _render_action_feedback()

    tab = st.session_state.selected_tab
    if tab == "홈":
        snapshot = _refresh_home_watchlist_snapshot(snapshot, service, settings=settings)
        _render_overview_tab(snapshot, service, test_report, schedule_status, read_preview_frame=read_preview_frame)
    elif tab == "데이터 갱신":
        _render_actions_tab(
            symbol_lookup,
            schedule_status,
            settings=settings,
            render_schedule_status_panel=_render_schedule_status_panel,
        )
    elif tab == "용어 해설":
        _render_glossary_tab(service)
    elif tab == "투자 리포트":
        _render_reports_tab(
            snapshot,
            service,
            read_preview_frame=read_preview_frame,
            load_indicator_frame_for_symbol=load_indicator_frame_for_symbol,
        )
    elif tab == "관심종목":
        _render_watchlist_tab(
            snapshot,
            service,
            read_preview_frame=read_preview_frame,
            load_indicator_frame_for_symbol=load_indicator_frame_for_symbol,
        )
    elif tab == "백테스트":
        _render_backtest_tab(
            snapshot,
            service,
            symbol_lookup=symbol_lookup,
        )
    elif tab == "데이터 보기":
        _render_data_tab(snapshot, service, read_preview_frame=read_preview_frame)
    else:
        _render_test_tab(test_report)


def _refresh_home_watchlist_snapshot(
    snapshot,
    service: DashboardDataService,
    *,
    settings: AppSettings,
    favorites_store: ReportFavoritesStore | None = None,
):
    try:
        store = favorites_store or ReportFavoritesStore(settings=settings)
        favorite_symbols = store.load_symbols()
    except Exception as error:  # noqa: BLE001
        st.warning(f"홈 관심종목 목록을 불러오지 못했습니다: {error}")
        return snapshot

    if not favorite_symbols:
        return snapshot

    status_factory = getattr(st, "status", None)
    status_context = (
        status_factory(
            f"관심종목 최신 데이터를 확인하고 있습니다. 등록 종목 {len(favorite_symbols)}개",
            expanded=True,
        )
        if callable(status_factory)
        else nullcontext(None)
    )
    try:
        with status_context as status:
            write = getattr(st, "write", None)
            if callable(write):
                write("가격·수급 데이터를 확인한 뒤 필요한 종목만 지표, 신호, 리포트 순서로 갱신합니다.")
            refresh_result = _refresh_favorite_symbols_if_needed(service, favorite_symbols)
            updated_symbols = refresh_result["pipeline_symbols"]
            update = getattr(status, "update", None)
            if callable(update):
                if updated_symbols:
                    update(label=f"관심종목 {len(updated_symbols)}개 최신화 완료", state="complete", expanded=False)
                else:
                    update(label="관심종목이 이미 최신 상태입니다.", state="complete", expanded=False)
    except Exception as error:  # noqa: BLE001
        st.warning(f"홈 관심종목 자동 최신화 중 오류가 발생했습니다: {error}")
        return snapshot

    if not refresh_result["collected_symbols"] and not refresh_result["pipeline_symbols"]:
        return snapshot

    return service.build_snapshot()
