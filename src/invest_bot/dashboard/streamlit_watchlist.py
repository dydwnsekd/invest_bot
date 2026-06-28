from __future__ import annotations

from collections.abc import Callable

import pandas as pd
import streamlit as st

from invest_bot.dashboard.report_favorites import ReportFavoritesStore
from invest_bot.dashboard.service import DashboardDataService
from invest_bot.dashboard.streamlit_reports import (
    build_report_entries,
    format_report_selection_option,
    get_report_entry_by_key,
    query_report_previews,
    render_market_report_card,
    resolve_selected_report_key,
    selected_entry_key_index,
    sort_report_entries,
)


WATCHLIST_SELECTION_KEY = "watchlist_selected_entry_key"
WATCHLIST_SORT_OPTION_KEY = "watchlist_sort_option"


def render_watchlist_tab(
    snapshot,
    service: DashboardDataService,
    *,
    read_preview_frame: Callable[[object], pd.DataFrame],
    load_indicator_frame_for_symbol: Callable[[str], pd.DataFrame | None],
    favorites_store: ReportFavoritesStore | None = None,
) -> None:
    st.markdown('<h3 class="section-title">관심종목</h3>', unsafe_allow_html=True)
    st.markdown(
        '<div class="section-copy">저장해 둔 관심종목만 모아서 최신 리포트와 차트를 빠르게 다시 확인할 수 있습니다.</div>',
        unsafe_allow_html=True,
    )

    favorites_store = favorites_store or ReportFavoritesStore()
    favorite_symbols = favorites_store.load_symbols()
    if not favorite_symbols:
        st.info("아직 저장된 관심종목이 없습니다. `리포트 해석` 탭에서 관심종목을 추가해 보세요.")
        return

    report_previews = [preview for preview in snapshot.processed_previews if preview.name == "market_reports"]
    favorite_previews = [preview for preview in report_previews if preview.symbol in favorite_symbols]
    if not favorite_previews:
        st.info("저장된 관심종목과 연결되는 최신 시장 리포트가 아직 없습니다.")
        return

    query = st.text_input(
        "관심종목 검색",
        placeholder="종목코드 또는 종목명으로 찾기",
        key="watchlist_query",
    ).strip().lower()
    visible_previews = query_report_previews(favorite_previews, query)
    entries = build_report_entries(
        visible_previews,
        service,
        read_preview_frame=read_preview_frame,
        favorite_symbols=favorite_symbols,
    )

    sort_option = st.selectbox(
        "정렬",
        options=["즐겨찾기 우선", "최신순", "종목명순", "매수 관점 우선"],
        index=["즐겨찾기 우선", "최신순", "종목명순", "매수 관점 우선"].index(
            str(st.session_state.get(WATCHLIST_SORT_OPTION_KEY, "즐겨찾기 우선"))
        )
        if str(st.session_state.get(WATCHLIST_SORT_OPTION_KEY, "즐겨찾기 우선"))
        in {"즐겨찾기 우선", "최신순", "종목명순", "매수 관점 우선"}
        else 0,
        key=WATCHLIST_SORT_OPTION_KEY,
    )
    visible_entries = sort_report_entries(entries, sort_option)

    metric_columns = st.columns(3)
    metric_columns[0].metric("저장된 관심종목", len(favorite_symbols))
    metric_columns[1].metric("현재 후보", len(visible_entries))
    metric_columns[2].metric("매수 관점", sum(1 for item in visible_entries if item["final_opinion"] == "buy"))

    if not visible_entries:
        st.warning("현재 검색 조건에 맞는 관심종목 리포트가 없습니다.")
        return

    selected_entry_key = resolve_selected_report_key(
        visible_entries,
        st.session_state.get(WATCHLIST_SELECTION_KEY),
    )
    selected_key = st.selectbox(
        "관심종목 선택",
        options=[str(entry["entry_key"]) for entry in visible_entries],
        index=selected_entry_key_index(visible_entries, selected_entry_key),
        format_func=lambda entry_key: format_report_selection_option(visible_entries, entry_key),
        key=WATCHLIST_SELECTION_KEY,
    )
    selected_entry = get_report_entry_by_key(visible_entries, selected_key)

    st.caption(f"저장된 관심종목 {len(visible_entries)}건 중 선택한 1건만 본문에 표시합니다.")
    render_market_report_card(
        selected_entry["preview"],
        service,
        frame=selected_entry["frame"],
        read_preview_frame=read_preview_frame,
        load_indicator_frame_for_symbol=load_indicator_frame_for_symbol,
        favorites_store=favorites_store,
        is_favorite=bool(selected_entry["is_favorite"]),
    )
