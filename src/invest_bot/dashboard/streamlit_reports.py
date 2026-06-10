from __future__ import annotations

from collections.abc import Callable
from html import escape

import pandas as pd
import streamlit as st

from invest_bot.dashboard.service import DashboardDataService, DatasetPreview
from invest_bot.dashboard.streamlit_formatters import (
    format_frame_for_display,
    format_number,
    format_symbol_display,
    localize_reason,
    localize_report_summary_from_row,
    state_label,
)


def render_reports_tab(
    snapshot,
    service: DashboardDataService,
    *,
    read_preview_frame: Callable[[object], pd.DataFrame],
    load_indicator_frame_for_symbol: Callable[[str], pd.DataFrame | None],
) -> None:
    st.markdown('<h3 class="section-title">리포트 해석</h3>', unsafe_allow_html=True)
    st.markdown(
        '<div class="section-copy">종목별 현재 판단과 이유를 한국어 기준으로 먼저 읽고, 필요하면 상세 수치와 차트까지 이어서 확인할 수 있습니다.</div>',
        unsafe_allow_html=True,
    )

    report_previews = [preview for preview in snapshot.processed_previews if preview.name == "market_reports"]
    signal_previews = [preview for preview in snapshot.processed_previews if preview.name == "golden_cross_signals"]

    report_entries = build_report_entries(report_previews, service, read_preview_frame=read_preview_frame)
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

    filtered_entries = filter_report_entries(
        report_entries=report_entries,
        query=query,
        opinion_filter=opinion_filter,
        trend_filter=trend_value,
        signal_filter=signal_value,
    )
    sorted_entries = sort_report_entries(filtered_entries, sort_option)

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
                render_market_report_card(
                    entry["preview"],
                    service,
                    frame=entry["frame"],
                    read_preview_frame=read_preview_frame,
                    load_indicator_frame_for_symbol=load_indicator_frame_for_symbol,
                )

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
                render_signal_card(preview, service, read_preview_frame=read_preview_frame)


def build_report_entries(
    previews: list[DatasetPreview],
    service: DashboardDataService,
    *,
    read_preview_frame: Callable[[object], pd.DataFrame],
) -> list[dict[str, object]]:
    entries: list[dict[str, object]] = []
    for preview in previews:
        frame = read_preview_frame(preview.path)
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
                "display_opinion": state_label(service, str(row.get("final_opinion", "unknown"))),
                "display_trend": state_label(service, str(row.get("trend_state", "unknown"))),
                "display_signal": state_label(service, str(row.get("golden_cross_signal", "unknown"))),
            }
        )
    return entries


def filter_report_entries(
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


def sort_report_entries(report_entries: list[dict[str, object]], sort_option: str) -> list[dict[str, object]]:
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


def render_market_report_card(
    preview: DatasetPreview,
    service: DashboardDataService,
    *,
    frame: pd.DataFrame | None = None,
    read_preview_frame: Callable[[object], pd.DataFrame],
    load_indicator_frame_for_symbol: Callable[[str], pd.DataFrame | None],
) -> None:
    frame = frame if frame is not None else read_preview_frame(preview.path)
    if frame.empty:
        return
    row = frame.iloc[-1]
    opinion = str(row.get("final_opinion", "unknown"))
    opinion_label = state_label(service, opinion)
    symbol_label = format_symbol_display(preview.symbol, preview.symbol_name or str(row.get("symbol_name", "")))
    summary = localize_report_summary_from_row(service, row)
    reason = localize_reason(str(row.get("golden_cross_reason", "")))

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
        metric_columns[0].metric("추세", state_label(service, str(row.get("trend_state", "unknown"))))
        metric_columns[1].metric("골든크로스", state_label(service, str(row.get("golden_cross_signal", "unknown"))))
        metric_columns[2].metric("RSI 상태", state_label(service, str(row.get("rsi_state", "unknown"))))
        metric_columns[3].metric("수급", state_label(service, str(row.get("investor_flow", "unknown"))))

        detail_columns = st.columns(4)
        detail_columns[0].metric("종가", format_number(row.get("close")))
        detail_columns[1].metric("5일선", format_number(row.get("ma_5")))
        detail_columns[2].metric("20일선", format_number(row.get("ma_20")))
        detail_columns[3].metric("RSI 14", format_number(row.get("rsi_14")))

        if reason:
            st.caption(f"판단 근거: {reason}")

        indicator_frame = load_indicator_frame_for_symbol(preview.symbol)
        if indicator_frame is not None:
            chart_frame = indicator_frame.copy()
            chart_frame["date"] = pd.to_datetime(chart_frame["date"], errors="coerce")
            chart_frame = chart_frame.dropna(subset=["date"]).set_index("date")[["close", "ma_5", "ma_20"]].tail(60)
            st.line_chart(chart_frame, height=280, width="stretch")

        if st.toggle("리포트 상세 보기", key=f"toggle_report_detail_{preview.symbol}_{preview.path.name}"):
            st.dataframe(format_frame_for_display(frame, service), width="stretch", hide_index=True)


def render_signal_card(
    preview: DatasetPreview,
    service: DashboardDataService,
    *,
    read_preview_frame: Callable[[object], pd.DataFrame],
) -> None:
    frame = read_preview_frame(preview.path)
    if frame.empty:
        return
    row = frame.iloc[-1]
    signal = str(row.get("signal", "unknown"))
    signal_label = state_label(service, signal)
    symbol_label = format_symbol_display(preview.symbol, preview.symbol_name)
    reason = localize_reason(str(row.get("signal_reason", "")))

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
    stat_columns[0].metric("5일선", format_number(row.get("signal_ma_5")))
    stat_columns[1].metric("20일선", format_number(row.get("signal_ma_20")))
