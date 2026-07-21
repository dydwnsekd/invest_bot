from __future__ import annotations

from functools import partial

import streamlit as st

from invest_bot.config.settings import AppSettings
from invest_bot.dashboard.service import DashboardDataService
from invest_bot.dashboard.streamlit_actions import render_actions_tab as _render_actions_tab
from invest_bot.dashboard.streamlit_backtest import render_backtest_tab as _render_backtest_tab
from invest_bot.dashboard.streamlit_data import render_data_tab as _render_data_tab
from invest_bot.dashboard.streamlit_layout import (
    render_action_feedback as _render_action_feedback,
    render_header as _render_header,
    render_sidebar as _render_sidebar,
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
from invest_bot.dashboard.streamlit_watchlist import render_watchlist_tab as _render_watchlist_tab
from invest_bot.market.symbol_lookup import SymbolLookup


APP_TITLE = "invest_bot admin"

def main() -> None:
    st.set_page_config(
        page_title=APP_TITLE,
        page_icon=":material/query_stats:",
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
        st.session_state.selected_tab = "상태판"
    if "action_message" not in st.session_state:
        st.session_state.action_message = None
    if "action_message_type" not in st.session_state:
        st.session_state.action_message_type = "info"

    _render_sidebar(service, schedule_status)
    _render_header()
    _render_action_feedback()

    tab = st.session_state.selected_tab
    if tab == "상태판":
        _render_overview_tab(snapshot, service, test_report, schedule_status, read_preview_frame=read_preview_frame)
    elif tab == "작업 실행":
        _render_actions_tab(
            symbol_lookup,
            schedule_status,
            settings=settings,
            render_schedule_status_panel=_render_schedule_status_panel,
        )
    elif tab == "리포트 해석":
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
    elif tab == "데이터 탐색":
        _render_data_tab(snapshot, service, read_preview_frame=read_preview_frame)
    else:
        _render_test_tab(test_report)
