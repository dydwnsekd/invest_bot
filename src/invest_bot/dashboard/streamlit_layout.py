from __future__ import annotations

from html import escape

import streamlit as st

from invest_bot.dashboard.service import DashboardDataService


TAB_META = {
    "홈": {
        "eyebrow": "오늘의 투자 작업실",
        "title": "무엇을 먼저 보면 좋을까요?",
        "copy": "데이터 상태, 최신 리포트, 신호, 다음 실행 작업을 한 화면에서 이어서 확인합니다.",
    },
    "데이터 갱신": {
        "eyebrow": "수집 · 분석 실행",
        "title": "데이터를 최신 상태로 갱신합니다",
        "copy": "종목을 고르고 조회 기간을 선택한 뒤 수집, 지표 계산, 신호 생성, 리포트 생성을 실행합니다.",
    },
    "투자 리포트": {
        "eyebrow": "해석 · 근거 확인",
        "title": "종목별 판단과 이유를 읽습니다",
        "copy": "최종 의견, 전략별 판단, 차트, 상세 데이터를 한 종목씩 집중해서 확인합니다.",
    },
    "관심종목": {
        "eyebrow": "저장한 종목",
        "title": "관심종목만 빠르게 다시 봅니다",
        "copy": "리포트에서 저장한 종목을 모아 최신 판단과 차트를 다시 확인합니다.",
    },
    "백테스트": {
        "eyebrow": "전략 검증",
        "title": "전략이 과거에 어떻게 움직였는지 검증합니다",
        "copy": "선택한 종목과 전략의 준비 상태를 확인하고 수익률, 거래 로그, 비교표를 봅니다.",
    },
    "데이터 보기": {
        "eyebrow": "원본 · 가공 데이터",
        "title": "숫자와 원본 데이터를 확인합니다",
        "copy": "종목별 데이터셋을 요약부터 보고 필요한 경우 차트, 표, 컬럼 설명까지 내려갑니다.",
    },
    "용어 해설": {
        "eyebrow": "쉬운 설명",
        "title": "낯선 용어를 바로 이해합니다",
        "copy": "리포트, 전략, 지표, 수급, 데이터 용어를 검색하고 읽는 법을 확인합니다.",
    },
    "시스템 검증": {
        "eyebrow": "테스트 상태",
        "title": "시스템이 정상인지 확인합니다",
        "copy": "저장된 테스트 결과와 실패 항목을 확인해 운영 화면의 신뢰도를 점검합니다.",
    },
}

TAB_NAMES = tuple(TAB_META.keys())
TAB_ALIASES = {
    "상태판": "홈",
    "작업 실행": "데이터 갱신",
    "리포트 해석": "투자 리포트",
    "데이터 탐색": "데이터 보기",
    "검증": "시스템 검증",
}


def resolve_tab_name(tab_name: str | None) -> str:
    resolved = TAB_ALIASES.get(str(tab_name), str(tab_name))
    return resolved if resolved in TAB_META else "홈"


def render_sidebar(service: DashboardDataService, schedule_status) -> None:
    st.session_state.selected_tab = resolve_tab_name(st.session_state.get("selected_tab"))
    with st.sidebar:
        st.markdown("## invest_bot")
        st.caption("데이터 갱신부터 투자 리포트, 백테스트까지 한 흐름으로 확인합니다.")
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


def render_header(selected_tab: str | None = None) -> None:
    tab_name = resolve_tab_name(selected_tab or st.session_state.get("selected_tab"))
    meta = TAB_META[tab_name]
    st.markdown(
        f"""
        <div class="hero-shell compact-hero">
          <div class="eyebrow">{escape(meta["eyebrow"])}</div>
          <h1 class="hero-title">{escape(meta["title"])}</h1>
          <div class="hero-copy">{escape(meta["copy"])}</div>
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
    elif message_type == "warning":
        st.warning(message)
    elif message_type == "error":
        st.error(message)
    else:
        st.info(message)
