from __future__ import annotations

import pandas as pd
import streamlit as st

from invest_bot.dashboard.service import DashboardDataService, DatasetPreview, TestReportPreview
from invest_bot.dashboard.streamlit_formatters import (
    compact_datetime,
    format_symbol_display,
    localize_reason,
    localize_report_summary_from_row,
    state_label,
)


def render_overview_tab(
    snapshot,
    test_report: TestReportPreview | None,
    schedule_status,
    *,
    read_preview_frame,
) -> None:
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
        render_latest_signal_summary(signal_previews, service=DashboardDataService(), read_preview_frame=read_preview_frame)

    with right:
        render_latest_report_summary(report_previews, service=DashboardDataService(), read_preview_frame=read_preview_frame)
        if schedule_status is not None:
            st.markdown("<div style='height:0.8rem'></div>", unsafe_allow_html=True)
            render_schedule_status_summary(schedule_status)


def render_latest_signal_summary(
    signal_previews: list[DatasetPreview],
    service: DashboardDataService,
    *,
    read_preview_frame,
) -> None:
    with st.container(border=True):
        st.markdown('<h3 class="section-title">최신 신호 요약</h3>', unsafe_allow_html=True)
        if not signal_previews:
            st.caption("생성된 골든크로스 신호가 없습니다.")
            return

        latest = signal_previews[0]
        frame = read_preview_frame(latest.path)
        if frame.empty:
            st.caption("신호 데이터가 비어 있습니다.")
            return

        row = frame.iloc[-1]
        symbol_label = format_symbol_display(latest.symbol, latest.symbol_name or str(row.get("symbol_name", "")))
        if symbol_label:
            st.caption(symbol_label)
        st.metric("대표 신호", state_label(service, str(row.get("signal", "hold"))))
        st.caption(localize_reason(str(row.get("signal_reason", ""))))


def render_latest_report_summary(
    report_previews: list[DatasetPreview],
    service: DashboardDataService,
    *,
    read_preview_frame,
) -> None:
    with st.container(border=True):
        st.markdown('<h3 class="section-title">최신 리포트 카드</h3>', unsafe_allow_html=True)
        if not report_previews:
            st.caption("생성된 시장 리포트가 없습니다.")
            return

        latest = report_previews[0]
        frame = read_preview_frame(latest.path)
        if frame.empty:
            st.caption("리포트 데이터가 비어 있습니다.")
            return

        row = frame.iloc[-1]
        symbol_label = format_symbol_display(str(row.get("symbol", latest.symbol)), str(row.get("symbol_name", latest.symbol_name)))
        st.markdown(f"#### {symbol_label}")
        st.caption(localize_report_summary_from_row(service, row))
        badge_columns = st.columns(2)
        badge_columns[0].metric("최종 의견", state_label(service, str(row.get("final_opinion", "hold"))))
        badge_columns[1].metric("추세", state_label(service, str(row.get("trend_state", "neutral"))))


def render_schedule_status_summary(schedule_status) -> None:
    with st.container(border=True):
        st.markdown('<h3 class="section-title">정기 수집 요약</h3>', unsafe_allow_html=True)
        if not schedule_status.log_exists:
            st.caption("아직 정기 수집 로그가 없습니다. `run_scheduled_collection.py --once`로 첫 실행을 남겨보세요.")
            return

        cols = st.columns(2)
        cols[0].metric("마지막 실행", compact_datetime(schedule_status.last_finished_at))
        cols[1].metric("다음 예정 시각", compact_datetime(schedule_status.next_run_at))
        status_text = "성공" if schedule_status.last_failed_count == 0 else "일부 실패"
        st.caption(
            f"최근 결과: {status_text} · 성공 {schedule_status.last_success_count} · 실패 {schedule_status.last_failed_count}"
        )


def render_schedule_status_panel(schedule_status) -> None:
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
        latest_left.markdown(f"**마지막 시작 시각**  \n{compact_datetime(schedule_status.last_started_at)}")
        latest_right.markdown(f"**마지막 종료 시각**  \n{compact_datetime(schedule_status.last_finished_at)}")

        next_run = compact_datetime(schedule_status.next_run_at)
        if schedule_status.next_run_at:
            st.info(f"다음 실행 예정 시각: {next_run}")
        elif not schedule_status.log_exists:
            st.warning("아직 정기 수집 실행 이력이 없습니다.")

        if schedule_status.recent_entries:
            recent_frame = pd.DataFrame(schedule_status.recent_entries)
            if st.toggle("최근 수집 로그 보기", key="toggle_schedule_logs"):
                st.dataframe(recent_frame, width="stretch", hide_index=True)
