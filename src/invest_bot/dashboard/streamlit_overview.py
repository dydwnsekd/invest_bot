from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from html import escape

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


@dataclass(frozen=True, slots=True)
class OverviewTrustStatus:
    label: str
    detail: str
    report_date: date | None
    signal_date: date | None


def render_overview_tab(
    snapshot,
    service: DashboardDataService,
    test_report: TestReportPreview | None,
    schedule_status,
    *,
    read_preview_frame,
) -> None:
    report_previews = [preview for preview in snapshot.processed_previews if preview.name == "market_reports"]
    signal_previews = [preview for preview in snapshot.processed_previews if preview.name == "golden_cross_signals"]
    report_rows = collect_latest_rows(report_previews, read_preview_frame=read_preview_frame)
    signal_rows = collect_latest_rows(signal_previews, read_preview_frame=read_preview_frame)
    trust_status = build_overview_trust_status(report_rows, signal_rows, test_report)

    render_overview_trust_status(trust_status)
    render_investor_briefing_metrics(snapshot, report_rows, signal_rows, trust_status)

    top_left, top_right = st.columns([1.35, 1], gap="large")

    with top_left:
        render_today_briefing(report_rows, signal_rows, service=service)
        st.markdown("<div style='height:0.8rem'></div>", unsafe_allow_html=True)
        render_watch_targets(report_rows, signal_rows, service=service)

    with top_right:
        render_next_action_panel(schedule_status, test_report)
        st.markdown("<div style='height:0.8rem'></div>", unsafe_allow_html=True)
        render_quick_start_panel()

    lower_left, lower_right = st.columns([1, 1], gap="large")
    with lower_left:
        render_latest_report_summary(report_previews, service=service, read_preview_frame=read_preview_frame)
    with lower_right:
        render_latest_signal_summary(signal_previews, service=service, read_preview_frame=read_preview_frame)
        if schedule_status is not None:
            st.markdown("<div style='height:0.8rem'></div>", unsafe_allow_html=True)
            render_schedule_status_summary(schedule_status)


def collect_latest_rows(
    previews: list[DatasetPreview],
    *,
    read_preview_frame,
    limit: int = 8,
) -> list[tuple[DatasetPreview, pd.Series]]:
    rows: list[tuple[DatasetPreview, pd.Series]] = []
    for preview in previews[:limit]:
        frame = read_preview_frame(preview)
        if frame is None or frame.empty:
            continue
        rows.append((preview, latest_row(frame)))
    return rows


def latest_row(frame: pd.DataFrame) -> pd.Series:
    for column in ("date", "trade_date", "stck_bsop_date"):
        if column not in frame.columns:
            continue
        parsed_dates = pd.to_datetime(frame[column], errors="coerce")
        if parsed_dates.notna().any():
            return frame.loc[parsed_dates.idxmax()]
    return frame.iloc[-1]


def build_overview_trust_status(
    report_rows: list[tuple[DatasetPreview, pd.Series]],
    signal_rows: list[tuple[DatasetPreview, pd.Series]],
    test_report: TestReportPreview | None,
    *,
    today: date | None = None,
) -> OverviewTrustStatus:
    report_date = latest_row_date(report_rows)
    signal_date = latest_row_date(signal_rows)
    reference_today = today or date.today()
    latest_expected_date = latest_weekday(reference_today)

    if test_report and test_report.failed:
        return OverviewTrustStatus(
            label=f"테스트 실패 {test_report.failed}건",
            detail="저장된 테스트 결과에 실패 항목이 있습니다. 투자 판단 전에 시스템 검증을 확인해 주세요.",
            report_date=report_date,
            signal_date=signal_date,
        )
    if report_date is None:
        return OverviewTrustStatus(
            label="리포트 없음",
            detail="표시할 투자 리포트가 없습니다. 데이터 갱신에서 전체 파이프라인을 실행해 주세요.",
            report_date=None,
            signal_date=signal_date,
        )
    if report_date < latest_expected_date - timedelta(days=3):
        return OverviewTrustStatus(
            label="기준일 확인 필요",
            detail=(
                f"최신 리포트 기준일은 {format_reference_date(report_date)}입니다. "
                "투자 판단 전에 데이터 갱신에서 최신 수집과 리포트 생성을 확인해 주세요."
            ),
            report_date=report_date,
            signal_date=signal_date,
        )
    if signal_date is None or signal_date != report_date:
        signal_detail = "전략 신호가 없습니다." if signal_date is None else f"전략 신호 기준일은 {format_reference_date(signal_date)}입니다."
        return OverviewTrustStatus(
            label="기준일 불일치",
            detail=f"리포트 기준일은 {format_reference_date(report_date)}이고, {signal_detail} 두 결과를 함께 확인해 주세요.",
            report_date=report_date,
            signal_date=signal_date,
        )
    return OverviewTrustStatus(
        label="기준일 확인됨",
        detail=f"리포트와 전략 신호의 기준일은 {format_reference_date(report_date)}입니다.",
        report_date=report_date,
        signal_date=signal_date,
    )


