from __future__ import annotations

from html import escape

import pandas as pd
import streamlit as st

from invest_bot.dashboard.service import DashboardDataService
from invest_bot.dashboard.streamlit_formatters import (
    format_symbol_display,
    localize_reason,
    localize_report_summary_from_row,
    state_label,
)
from invest_bot.dashboard.streamlit_reports import sort_report_entries

INTERPRETATION_SORT_OPTION_KEY = "interpretation_sort_option"
INTERPRETATION_OPINION_FILTER_KEY = "interpretation_opinion_filter"
INTERPRETATION_STRATEGY_FILTER_KEY = "interpretation_strategy_filter"

STRATEGY_COLUMNS = (
    ("골든크로스", "golden_cross_signal", "golden_cross_reason"),
    ("RSI", "rsi_strategy_signal", "rsi_strategy_reason"),
    ("추세필터", "trend_filter_signal", "trend_filter_reason"),
    ("평균회귀", "mean_reversion_signal", "mean_reversion_reason"),
)


def render_interpretations_panel(
    entries: list[dict[str, object]],
    service: DashboardDataService,
    *,
    show_reason_expander: bool = False,
) -> None:
    control_columns = st.columns(3)
    opinion_filter = control_columns[0].selectbox(
        "최종 의견",
        options=["전체", "매수 관점", "관심 관찰", "관망", "매도 관점", "정보 부족"],
        key=INTERPRETATION_OPINION_FILTER_KEY,
    )
    strategy_filter = control_columns[1].selectbox(
        "전략 신호",
        options=["전체", "매수 관점", "관망", "매도 관점", "정보 부족"],
        key=INTERPRETATION_STRATEGY_FILTER_KEY,
    )
    sort_option = control_columns[2].selectbox(
        "정렬",
        options=["최신순", "매수 관점 우선", "종목명순"],
        key=INTERPRETATION_SORT_OPTION_KEY,
    )

    visible_entries = filter_interpretation_entries(entries, opinion_filter=opinion_filter, strategy_filter=strategy_filter)
    visible_entries = sort_report_entries(visible_entries, sort_option)
    rows = build_interpretation_rows(visible_entries, service)

    metric_columns = st.columns(4)
    metric_columns[0].metric("표시 종목", len(rows))
    metric_columns[1].metric("매수 관점", sum(1 for row in rows if row["최종 의견"] == "매수 관점"))
    metric_columns[2].metric("전략 매수 신호", sum(count_buy_strategy_signals(row) for row in rows))
    metric_columns[3].metric("정보 부족", sum(1 for row in rows if "정보 부족" in row.values()))

    if not rows:
        st.warning("현재 조건에 맞는 종목/전략 해석이 없습니다.")
        return

    st.markdown(render_interpretation_cards(rows), unsafe_allow_html=True)
    render_strategy_reasons(visible_entries, service, show_expander=show_reason_expander)


def render_strategy_reasons(
    entries: list[dict[str, object]],
    service: DashboardDataService,
    *,
    show_expander: bool,
) -> None:
    reason_rows = build_strategy_reason_rows(entries, service)
    if show_expander:
        with st.expander("전략 판단 근거 보기"):
            render_strategy_reason_content(reason_rows)
        return

    st.markdown("#### 전략 판단 근거")
    render_strategy_reason_content(reason_rows)


def render_strategy_reason_content(reason_rows: list[dict[str, object]]) -> None:
    if reason_rows:
        st.markdown(render_strategy_reason_cards(reason_rows), unsafe_allow_html=True)
    else:
        st.caption("표시할 전략 판단 근거가 없습니다.")

def render_interpretation_cards(rows: list[dict[str, object]]) -> str:
    cards = []
    for row in rows:
        cards.append(
            f"""
            <article class="interpretation-card">
              <div class="interpretation-card-header">
                <div>
                  <div class="muted-label">{escape(str(row.get('날짜', '')))}</div>
                  <h4>{escape(str(row.get('종목', '')))}</h4>
                </div>
                <span class="interpretation-pill">{escape(str(row.get('최종 의견', '')))}</span>
              </div>
              <div class="interpretation-signal-grid">
                {render_signal_cell('추세', row.get('추세', ''))}
                {render_signal_cell('골든크로스', row.get('골든크로스', ''))}
                {render_signal_cell('RSI 전략', row.get('RSI 전략', ''))}
                {render_signal_cell('추세필터', row.get('추세필터', ''))}
                {render_signal_cell('평균회귀', row.get('평균회귀', ''))}
                {render_signal_cell('수급', row.get('수급', ''))}
              </div>
              <p class="interpretation-summary">{escape(str(row.get('한 줄 해석', '')))}</p>
            </article>
            """
        )
    return f"<div class='interpretation-grid'>{''.join(cards)}</div>"


