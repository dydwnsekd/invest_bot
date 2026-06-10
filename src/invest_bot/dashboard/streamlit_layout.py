from __future__ import annotations

from html import escape

import streamlit as st

from invest_bot.dashboard.service import DashboardDataService


TAB_NAMES = ("상태판", "작업 실행", "리포트 해석", "데이터 탐색", "검증")


def render_sidebar(service: DashboardDataService, schedule_status) -> None:
    with st.sidebar:
        st.markdown("## invest_bot")
        st.caption("수집, 분석, 신호, 리포트를 하나의 운영 화면에서 확인합니다.")
        st.markdown('<div class="sidebar-nav-title">화면 이동</div>', unsafe_allow_html=True)
        for tab_name in TAB_NAMES:
            button_type = "primary" if st.session_state.selected_tab == tab_name else "secondary"
            if st.button(tab_name, width="stretch", type=button_type, key=f"nav_{tab_name}"):
                st.session_state.selected_tab = tab_name
                st.rerun()

        st.divider()
        st.markdown(
            f"""
            <div class="sidebar-info-card">
              <div class="sidebar-info-title">데이터 위치</div>
              <div class="sidebar-info-label">원본 데이터</div>
              <div class="sidebar-info-value">{escape(str(service.raw_root))}</div>
              <div class="sidebar-info-label">분석 데이터</div>
              <div class="sidebar-info-value">{escape(str(service.processed_root))}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        if schedule_status is not None:
            st.markdown(
                f"""
                <div class="sidebar-info-card">
                  <div class="sidebar-info-title">정기 수집 상태</div>
                  <div class="sidebar-info-label">대상 종목 수</div>
                  <div class="sidebar-info-value">{len(schedule_status.schedule.symbols)}개</div>
                  <div class="sidebar-info-label">수집 주기</div>
                  <div class="sidebar-info-value">{schedule_status.schedule.interval_minutes}분</div>
                </div>
                """,
                unsafe_allow_html=True,
            )


def render_header() -> None:
    st.markdown(
        """
        <div class="hero-shell">
          <div class="eyebrow">Streamlit 운영 화면</div>
          <h1 class="hero-title">국내주식 운영 대시보드</h1>
          <div class="hero-copy">
            지금 상태를 빠르게 파악하고, 필요한 작업을 실행한 뒤, 리포트와 데이터를 자연스럽게 이어서 확인할 수 있도록 화면 흐름을 정리한 Streamlit 운영 화면입니다.
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_action_feedback() -> None:
    message = st.session_state.get("action_message")
    if not message:
        return

    message_type = st.session_state.get("action_message_type", "info")
    if message_type == "success":
        st.success(message)
    elif message_type == "error":
        st.error(message)
    else:
        st.info(message)