def latest_row_date(rows: list[tuple[DatasetPreview, pd.Series]]) -> date | None:
    dates: list[date] = []
    for _, row in rows:
        for column in ("date", "trade_date", "stck_bsop_date"):
            parsed = pd.to_datetime(row.get(column), errors="coerce")
            if not pd.isna(parsed):
                dates.append(parsed.date())
                break
    return max(dates) if dates else None


def latest_weekday(reference_date: date) -> date:
    while reference_date.weekday() >= 5:
        reference_date -= timedelta(days=1)
    return reference_date


def format_reference_date(value: date) -> str:
    return value.strftime("%Y-%m-%d")


def render_overview_trust_status(status: OverviewTrustStatus) -> None:
    if status.label == "기준일 확인됨":
        st.info(f"데이터 기준일 · {status.detail}")
        return
    st.warning(f"데이터 확인 필요 · {status.detail}")


def render_investor_briefing_metrics(snapshot, report_rows, signal_rows, trust_status: OverviewTrustStatus) -> None:
    buy_report_count = sum(1 for _, row in report_rows if str(row.get("final_opinion", "")).lower() == "buy")
    buy_signal_count = sum(1 for _, row in signal_rows if str(row.get("signal", "")).lower() == "buy")

    metric_columns = st.columns(4)
    metric_columns[0].metric("추적 데이터셋", len(snapshot.raw_previews) + len(snapshot.processed_previews))
    metric_columns[1].metric("리포트 종목", len(report_rows))
    metric_columns[2].metric("매수/관심 신호", buy_report_count + buy_signal_count)
    metric_columns[3].metric("데이터 상태", compact_trust_label(trust_status.label))


def compact_trust_label(label: str) -> str:
    return {
        "기준일 확인 필요": "확인 필요",
        "기준일 불일치": "불일치",
        "기준일 확인됨": "확인됨",
    }.get(label, label)