def render_signal_cell(label: str, value: object) -> str:
    return (
        "<div class='interpretation-signal-cell'>"
        f"<span>{escape(label)}</span>"
        f"<strong>{escape(str(value))}</strong>"
        "</div>"
    )


def render_strategy_reason_cards(rows: list[dict[str, object]]) -> str:
    items = []
    for row in rows:
        items.append(
            f"""
            <article class="interpretation-reason-card">
              <div class="interpretation-reason-title">
                <strong>{escape(str(row.get('종목', '')))}</strong>
                <span>{escape(str(row.get('전략', '')))} · {escape(str(row.get('판단', '')))}</span>
              </div>
              <p>{escape(str(row.get('근거', '')))}</p>
            </article>
            """
        )
    return f"<div class='interpretation-reason-list'>{''.join(items)}</div>"

def filter_interpretation_entries(
    entries: list[dict[str, object]],
    *,
    opinion_filter: str = "전체",
    strategy_filter: str = "전체",
) -> list[dict[str, object]]:
    filtered = entries
    if opinion_filter != "전체":
        filtered = [entry for entry in filtered if str(entry.get("display_opinion", "")) == opinion_filter]
    if strategy_filter != "전체":
        filtered = [entry for entry in filtered if entry_has_strategy_label(entry, strategy_filter)]
    return filtered


def entry_has_strategy_label(entry: dict[str, object], strategy_filter: str) -> bool:
    frame = entry.get("frame")
    if not isinstance(frame, pd.DataFrame) or frame.empty:
        return False
    row = frame.iloc[-1]
    service = DashboardDataService()
    return any(state_label(service, str(row.get(signal_key, "unknown"))) == strategy_filter for _, signal_key, _ in STRATEGY_COLUMNS)


def build_interpretation_rows(entries: list[dict[str, object]], service: DashboardDataService) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for entry in entries:
        frame = entry.get("frame")
        if not isinstance(frame, pd.DataFrame) or frame.empty:
            continue
        row = frame.iloc[-1]
        rows.append(
            {
                "종목": format_symbol_display(str(entry.get("symbol", "")), str(entry.get("symbol_name", ""))),
                "날짜": str(row.get("date", entry.get("date", ""))),
                "최종 의견": state_label(service, str(row.get("final_opinion", "unknown"))),
                "추세": state_label(service, str(row.get("trend_state", "unknown"))),
                "골든크로스": state_label(service, str(row.get("golden_cross_signal", "unknown"))),
                "RSI 전략": state_label(service, str(row.get("rsi_strategy_signal", "unknown"))),
                "추세필터": state_label(service, str(row.get("trend_filter_signal", "unknown"))),
                "평균회귀": state_label(service, str(row.get("mean_reversion_signal", "unknown"))),
                "수급": state_label(service, str(row.get("investor_flow", "unknown"))),
                "한 줄 해석": localize_report_summary_from_row(service, row),
            }
        )
    return rows


def build_strategy_reason_rows(entries: list[dict[str, object]], service: DashboardDataService) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for entry in entries:
        frame = entry.get("frame")
        if not isinstance(frame, pd.DataFrame) or frame.empty:
            continue
        row = frame.iloc[-1]
        symbol_label = format_symbol_display(str(entry.get("symbol", "")), str(entry.get("symbol_name", "")))
        for strategy_name, signal_key, reason_key in STRATEGY_COLUMNS:
            rows.append(
                {
                    "종목": symbol_label,
                    "전략": strategy_name,
                    "판단": state_label(service, str(row.get(signal_key, "unknown"))),
                    "근거": localize_reason(str(row.get(reason_key, "")).strip()) or "판단 근거가 아직 없습니다.",
                }
            )
    return rows


def count_buy_strategy_signals(row: dict[str, object]) -> int:
    return sum(
        1
        for key in ("골든크로스", "RSI 전략", "추세필터", "평균회귀")
        if row.get(key) == "매수 관점"
    )
