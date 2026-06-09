from __future__ import annotations

from html import escape
import re

import pandas as pd
import streamlit as st

from invest_bot.dashboard.service import DashboardDataService, DatasetPreview, TestReportPreview
from invest_bot.jobs.analyze_daily_prices import generate_indicators_for_symbol
from invest_bot.jobs.collect_market_data import collect_market_data_for_symbols
from invest_bot.jobs.run_golden_cross_signals import generate_golden_cross_signals_for_symbol
from invest_bot.jobs.run_market_report import generate_market_report_for_symbol
from invest_bot.jobs.scheduled_collection import load_schedule_status
from invest_bot.market.symbol_lookup import ResolvedSymbol, SymbolLookup


APP_TITLE = "invest_bot admin"
TAB_NAMES = ("상태판", "작업 실행", "리포트 해석", "데이터 탐색", "검증")
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


def main() -> None:
    st.set_page_config(
        page_title=APP_TITLE,
        page_icon=":material/query_stats:",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    _apply_custom_style()

    service = DashboardDataService()
    symbol_lookup = SymbolLookup()
    schedule_status = _load_optional_schedule_status()

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
        _render_overview_tab(snapshot, test_report, schedule_status)
    elif tab == "작업 실행":
        _render_actions_tab(symbol_lookup, schedule_status)
    elif tab == "리포트 해석":
        _render_reports_tab(snapshot, service)
    elif tab == "데이터 탐색":
        _render_data_tab(snapshot, service)
    else:
        _render_test_tab(test_report)


def _apply_custom_style() -> None:
    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;700&family=Noto+Sans+KR:wght@400;500;700&display=swap');

        html, body, [data-testid="stAppViewContainer"] {
            background:
                radial-gradient(circle at top left, rgba(15, 118, 110, 0.12), transparent 28%),
                radial-gradient(circle at top right, rgba(217, 119, 6, 0.10), transparent 24%),
                linear-gradient(180deg, #f7f2e9 0%, #f3ede2 100%);
        }

        [data-testid="stAppViewContainer"],
        [data-testid="stAppViewContainer"] p,
        [data-testid="stAppViewContainer"] div,
        [data-testid="stAppViewContainer"] span,
        [data-testid="stAppViewContainer"] label,
        [data-testid="stAppViewContainer"] h1,
        [data-testid="stAppViewContainer"] h2,
        [data-testid="stAppViewContainer"] h3,
        [data-testid="stAppViewContainer"] h4,
        [data-testid="stAppViewContainer"] h5,
        [data-testid="stAppViewContainer"] h6,
        [data-testid="stAppViewContainer"] button,
        [data-testid="stSidebar"],
        [data-testid="stSidebar"] p,
        [data-testid="stSidebar"] div,
        [data-testid="stSidebar"] span,
        [data-testid="stSidebar"] label,
        [data-testid="stSidebar"] h1,
        [data-testid="stSidebar"] h2,
        [data-testid="stSidebar"] h3,
        [data-testid="stSidebar"] h4,
        [data-testid="stSidebar"] h5,
        [data-testid="stSidebar"] h6,
        [data-testid="stSidebar"] button {
            font-family: "Noto Sans KR", "Space Grotesk", sans-serif;
        }

        .material-symbols-rounded,
        .material-symbols-outlined,
        .material-icons,
        [class*="material-symbols"],
        [data-testid="stExpandSidebarButton"],
        [data-testid="stExpandSidebarButton"] *,
        [data-testid="stSidebarCollapseButton"] span,
        [data-testid="stSidebarNavCollapseButton"] span {
            font-family: "Material Symbols Rounded", "Material Symbols Outlined", "Material Icons" !important;
            font-weight: normal !important;
            font-style: normal !important;
            font-size: 1.25rem !important;
            line-height: 1 !important;
            letter-spacing: normal !important;
            text-transform: none !important;
            display: inline-block !important;
            white-space: nowrap !important;
            word-wrap: normal !important;
            direction: ltr !important;
            -webkit-font-smoothing: antialiased !important;
            font-variation-settings:
                "FILL" 0,
                "wght" 400,
                "GRAD" 0,
                "opsz" 24;
        }

        [data-testid="stSidebar"] {
            background: linear-gradient(180deg, #0f172a 0%, #111827 100%);
        }

        [data-testid="stSidebar"] * {
            color: #f8fafc;
        }

        [data-testid="stSidebar"] .stButton > button {
            width: 100%;
            border-radius: 0.95rem;
            border: 1px solid rgba(148, 163, 184, 0.26);
            background: rgba(30, 41, 59, 0.82);
            color: #f8fafc;
            font-weight: 700;
            box-shadow: none;
            transition: all 0.16s ease;
        }

        [data-testid="stSidebar"] .stButton > button:hover {
            border-color: rgba(45, 212, 191, 0.6);
            background: rgba(51, 65, 85, 0.96);
            color: #ffffff;
        }

        [data-testid="stSidebar"] .stButton > button[kind="primary"] {
            background: linear-gradient(135deg, #14b8a6 0%, #0f766e 100%);
            border-color: rgba(20, 184, 166, 0.65);
            color: #f8fffe;
            box-shadow: 0 10px 24px rgba(15, 118, 110, 0.24);
        }

        [data-testid="stSidebar"] .stButton > button[kind="primary"]:hover {
            background: linear-gradient(135deg, #2dd4bf 0%, #0f766e 100%);
            color: #ffffff;
        }

        .hero-shell {
            padding: 1.4rem 1.6rem;
            border-radius: 1.4rem;
            background: linear-gradient(135deg, rgba(255,250,242,0.96), rgba(255,255,255,0.84));
            border: 1px solid rgba(15, 23, 42, 0.08);
            box-shadow: 0 22px 60px rgba(15, 23, 42, 0.08);
            margin-bottom: 1rem;
        }

        .eyebrow {
            display: inline-flex;
            align-items: center;
            gap: 0.35rem;
            padding: 0.28rem 0.7rem;
            border-radius: 999px;
            font-size: 0.78rem;
            font-weight: 700;
            color: #0f766e;
            background: rgba(15, 118, 110, 0.10);
            margin-bottom: 0.75rem;
        }

        .hero-title {
            font-family: "Space Grotesk", "Noto Sans KR", sans-serif;
            font-size: 2.2rem;
            line-height: 1.05;
            margin: 0;
            color: #111827;
            letter-spacing: -0.04em;
        }

        .hero-copy {
            margin-top: 0.75rem;
            color: #475569;
            font-size: 0.98rem;
        }

        .streamlit-card {
            padding: 1rem 1rem 0.85rem 1rem;
            border-radius: 1.1rem;
            background: rgba(255, 252, 247, 0.96);
            border: 1px solid rgba(15, 23, 42, 0.08);
            box-shadow: 0 14px 34px rgba(15, 23, 42, 0.06);
        }

        .section-title {
            margin: 0;
            font-family: "Space Grotesk", "Noto Sans KR", sans-serif;
            font-size: 1.15rem;
            color: #111827;
            letter-spacing: -0.03em;
        }

        .section-copy {
            margin-top: 0.35rem;
            color: #64748b;
            font-size: 0.93rem;
        }

        .badge {
            display: inline-flex;
            align-items: center;
            border-radius: 999px;
            padding: 0.34rem 0.7rem;
            font-size: 0.78rem;
            font-weight: 700;
            margin-right: 0.35rem;
            margin-bottom: 0.35rem;
        }

        .badge-buy, .badge-bullish, .badge-supportive, .badge-active, .badge-strong {
            background: rgba(22, 163, 74, 0.12);
            color: #166534;
        }

        .badge-sell, .badge-bearish, .badge-weak, .badge-overbought {
            background: rgba(220, 38, 38, 0.11);
            color: #991b1b;
        }

        .badge-hold, .badge-watch, .badge-neutral, .badge-normal, .badge-quiet, .badge-oversold, .badge-mixed, .badge-unknown {
            background: rgba(148, 163, 184, 0.14);
            color: #334155;
        }

        .summary-box {
            padding: 0.95rem 1rem;
            border-radius: 1rem;
            background: rgba(248, 250, 252, 0.82);
            border: 1px solid rgba(148, 163, 184, 0.22);
        }

        .muted-label {
            color: #64748b;
            font-size: 0.82rem;
        }

        .sidebar-nav-title {
            margin-top: 0.4rem;
            margin-bottom: 0.6rem;
            font-family: "Space Grotesk", "Noto Sans KR", sans-serif;
            font-size: 0.92rem;
            letter-spacing: 0.04em;
            text-transform: uppercase;
            color: #cbd5e1;
        }

        .sidebar-info-card {
            margin-top: 0.35rem;
            padding: 0.95rem 1rem;
            border-radius: 1rem;
            background: rgba(30, 41, 59, 0.78);
            border: 1px solid rgba(148, 163, 184, 0.22);
        }

        .sidebar-info-title {
            margin: 0 0 0.6rem 0;
            font-family: "Space Grotesk", "Noto Sans KR", sans-serif;
            font-size: 0.95rem;
            font-weight: 700;
            color: #f8fafc;
        }

        .sidebar-info-label {
            margin-top: 0.45rem;
            font-size: 0.78rem;
            text-transform: uppercase;
            letter-spacing: 0.04em;
            color: #94a3b8;
        }

        .sidebar-info-value {
            margin-top: 0.18rem;
            padding: 0.42rem 0.55rem;
            border-radius: 0.7rem;
            background: rgba(15, 23, 42, 0.5);
            color: #f8fafc;
            font-size: 0.82rem;
            word-break: break-all;
        }

        div[data-baseweb="tab-list"] {
            gap: 0.45rem;
            padding: 0.3rem;
            border-radius: 1rem;
            background: rgba(255, 250, 242, 0.82);
            border: 1px solid rgba(148, 163, 184, 0.18);
        }

        button[data-baseweb="tab"] {
            height: 2.8rem;
            padding: 0 1rem;
            border-radius: 0.85rem;
            color: #475569;
            background: transparent;
        }

        button[data-baseweb="tab"][aria-selected="true"] {
            background: linear-gradient(135deg, rgba(255, 255, 255, 0.96), rgba(255, 247, 237, 0.96));
            color: #0f172a;
            border: 1px solid rgba(15, 118, 110, 0.18);
            box-shadow: 0 8px 20px rgba(15, 23, 42, 0.06);
        }

        button[data-baseweb="tab"]::after {
            background: transparent !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _render_sidebar(service: DashboardDataService, schedule_status) -> None:
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


def _render_header() -> None:
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


def _render_action_feedback() -> None:
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


def _render_overview_tab(snapshot, test_report: TestReportPreview | None, schedule_status) -> None:
    report_previews = [preview for preview in snapshot.processed_previews if preview.name == "market_reports"]
    signal_previews = [preview for preview in snapshot.processed_previews if preview.name == "golden_cross_signals"]

    metric_columns = st.columns(4)
    metric_columns[0].metric("원본 데이터셋", len(snapshot.raw_previews))
    metric_columns[1].metric("분석 데이터셋", len(snapshot.processed_previews))
    metric_columns[2].metric("최신 리포트", len(report_previews))
    metric_columns[3].metric("테스트 실패", test_report.failed if test_report else 0)

    left, right = st.columns([1.15, 1], gap="large")

    with left:
        st.markdown('<div class="streamlit-card">', unsafe_allow_html=True)
        st.markdown('<h3 class="section-title">처음 보는 사람을 위한 진행 순서</h3>', unsafe_allow_html=True)
        st.markdown(
            '<div class="section-copy">이 화면은 상태 파악부터 실행, 결과 확인까지 한 번에 이어지도록 구성했습니다.</div>',
            unsafe_allow_html=True,
        )
        st.markdown(
            """
            1. `상태판`에서 최신 리포트, 신호, 정기 수집 상태를 먼저 읽습니다.
            2. 업데이트가 필요하면 `작업 실행`에서 데이터 수집 또는 전체 파이프라인을 돌립니다.
            3. `리포트 해석`에서 종목별 판단과 이유를 비교합니다.
            4. 숫자가 더 필요할 때만 `데이터 탐색`으로 내려가 원본과 분석 데이터를 확인합니다.
            5. 마지막으로 `검증`에서 테스트 실패가 없는지 점검합니다.
            """
        )
        st.markdown("</div>", unsafe_allow_html=True)

        st.markdown("<div style='height:0.8rem'></div>", unsafe_allow_html=True)
        _render_latest_signal_summary(signal_previews, service=DashboardDataService())

    with right:
        _render_latest_report_summary(report_previews, service=DashboardDataService())
        if schedule_status is not None:
            st.markdown("<div style='height:0.8rem'></div>", unsafe_allow_html=True)
            _render_schedule_status_summary(schedule_status)


def _render_actions_tab(symbol_lookup: SymbolLookup, schedule_status) -> None:
    st.markdown('<h3 class="section-title">작업 실행</h3>', unsafe_allow_html=True)
    st.markdown(
        '<div class="section-copy">수집부터 리포트 생성까지 필요한 작업을 여기서 바로 실행합니다.</div>',
        unsafe_allow_html=True,
    )

    if schedule_status is not None:
        _render_schedule_status_panel(schedule_status)
        st.markdown("<div style='height:0.8rem'></div>", unsafe_allow_html=True)

    with st.container(border=True):
        st.markdown("#### 공통 입력")
        symbols_text = st.text_area(
            "종목코드 또는 종목명",
            value=st.session_state.get("streamlit_symbols", "005930"),
            help="여러 종목은 쉼표 또는 줄바꿈으로 구분합니다. 예: 005930, SK하이닉스",
        )
        days = st.number_input("수집 일수", min_value=1, max_value=3650, value=30, step=1)
        st.session_state.streamlit_symbols = symbols_text

    action_columns = st.columns(5, gap="small")

    if action_columns[0].button("데이터 수집", width="stretch", type="primary"):
        _run_collect_action(symbol_lookup, symbols_text, int(days))
    if action_columns[1].button("지표 계산", width="stretch"):
        _run_single_symbol_action(symbol_lookup, symbols_text, generate_indicators_for_symbol, "지표 계산")
    if action_columns[2].button("신호 생성", width="stretch"):
        _run_single_symbol_action(symbol_lookup, symbols_text, generate_golden_cross_signals_for_symbol, "골든크로스 신호 생성")
    if action_columns[3].button("리포트 생성", width="stretch"):
        _run_single_symbol_action(symbol_lookup, symbols_text, generate_market_report_for_symbol, "시장 리포트 생성")
    if action_columns[4].button("전체 파이프라인", width="stretch"):
        _run_full_pipeline_action(symbol_lookup, symbols_text, int(days))

    st.markdown("<div style='height:0.8rem'></div>", unsafe_allow_html=True)
    with st.container(border=True):
        st.markdown("#### 실행 가이드")
        st.markdown(
            """
            - `데이터 수집`: KIS에서 원본 데이터를 내려받습니다.
            - `지표 계산`: 일봉 CSV를 읽어 `ma_5`, `ma_20`, `ma_60`, `rsi_14`를 계산합니다.
            - `신호 생성`: 골든크로스 전략 기준 `buy / sell / hold`를 만듭니다.
            - `리포트 생성`: 추세, RSI, 거래량, 수급을 묶어 한 줄 의견을 생성합니다.
            - `전체 파이프라인`: 위 단계를 순서대로 한 번에 실행합니다.
            """
        )


def _render_data_tab(snapshot, service: DashboardDataService) -> None:
    st.markdown('<h3 class="section-title">데이터 탐색</h3>', unsafe_allow_html=True)
    st.markdown(
        '<div class="section-copy">원본 수집 데이터와 분석 결과를 같은 규칙으로 보여 줍니다. 먼저 추천 컬럼만 보고, 필요할 때만 자세히 펼쳐 보도록 구성했습니다.</div>',
        unsafe_allow_html=True,
    )

    raw_tab, processed_tab = st.tabs(["원본 데이터", "분석 데이터"])
    with raw_tab:
        for preview in snapshot.raw_previews:
            _render_dataset_preview(preview, service)
    with processed_tab:
        for preview in snapshot.processed_previews:
            _render_dataset_preview(preview, service)


def _render_reports_tab(snapshot, service: DashboardDataService) -> None:
    st.markdown('<h3 class="section-title">리포트 해석</h3>', unsafe_allow_html=True)
    st.markdown(
        '<div class="section-copy">종목별 현재 판단과 이유를 한국어 기준으로 먼저 읽고, 필요하면 상세 수치와 차트까지 이어서 확인할 수 있습니다.</div>',
        unsafe_allow_html=True,
    )

    report_previews = [preview for preview in snapshot.processed_previews if preview.name == "market_reports"]
    signal_previews = [preview for preview in snapshot.processed_previews if preview.name == "golden_cross_signals"]

    report_entries = _build_report_entries(report_previews, service)
    if not report_entries:
        st.info("표시할 시장 리포트가 아직 없습니다. 전체 파이프라인이나 리포트 생성을 먼저 실행해 주세요.")
        return

    filter_left, filter_mid, filter_right = st.columns([1.4, 1, 1], gap="small")
    query = filter_left.text_input(
        "종목 검색",
        placeholder="종목코드 또는 종목명으로 찾기",
        key="report_query",
    ).strip().lower()
    opinion_filter = filter_mid.selectbox(
        "최종 의견",
        ("전체", "매수 관점", "관망", "매도 관점", "관심 관찰", "정보 부족"),
        key="report_opinion_filter",
    )
    sort_option = filter_right.selectbox(
        "정렬",
        ("최신 리포트 우선", "매수 관점 우선", "종목명순"),
        key="report_sort",
    )

    trend_filter, signal_filter = st.columns(2, gap="small")
    trend_value = trend_filter.selectbox(
        "추세 상태",
        ("전체", "상승 우세", "중립", "하락 우세", "정보 부족"),
        key="report_trend_filter",
    )
    signal_value = signal_filter.selectbox(
        "골든크로스 신호",
        ("전체", "매수 관점", "관망", "매도 관점", "정보 부족"),
        key="report_signal_filter",
    )

    filtered_entries = _filter_report_entries(
        report_entries=report_entries,
        query=query,
        opinion_filter=opinion_filter,
        trend_filter=trend_value,
        signal_filter=signal_value,
    )
    sorted_entries = _sort_report_entries(filtered_entries, sort_option)

    metric_columns = st.columns(4)
    metric_columns[0].metric("전체 리포트", len(sorted_entries))
    metric_columns[1].metric("매수 관점", sum(1 for item in sorted_entries if item["final_opinion"] == "buy"))
    metric_columns[2].metric("관망", sum(1 for item in sorted_entries if item["final_opinion"] == "hold"))
    metric_columns[3].metric("매도 관점", sum(1 for item in sorted_entries if item["final_opinion"] == "sell"))

    if not sorted_entries:
        st.warning("현재 필터 조건에 맞는 리포트가 없습니다.")
    else:
        st.caption(f"현재 조건에서 {len(sorted_entries)}개의 리포트를 표시합니다.")
        report_columns = st.columns(2, gap="large")
        for index, entry in enumerate(sorted_entries):
            with report_columns[index % 2]:
                _render_market_report_card(entry["preview"], service, frame=entry["frame"])

    filtered_symbols = {entry["symbol"] for entry in sorted_entries}
    visible_signal_previews = [
        preview for preview in signal_previews if not filtered_symbols or preview.symbol in filtered_symbols
    ]

    if visible_signal_previews:
        st.markdown("<div style='height:0.5rem'></div>", unsafe_allow_html=True)
        st.markdown("#### 최신 골든크로스 신호")
        st.caption("현재 리포트 필터에 맞는 종목의 최신 신호만 함께 보여줍니다.")
        signal_columns = st.columns(2)
        for index, preview in enumerate(visible_signal_previews[:6]):
            with signal_columns[index % 2]:
                _render_signal_card(preview, service)


def _build_report_entries(
    previews: list[DatasetPreview],
    service: DashboardDataService,
) -> list[dict[str, object]]:
    entries: list[dict[str, object]] = []
    for preview in previews:
        frame = _read_preview_frame(preview.path)
        if frame.empty:
            continue
        row = frame.iloc[-1]
        entries.append(
            {
                "preview": preview,
                "frame": frame,
                "symbol": preview.symbol,
                "symbol_name": preview.symbol_name or str(row.get("symbol_name", "")),
                "date": str(row.get("date", "")),
                "final_opinion": str(row.get("final_opinion", "unknown")),
                "trend_state": str(row.get("trend_state", "unknown")),
                "golden_cross_signal": str(row.get("golden_cross_signal", "unknown")),
                "summary": str(row.get("summary", "")),
                "display_opinion": _state_label(service, str(row.get("final_opinion", "unknown"))),
                "display_trend": _state_label(service, str(row.get("trend_state", "unknown"))),
                "display_signal": _state_label(service, str(row.get("golden_cross_signal", "unknown"))),
            }
        )
    return entries


def _filter_report_entries(
    report_entries: list[dict[str, object]],
    query: str,
    opinion_filter: str,
    trend_filter: str,
    signal_filter: str,
) -> list[dict[str, object]]:
    filtered = report_entries
    if query:
        filtered = [
            entry
            for entry in filtered
            if query in str(entry["symbol"]).lower()
            or query in str(entry["symbol_name"]).lower()
        ]
    if opinion_filter != "전체":
        filtered = [entry for entry in filtered if entry["display_opinion"] == opinion_filter]
    if trend_filter != "전체":
        filtered = [entry for entry in filtered if entry["display_trend"] == trend_filter]
    if signal_filter != "전체":
        filtered = [entry for entry in filtered if entry["display_signal"] == signal_filter]
    return filtered


def _sort_report_entries(report_entries: list[dict[str, object]], sort_option: str) -> list[dict[str, object]]:
    if sort_option == "종목명순":
        return sorted(report_entries, key=lambda entry: (str(entry["symbol_name"]), str(entry["symbol"])))
    if sort_option == "매수 관점 우선":
        opinion_rank = {"buy": 0, "watch": 1, "hold": 2, "sell": 3, "unknown": 4}
        return sorted(
            report_entries,
            key=lambda entry: (
                opinion_rank.get(str(entry["final_opinion"]), 9),
                str(entry["date"]),
                str(entry["symbol"]),
            ),
        )
    return sorted(report_entries, key=lambda entry: (str(entry["date"]), str(entry["symbol"])), reverse=True)


def _render_test_tab(test_report: TestReportPreview | None) -> None:
    st.markdown('<h3 class="section-title">검증 상태</h3>', unsafe_allow_html=True)
    st.markdown(
        '<div class="section-copy">대시보드와 파이프라인 변경이 기존 동작을 깨지 않았는지 최근 테스트 결과로 확인합니다.</div>',
        unsafe_allow_html=True,
    )

    if test_report is None:
        st.info("저장된 pytest 결과가 없습니다. `python scripts/run_tests.py` 실행 후 다시 확인해 주세요.")
        return

    metric_columns = st.columns(5)
    metric_columns[0].metric("전체", test_report.total)
    metric_columns[1].metric("통과", test_report.passed)
    metric_columns[2].metric("실패", test_report.failed)
    metric_columns[3].metric("스킵", test_report.skipped)
    metric_columns[4].metric("에러", test_report.errors)

    with st.container(border=True):
        st.markdown("#### 최근 테스트 결과")
        st.caption(test_report.command)
        failed_cases = [case for case in test_report.test_cases if case.status != "passed"]
        if not failed_cases:
            st.success("현재 저장된 테스트 결과에는 실패가 없습니다.")
        else:
            for case in failed_cases:
                st.error(f"{case.name}: {case.detail}")

        if st.toggle("전체 테스트 케이스 보기", key="toggle_test_cases"):
            frame = pd.DataFrame(
                [{"name": case.name, "status": case.status, "detail": case.detail} for case in test_report.test_cases]
            )
            st.dataframe(frame, width="stretch", hide_index=True)


def _render_dataset_preview(preview: DatasetPreview, service: DashboardDataService) -> None:
    frame = _read_preview_frame(preview.path)
    default_columns = [column for column in preview.recommended_columns if column in frame.columns]
    if "symbol_name" in frame.columns and "symbol_name" not in default_columns:
        default_columns.insert(0, "symbol_name")
    if "symbol_name" in default_columns and "symbol" in default_columns:
        default_columns.remove("symbol")
    if not default_columns:
        default_columns = list(frame.columns[: min(6, len(frame.columns))])

    with st.container(border=True):
        title = preview.display_name
        symbol_label = _format_symbol_display(preview.symbol, preview.symbol_name)
        if symbol_label:
            title = f"{title} · {symbol_label}"
        st.markdown(f"#### {title}")
        st.caption(f"{preview.summary} · {preview.path.name}")

        meta_left, meta_right = st.columns(2)
        meta_left.metric("행 수", preview.row_count)
        meta_right.metric("컬럼 수", len(preview.columns))

        if st.toggle("데이터 설명 보기", key=f"toggle_summary_{preview.name}_{preview.symbol}_{preview.path.name}"):
            st.markdown(f"- **무엇인가요?** {preview.summary}")
            st.markdown(f"- **왜 보나요?** {preview.purpose}")
            st.markdown(f"- **처음에는 무엇을 보면 좋을까요?** {preview.first_look}")

        if st.toggle("컬럼 설명 보기", key=f"toggle_columns_{preview.name}_{preview.symbol}_{preview.path.name}"):
            for column in preview.columns:
                label = service.COLUMN_META.get(column)
                if label is None:
                    st.markdown(f"- `{column}`: 원본 응답 컬럼입니다.")
                else:
                    st.markdown(f"- `{column}` / **{label.label}**: {label.description} {label.why}")

        if st.toggle("표 옵션", key=f"toggle_options_{preview.name}_{preview.symbol}_{preview.path.name}"):
            max_rows = max(1, min(len(frame), 50))
            if max_rows == 1:
                rows = 1
                st.caption("표시 가능한 행이 1개라 행 수 선택은 생략합니다.")
            else:
                rows = st.slider(
                    "표시 행 수",
                    min_value=1,
                    max_value=max_rows,
                    value=min(max_rows, 8),
                    key=f"rows_{preview.name}_{preview.symbol}_{preview.path.name}",
                )
            selected_columns = st.multiselect(
                "표시할 컬럼",
                options=list(frame.columns),
                default=default_columns,
                key=f"cols_{preview.name}_{preview.symbol}_{preview.path.name}",
            )
        else:
            rows = min(max(1, len(frame)), 8)
            selected_columns = default_columns

        table = frame[selected_columns] if selected_columns else frame
        st.dataframe(_format_frame_for_display(table.head(rows), service), width="stretch", hide_index=True)


def _render_market_report_card(
    preview: DatasetPreview,
    service: DashboardDataService,
    frame: pd.DataFrame | None = None,
) -> None:
    frame = frame if frame is not None else _read_preview_frame(preview.path)
    if frame.empty:
        return
    row = frame.iloc[-1]
    opinion = str(row.get("final_opinion", "unknown"))
    opinion_label = _state_label(service, opinion)
    symbol_label = _format_symbol_display(preview.symbol, preview.symbol_name or str(row.get("symbol_name", "")))
    summary = _localize_report_summary_from_row(service, row)
    reason = _localize_reason(str(row.get("golden_cross_reason", "")))

    with st.container(border=True):
        st.markdown(
            f"""
            <div class="summary-box">
              <div class="muted-label">{escape(symbol_label or "종목 정보 없음")}</div>
              <div style="display:flex;align-items:center;justify-content:space-between;gap:1rem;margin-top:0.35rem;">
                <div>
                  <h3 class="section-title">{escape(preview.symbol_name or str(row.get("symbol_name", "")) or preview.symbol)}</h3>
                  <div class="section-copy">{escape(summary)}</div>
                </div>
                <div class="badge badge-{escape(opinion)}">{escape(opinion_label)}</div>
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        metric_columns = st.columns(4)
        metric_columns[0].metric("추세", _state_label(service, str(row.get("trend_state", "unknown"))))
        metric_columns[1].metric("골든크로스", _state_label(service, str(row.get("golden_cross_signal", "unknown"))))
        metric_columns[2].metric("RSI 상태", _state_label(service, str(row.get("rsi_state", "unknown"))))
        metric_columns[3].metric("수급", _state_label(service, str(row.get("investor_flow", "unknown"))))

        detail_columns = st.columns(4)
        detail_columns[0].metric("종가", _format_number(row.get("close")))
        detail_columns[1].metric("5일선", _format_number(row.get("ma_5")))
        detail_columns[2].metric("20일선", _format_number(row.get("ma_20")))
        detail_columns[3].metric("RSI 14", _format_number(row.get("rsi_14")))

        if reason:
            st.caption(f"판단 근거: {reason}")

        indicator_frame = _load_indicator_frame_for_symbol(preview.symbol)
        if indicator_frame is not None:
            chart_frame = indicator_frame.copy()
            chart_frame["date"] = pd.to_datetime(chart_frame["date"], errors="coerce")
            chart_frame = chart_frame.dropna(subset=["date"]).set_index("date")[["close", "ma_5", "ma_20"]].tail(60)
            st.line_chart(chart_frame, height=280, width="stretch")

        if st.toggle("리포트 상세 보기", key=f"toggle_report_detail_{preview.symbol}_{preview.path.name}"):
            st.dataframe(_format_frame_for_display(frame, service), width="stretch", hide_index=True)


def _render_signal_card(preview: DatasetPreview, service: DashboardDataService) -> None:
    frame = _read_preview_frame(preview.path)
    if frame.empty:
        return
    row = frame.iloc[-1]
    signal = str(row.get("signal", "unknown"))
    signal_label = _state_label(service, signal)
    symbol_label = _format_symbol_display(preview.symbol, preview.symbol_name)
    reason = _localize_reason(str(row.get("signal_reason", "")))

    st.markdown(
        f"""
        <div class="streamlit-card">
          <div class="muted-label">{escape(symbol_label or "종목 정보 없음")}</div>
          <h4 class="section-title" style="margin-top:0.35rem;">{escape(signal_label)}</h4>
          <div class="section-copy">{escape(reason)}</div>
          <div style="margin-top:0.7rem;">
            <span class="badge badge-{escape(signal)}">{escape(signal_label)}</span>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    stat_columns = st.columns(2)
    stat_columns[0].metric("5일선", _format_number(row.get("signal_ma_5")))
    stat_columns[1].metric("20일선", _format_number(row.get("signal_ma_20")))


def _render_latest_signal_summary(signal_previews: list[DatasetPreview], service: DashboardDataService) -> None:
    with st.container(border=True):
        st.markdown('<h3 class="section-title">최신 신호 요약</h3>', unsafe_allow_html=True)
        if not signal_previews:
            st.caption("생성된 골든크로스 신호가 없습니다.")
            return

        latest = signal_previews[0]
        frame = _read_preview_frame(latest.path)
        if frame.empty:
            st.caption("신호 데이터가 비어 있습니다.")
            return

        row = frame.iloc[-1]
        symbol_label = _format_symbol_display(latest.symbol, latest.symbol_name or str(row.get("symbol_name", "")))
        if symbol_label:
            st.caption(symbol_label)
        st.metric("대표 신호", _state_label(service, str(row.get("signal", "hold"))))
        st.caption(_localize_reason(str(row.get("signal_reason", ""))))


def _render_latest_report_summary(report_previews: list[DatasetPreview], service: DashboardDataService) -> None:
    with st.container(border=True):
        st.markdown('<h3 class="section-title">최신 리포트 카드</h3>', unsafe_allow_html=True)
        if not report_previews:
            st.caption("생성된 시장 리포트가 없습니다.")
            return

        latest = report_previews[0]
        frame = _read_preview_frame(latest.path)
        if frame.empty:
            st.caption("리포트 데이터가 비어 있습니다.")
            return

        row = frame.iloc[-1]
        symbol_label = _format_symbol_display(str(row.get("symbol", latest.symbol)), str(row.get("symbol_name", latest.symbol_name)))
        st.markdown(f"#### {symbol_label}")
        st.caption(_localize_report_summary_from_row(service, row))
        badge_columns = st.columns(2)
        badge_columns[0].metric("최종 의견", _state_label(service, str(row.get("final_opinion", "hold"))))
        badge_columns[1].metric("추세", _state_label(service, str(row.get("trend_state", "neutral"))))


def _load_optional_schedule_status():
    try:
        return load_schedule_status()
    except (FileNotFoundError, ValueError):
        return None


def _render_schedule_status_summary(schedule_status) -> None:
    with st.container(border=True):
        st.markdown('<h3 class="section-title">정기 수집 요약</h3>', unsafe_allow_html=True)
        if not schedule_status.log_exists:
            st.caption("아직 정기 수집 로그가 없습니다. `run_scheduled_collection.py --once`로 첫 실행을 남겨보세요.")
            return

        cols = st.columns(2)
        cols[0].metric("마지막 실행", _compact_datetime(schedule_status.last_finished_at))
        cols[1].metric("다음 예정 시각", _compact_datetime(schedule_status.next_run_at))
        status_text = "성공" if schedule_status.last_failed_count == 0 else "일부 실패"
        st.caption(
            f"최근 결과: {status_text} · 성공 {schedule_status.last_success_count} · 실패 {schedule_status.last_failed_count}"
        )


def _render_schedule_status_panel(schedule_status) -> None:
    with st.container(border=True):
        st.markdown("#### 정기 수집 상태")
        config_left, config_right, config_tail = st.columns(3)
        config_left.metric("대상 종목 수", len(schedule_status.schedule.symbols))
        config_right.metric("수집 주기(분)", schedule_status.schedule.interval_minutes)
        config_tail.metric("누적 로그 실행 수", schedule_status.total_logged_runs)

        st.caption(
            f"수집 일수 {schedule_status.schedule.days}일 · 시작 즉시 실행 {'예' if schedule_status.schedule.run_on_startup else '아니오'}"
        )

        latest_left, latest_right = st.columns(2)
        latest_left.markdown(f"**마지막 시작 시각**  \n{_compact_datetime(schedule_status.last_started_at)}")
        latest_right.markdown(f"**마지막 종료 시각**  \n{_compact_datetime(schedule_status.last_finished_at)}")

        next_run = _compact_datetime(schedule_status.next_run_at)
        if schedule_status.next_run_at:
            st.info(f"다음 실행 예정 시각: {next_run}")
        elif not schedule_status.log_exists:
            st.warning("아직 정기 수집 실행 이력이 없습니다.")

        if schedule_status.recent_entries:
            recent_frame = pd.DataFrame(schedule_status.recent_entries)
            if st.toggle("최근 수집 로그 보기", key="toggle_schedule_logs"):
                st.dataframe(recent_frame, width="stretch", hide_index=True)


def _compact_datetime(value: str) -> str:
    if not value:
        return "-"
    try:
        parsed = pd.to_datetime(value)
    except Exception:  # noqa: BLE001
        return value
    if pd.isna(parsed):
        return value
    return parsed.strftime("%Y-%m-%d %H:%M")


def _run_collect_action(symbol_lookup: SymbolLookup, symbols_text: str, days: int) -> None:
    try:
        resolved_items = _resolve_many(symbol_lookup, symbols_text)
        result = collect_market_data_for_symbols(symbols=[item.symbol for item in resolved_items], days=days)
        label_summary = ", ".join(_format_symbol_display(item.symbol, item.symbol_name) for item in resolved_items[:3])
        suffix = "" if len(resolved_items) <= 3 else f" 외 {len(resolved_items) - 3}개"
        _set_action_message(
            f"데이터 수집 완료: {label_summary}{suffix} · {result['success_count']}개 성공, {result['failed_count']}개 실패",
            "success" if result["failed_count"] == 0 else "info",
        )
    except Exception as error:  # noqa: BLE001
        _set_action_message(f"데이터 수집 중 오류가 발생했습니다: {error}", "error")
    st.rerun()


def _run_single_symbol_action(symbol_lookup: SymbolLookup, symbols_text: str, callback, action_name: str) -> None:
    try:
        resolved = _resolve_single(symbol_lookup, symbols_text)
        result = callback(resolved.symbol)
        _set_action_message(
            f"{action_name} 완료: {_format_symbol_display(resolved.symbol, resolved.symbol_name)} · {result['saved_path']}",
            "success",
        )
    except Exception as error:  # noqa: BLE001
        _set_action_message(f"{action_name} 중 오류가 발생했습니다: {error}", "error")
    st.rerun()


def _run_full_pipeline_action(symbol_lookup: SymbolLookup, symbols_text: str, days: int) -> None:
    try:
        resolved_items = _resolve_many(symbol_lookup, symbols_text)
        collect_result = collect_market_data_for_symbols(symbols=[item.symbol for item in resolved_items], days=days)
        for symbol in collect_result["symbols"]:
            generate_indicators_for_symbol(symbol)
            generate_golden_cross_signals_for_symbol(symbol)
            generate_market_report_for_symbol(symbol)
        label_summary = ", ".join(_format_symbol_display(item.symbol, item.symbol_name) for item in resolved_items[:3])
        suffix = "" if len(resolved_items) <= 3 else f" 외 {len(resolved_items) - 3}개"
        _set_action_message(
            f"전체 파이프라인 완료: {label_summary}{suffix} · {collect_result['symbol_count']}개 종목 처리",
            "success" if collect_result["failed_count"] == 0 else "info",
        )
    except Exception as error:  # noqa: BLE001
        _set_action_message(f"전체 파이프라인 실행 중 오류가 발생했습니다: {error}", "error")
    st.rerun()


def _resolve_single(symbol_lookup: SymbolLookup, symbols_text: str) -> ResolvedSymbol:
    tokens = [token.strip() for token in symbols_text.replace(",", "\n").splitlines() if token.strip()]
    if not tokens:
        raise ValueError("종목코드 또는 종목명을 입력해 주세요.")
    return symbol_lookup.resolve(tokens[0])


def _resolve_many(symbol_lookup: SymbolLookup, symbols_text: str) -> list[ResolvedSymbol]:
    tokens = [token.strip() for token in symbols_text.replace(",", "\n").splitlines() if token.strip()]
    if not tokens:
        raise ValueError("종목코드 또는 종목명을 입력해 주세요.")
    return symbol_lookup.resolve_many(tokens)


def _set_action_message(message: str, message_type: str) -> None:
    st.session_state.action_message = message
    st.session_state.action_message_type = message_type


def _read_preview_frame(path) -> pd.DataFrame:
    try:
        frame = pd.read_csv(path)
    except pd.errors.EmptyDataError:
        return pd.DataFrame()
    return frame


def _load_indicator_frame_for_symbol(symbol: str) -> pd.DataFrame | None:
    service = DashboardDataService()
    indicator_dir = service.processed_root / "daily_prices_indicators"
    if not indicator_dir.exists():
        return None
    matches = sorted(indicator_dir.glob(f"{symbol}_*.csv"), key=lambda item: item.stat().st_mtime, reverse=True)
    if not matches:
        return None
    try:
        return pd.read_csv(matches[0])
    except pd.errors.EmptyDataError:
        return None


def _format_frame_for_display(frame: pd.DataFrame, service: DashboardDataService) -> pd.DataFrame:
    display = frame.copy()
    for column in display.columns:
        display[column] = display[column].map(lambda value: _format_display_value(service, column, value))
    return display


def _format_display_value(service: DashboardDataService, column: str, value: object) -> object:
    if pd.isna(value):
        return value
    if column == "symbol_name":
        return str(value).strip()
    if column == "symbol":
        return str(value)
    if column in STATE_COLUMNS:
        return _state_label(service, str(value))
    if column in {"summary"}:
        return _localize_report_summary(service, str(value))
    if column in {"signal_reason", "golden_cross_reason"}:
        return _localize_reason(str(value))
    if column in NUMERIC_COLUMNS:
        return _format_number(value)
    return value


def _state_label(service: DashboardDataService, value: str) -> str:
    return service.STATE_LABELS.get(value, value)


def _format_symbol_display(symbol: str, symbol_name: str) -> str:
    code = str(symbol).strip()
    name = str(symbol_name).strip()
    if name and code:
        return f"{name} ({code})"
    return name or code


def _localize_reason(reason: str) -> str:
    text = reason.strip()
    if not text:
        return ""
    if match := re.fullmatch(r"(?P<short>[\w_]+)\s+crossed\s+above\s+(?P<long>[\w_]+)\.?", text, flags=re.IGNORECASE):
        return f"{_humanize_indicator_name(match.group('short'))}이 {_humanize_indicator_name(match.group('long'))}을 상향 돌파했습니다."
    if match := re.fullmatch(r"(?P<short>[\w_]+)\s+crossed\s+below\s+(?P<long>[\w_]+)\.?", text, flags=re.IGNORECASE):
        return f"{_humanize_indicator_name(match.group('short'))}이 {_humanize_indicator_name(match.group('long'))}을 하향 이탈했습니다."
    if match := re.fullmatch(
        r"(?P<short>[\w_]+)\s+and\s+(?P<long>[\w_]+)\s+did\s+not\s+cross\.?",
        text,
        flags=re.IGNORECASE,
    ):
        return f"{_humanize_indicator_name(match.group('short'))}과 {_humanize_indicator_name(match.group('long'))}의 교차는 아직 확인되지 않았습니다."
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


def _localize_report_summary(service: DashboardDataService, summary: str) -> str:
    text = summary.strip()
    if not text:
        return ""
    pattern = re.compile(
        r"Trend is (?P<trend>[^,]+),\s*golden cross signal is (?P<signal>[^,]+),\s*RSI state is (?P<rsi>[^,]+),\s*volume is (?P<volume>[^,]+),\s*and investor flow is (?P<flow>[^.]+)\.?",
        flags=re.IGNORECASE,
    )
    if match := pattern.fullmatch(text):
        return _compose_localized_report_summary(
            service,
            trend_state=match.group("trend").strip(),
            signal=match.group("signal").strip(),
            rsi_state=match.group("rsi").strip(),
            volume_state=match.group("volume").strip(),
            investor_flow=match.group("flow").strip(),
        )
    return text


def _localize_report_summary_from_row(service: DashboardDataService, row: pd.Series) -> str:
    summary = str(row.get("summary", "")).strip()
    trend_state = str(row.get("trend_state", "")).strip()
    signal = str(row.get("golden_cross_signal", "")).strip()
    rsi_state = str(row.get("rsi_state", "")).strip()
    volume_state = str(row.get("volume_state", "")).strip()
    investor_flow = str(row.get("investor_flow", "")).strip()
    if all((trend_state, signal, rsi_state, volume_state, investor_flow)):
        return _compose_localized_report_summary(
            service,
            trend_state=trend_state,
            signal=signal,
            rsi_state=rsi_state,
            volume_state=volume_state,
            investor_flow=investor_flow,
        )
    return _localize_report_summary(service, summary)


def _compose_localized_report_summary(
    service: DashboardDataService,
    *,
    trend_state: str,
    signal: str,
    rsi_state: str,
    volume_state: str,
    investor_flow: str,
) -> str:
    return (
        f"추세는 {_state_label(service, trend_state)}이고, 골든크로스 신호는 {_state_label(service, signal)}이며, "
        f"RSI 상태는 {_state_label(service, rsi_state)}, 거래량은 {_state_label(service, volume_state)}, "
        f"수급은 {_state_label(service, investor_flow)}입니다."
    )


def _humanize_indicator_name(value: str) -> str:
    mapping = {
        "ma_5": "5일 이동평균선",
        "ma_20": "20일 이동평균선",
        "ma_60": "60일 이동평균선",
    }
    return mapping.get(value.strip().lower(), value.strip())


def _format_number(value: object) -> str:
    if value is None or pd.isna(value):
        return "-"
    number = float(value)
    if number.is_integer():
        return f"{int(number):,}"
    return f"{number:,.2f}"