def render_today_briefing(report_rows, signal_rows, *, service: DashboardDataService) -> None:
    st.markdown('<div class="streamlit-card investor-brief-card">', unsafe_allow_html=True)
    st.markdown('<div class="eyebrow inline-eyebrow">오늘의 투자 브리핑</div>', unsafe_allow_html=True)
    st.markdown('<h3 class="section-title">먼저 확인할 종목과 판단 근거</h3>', unsafe_allow_html=True)
    st.markdown(
        '<div class="section-copy">최신 리포트와 신호에서 투자자가 바로 볼 만한 판단을 앞쪽에 모았습니다.</div>',
        unsafe_allow_html=True,
    )

    if not report_rows:
        st.info("아직 투자 리포트가 없습니다. 데이터 갱신에서 전체 파이프라인을 실행하면 브리핑이 채워집니다.")
        st.markdown("</div>", unsafe_allow_html=True)
        return

    primary_preview, primary_row = report_rows[0]
    symbol_label = format_symbol_display(str(primary_row.get("symbol", primary_preview.symbol)), str(primary_row.get("symbol_name", primary_preview.symbol_name)))
    opinion = state_label(service, str(primary_row.get("final_opinion", "hold")))
    trend = state_label(service, str(primary_row.get("trend_state", "neutral")))
    summary = localize_report_summary_from_row(service, primary_row)
    date_text = format_row_date(primary_row) or "날짜 정보 없음"

    st.markdown(
        f"""
        <div class="briefing-lead-card">
          <div class="briefing-symbol">{escape(symbol_label)}</div>
          <div class="briefing-summary">{escape(summary)}</div>
          <div class="briefing-meta-grid">
            <div><span>최종 의견</span><strong>{escape(opinion)}</strong></div>
            <div><span>추세</span><strong>{escape(trend)}</strong></div>
            <div><span>기준일</span><strong>{escape(date_text)}</strong></div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if signal_rows:
        _, signal_row = signal_rows[0]
        signal = state_label(service, str(signal_row.get("signal", "hold")))
        reason = localize_reason(str(signal_row.get("signal_reason", "")))
        st.caption(f"최신 전략 신호: {signal} · {reason}")
    st.markdown("</div>", unsafe_allow_html=True)


def render_watch_targets(report_rows, signal_rows, *, service: DashboardDataService) -> None:
    st.markdown('<div class="streamlit-card">', unsafe_allow_html=True)
    st.markdown('<h3 class="section-title">오늘 볼 만한 종목</h3>', unsafe_allow_html=True)
    st.markdown(
        '<div class="section-copy">매수 관점, 관심 관찰, 강한 신호가 있는 종목을 먼저 보여줍니다.</div>',
        unsafe_allow_html=True,
    )

    candidate_rows = select_watch_targets(report_rows, signal_rows)
    if not candidate_rows:
        st.caption("아직 우선 확인할 종목이 없습니다. 최신 리포트나 신호를 생성해 보세요.")
        st.markdown("</div>", unsafe_allow_html=True)
        return

    st.markdown('<div class="watch-target-grid">', unsafe_allow_html=True)
    for preview, row, reason_key in candidate_rows[:4]:
        symbol_label = format_symbol_display(str(row.get("symbol", preview.symbol)), str(row.get("symbol_name", preview.symbol_name)))
        opinion = state_label(service, str(row.get("final_opinion", row.get("signal", "hold"))))
        reason = localize_report_summary_from_row(service, row) if "final_opinion" in row else localize_reason(str(row.get("signal_reason", "")))
        st.markdown(
            f"""
            <div class="watch-target-card">
              <div class="watch-target-reason">{escape(reason_key)}</div>
              <strong>{escape(symbol_label)}</strong>
              <span>{escape(opinion)}</span>
              <p>{escape(reason)}</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
    st.markdown("</div>", unsafe_allow_html=True)
    if st.button("투자 리포트에서 후보 자세히 보기", key="overview_open_reports", width="stretch"):
        navigate_to_tab("투자 리포트")
    st.markdown("</div>", unsafe_allow_html=True)


def select_watch_targets(report_rows, signal_rows) -> list[tuple[DatasetPreview, pd.Series, str]]:
    candidates: list[tuple[DatasetPreview, pd.Series, str]] = []
    seen: set[str] = set()

    for preview, row in report_rows:
        symbol = str(row.get("symbol", preview.symbol))
        opinion = str(row.get("final_opinion", "")).lower()
        trend = str(row.get("trend_state", "")).lower()
        if opinion in {"buy", "watch"} or trend == "bullish":
            label = "매수 관점" if opinion == "buy" else "추세 관심"
            candidates.append((preview, row, label))
            seen.add(symbol)

    for preview, row in signal_rows:
        symbol = str(row.get("symbol", preview.symbol))
        if symbol in seen:
            continue
        signal = str(row.get("signal", "")).lower()
        if signal == "buy":
            candidates.append((preview, row, "전략 신호"))
            seen.add(symbol)

    return candidates


def render_next_action_panel(schedule_status, test_report: TestReportPreview | None) -> None:
    st.markdown('<div class="streamlit-card next-action-card">', unsafe_allow_html=True)
    st.markdown('<h3 class="section-title">다음 행동</h3>', unsafe_allow_html=True)
    st.markdown('<div class="section-copy">현재 상태에 따라 먼저 할 일을 안내합니다.</div>', unsafe_allow_html=True)

    actions: list[tuple[str, str, str]] = []
    if schedule_status is None or not getattr(schedule_status, "log_exists", False):
        actions.append(("데이터 갱신", "정기 수집 로그가 없으면 먼저 데이터 갱신에서 수집과 리포트 생성을 실행하세요.", "데이터 갱신"))
    elif getattr(schedule_status, "last_failed_count", 0):
        actions.append(("수집 실패 확인", "최근 정기 수집에 실패가 있어 데이터 갱신에서 실패 종목을 다시 실행하세요.", "데이터 갱신"))
    else:
        actions.append(("투자 리포트 확인", "데이터가 준비되어 있으니 투자 리포트에서 종목별 판단을 읽어보세요.", "투자 리포트"))

    if test_report and test_report.failed:
        actions.append(("시스템 검증", "테스트 실패가 있으니 시스템 검증에서 실패 항목을 먼저 확인하세요.", "시스템 검증"))
    else:
        actions.append(("백테스트", "관심 있는 전략은 백테스트에서 과거 성과를 확인하세요.", "백테스트"))

    st.markdown('<div class="next-action-list">', unsafe_allow_html=True)
    for index, (title, copy, target_tab) in enumerate(actions):
        st.markdown(
            f"""
            <div class="next-action-item">
              <strong>{escape(title)}</strong>
              <p>{escape(copy)}</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        if st.button(f"{title} 열기", key=f"overview_next_action_{index}", width="stretch"):
            navigate_to_tab(target_tab)
    st.markdown("</div>", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)


def navigate_to_tab(tab_name: str) -> None:
    st.session_state.selected_tab = tab_name
    st.rerun()


def render_quick_start_panel() -> None:
    st.markdown('<div class="streamlit-card">', unsafe_allow_html=True)
    st.markdown('<h3 class="section-title">처음 보는 순서</h3>', unsafe_allow_html=True)
    st.markdown(
        '<div class="section-copy">상태 확인부터 실행, 판단, 검증까지 한 흐름으로 이어집니다.</div>',
        unsafe_allow_html=True,
    )
    render_quick_start_cards()
    st.markdown("</div>", unsafe_allow_html=True)


def render_quick_start_cards() -> None:
    st.markdown(
        """
        <div class="quick-start-grid">
          <div class="quick-start-card">
            <span class="quick-start-step">1</span>
            <strong>상태 확인</strong>
            <p>홈에서 최신 리포트, 신호, 정기 수집 상태를 먼저 확인합니다.</p>
          </div>
          <div class="quick-start-card">
            <span class="quick-start-step">2</span>
            <strong>데이터 갱신</strong>
            <p>데이터 갱신에서 종목과 조회 기간을 고르고 필요한 작업만 실행합니다.</p>
          </div>
          <div class="quick-start-card">
            <span class="quick-start-step">3</span>
            <strong>판단 읽기</strong>
            <p>투자 리포트에서 한 종목씩 의견, 전략, 차트, 해석 모아보기를 봅니다.</p>
          </div>
          <div class="quick-start-card">
            <span class="quick-start-step">4</span>
            <strong>검증하기</strong>
            <p>백테스트와 시스템 검증에서 전략 결과와 테스트 실패 여부를 확인합니다.</p>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


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
        frame = read_preview_frame(latest)
        if frame.empty:
            st.caption("신호 데이터가 비어 있습니다.")
            return

        row = latest_row(frame)
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
        frame = read_preview_frame(latest)
        if frame.empty:
            st.caption("리포트 데이터가 비어 있습니다.")
            return

        row = latest_row(frame)
        symbol_label = format_symbol_display(str(row.get("symbol", latest.symbol)), str(row.get("symbol_name", latest.symbol_name)))
        st.markdown(f"#### {symbol_label}")
        st.caption(localize_report_summary_from_row(service, row))
        badge_columns = st.columns(2)
        badge_columns[0].metric("최종 의견", state_label(service, str(row.get("final_opinion", "hold"))))
        badge_columns[1].metric("추세", state_label(service, str(row.get("trend_state", "neutral"))))


def format_row_date(row: pd.Series) -> str:
    for column in ("date", "trade_date", "stck_bsop_date"):
        parsed = pd.to_datetime(row.get(column), errors="coerce")
        if not pd.isna(parsed):
            return parsed.strftime("%Y-%m-%d")
    return ""


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
