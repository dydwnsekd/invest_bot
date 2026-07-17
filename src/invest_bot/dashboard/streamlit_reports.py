from __future__ import annotations

from collections.abc import Callable
from html import escape

import pandas as pd
import streamlit as st

from invest_bot.dashboard.report_favorites import ReportFavoritesStore
from invest_bot.dashboard.service import DashboardDataService, DatasetPreview
from invest_bot.dashboard.streamlit_charts import render_chart_selector
from invest_bot.dashboard.streamlit_formatters import (
    format_frame_for_display,
    format_number,
    format_symbol_display,
    localize_reason,
    localize_report_summary_from_row,
    state_label,
    state_text_color,
)
from invest_bot.dashboard.streamlit_state import load_professional_chart_frame_for_symbol

REPORT_SELECTION_KEY = "report_selected_entry_key"
REPORT_FAVORITES_ONLY_KEY = "report_favorites_only"
REPORT_SORT_OPTION_KEY = "report_sort_option"

def render_reports_tab(
    snapshot,
    service: DashboardDataService,
    *,
    read_preview_frame: Callable[[object], pd.DataFrame],
    load_indicator_frame_for_symbol: Callable[[str], pd.DataFrame | None],
    favorites_store: ReportFavoritesStore | None = None,
) -> None:
    st.markdown('<h3 class="section-title">리포트 해석</h3>', unsafe_allow_html=True)
    st.markdown(
        '<div class="section-copy">보고 싶은 종목 리포트를 하나 선택해 핵심 판단과 차트를 집중해서 읽을 수 있도록 화면을 정리했습니다.</div>',
        unsafe_allow_html=True,
    )

    report_previews = [preview for preview in snapshot.processed_previews if preview.name == "market_reports"]
    if not report_previews:
        st.info("표시할 시장 리포트가 아직 없습니다. 전체 파이프라인이나 리포트 생성을 먼저 실행해 주세요.")
        return

    favorites_store = favorites_store or ReportFavoritesStore()
    favorite_symbols = favorites_store.load_symbols()

    query = st.text_input(
        "리포트 검색",
        placeholder="종목코드 또는 종목명으로 찾기",
        key="report_query",
    ).strip().lower()
    visible_previews = query_report_previews(report_previews, query)
    report_entries = build_report_entries(
        visible_previews,
        service,
        read_preview_frame=read_preview_frame,
        favorite_symbols=favorite_symbols,
    )

    filter_columns = st.columns(2)
    favorites_only = filter_columns[0].toggle(
        "즐겨찾기만 보기",
        value=bool(st.session_state.get(REPORT_FAVORITES_ONLY_KEY, False)),
        key=REPORT_FAVORITES_ONLY_KEY,
    )
    sort_option = filter_columns[1].selectbox(
        "정렬",
        options=["최신순", "즐겨찾기 우선", "종목명순", "매수 관점 우선"],
        index=["최신순", "즐겨찾기 우선", "종목명순", "매수 관점 우선"].index(
            str(st.session_state.get(REPORT_SORT_OPTION_KEY, "최신순"))
        )
        if str(st.session_state.get(REPORT_SORT_OPTION_KEY, "최신순")) in {"최신순", "즐겨찾기 우선", "종목명순", "매수 관점 우선"}
        else 0,
        key=REPORT_SORT_OPTION_KEY,
    )
    visible_entries = sort_report_entries(
        filter_report_entries(
            report_entries,
            query="",
            opinion_filter="전체",
            trend_filter="전체",
            signal_filter="전체",
            favorites_only=favorites_only,
        ),
        sort_option,
    )

    if not visible_entries:
        st.warning("현재 검색 조건에 맞는 리포트가 없습니다.")
        return

    selected_entry_key = resolve_selected_report_key(
        visible_entries,
        st.session_state.get(REPORT_SELECTION_KEY),
    )
    selected_key = st.selectbox(
        "리포트 선택",
        options=[str(entry["entry_key"]) for entry in visible_entries],
        index=selected_entry_key_index(visible_entries, selected_entry_key),
        format_func=lambda entry_key: format_report_selection_option(visible_entries, entry_key),
        key=REPORT_SELECTION_KEY,
    )
    selected_entry = get_report_entry_by_key(visible_entries, selected_key)

    st.caption(
        f"현재 조건에서 {len(visible_entries)}개의 리포트 중 선택한 1건만 본문에 표시합니다."
    )
    render_market_report_card(
        selected_entry["preview"],
        service,
        frame=selected_entry["frame"],
        read_preview_frame=read_preview_frame,
        load_indicator_frame_for_symbol=load_indicator_frame_for_symbol,
        favorites_store=favorites_store,
        is_favorite=bool(selected_entry["is_favorite"]),
    )

def build_report_entries(
    previews: list[DatasetPreview],
    service: DashboardDataService,
    *,
    read_preview_frame: Callable[[object], pd.DataFrame],
    favorite_symbols: set[str] | None = None,
) -> list[dict[str, object]]:
    entries: list[dict[str, object]] = []
    favorite_symbols = favorite_symbols or set()
    for preview in previews:
        frame = read_preview_frame(preview)
        if frame.empty:
            continue
        row = frame.iloc[-1]
        entry_key = build_report_entry_key(preview)
        entries.append(
            {
                "entry_key": entry_key,
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
                "is_favorite": preview.symbol in favorite_symbols,
            }
        )
    return entries

def build_report_entry_key(preview: DatasetPreview) -> str:
    return f"{preview.symbol}:{preview.path.name}"

def query_report_previews(previews: list[DatasetPreview], query: str) -> list[DatasetPreview]:
    if not query:
        return previews
    return [
        preview
        for preview in previews
        if query in str(preview.symbol).lower() or query in str(preview.symbol_name).lower()
    ]


def query_report_entries(report_entries: list[dict[str, object]], query: str) -> list[dict[str, object]]:
    if not query:
        return report_entries
    return [
        entry
        for entry in report_entries
        if query in str(entry["symbol"]).lower() or query in str(entry["symbol_name"]).lower()
    ]

def get_report_entry_by_key(
    report_entries: list[dict[str, object]],
    entry_key: str | None,
) -> dict[str, object] | None:
    if entry_key:
        for entry in report_entries:
            if str(entry["entry_key"]) == entry_key:
                return entry
    return None


def resolve_selected_report_key(
    report_entries: list[dict[str, object]],
    selected_entry_key: str | None,
) -> str | None:
    selected_entry = get_report_entry_by_key(report_entries, selected_entry_key)
    if selected_entry is not None:
        return str(selected_entry["entry_key"])
    if not report_entries:
        return None
    return str(report_entries[0]["entry_key"])


def resolve_selected_report_entry(
    report_entries: list[dict[str, object]],
    selected_entry_key: str | None,
) -> dict[str, object] | None:
    resolved_key = resolve_selected_report_key(report_entries, selected_entry_key)
    return get_report_entry_by_key(report_entries, resolved_key)


def selected_entry_key_index(report_entries: list[dict[str, object]], selected_entry_key: str | None) -> int:
    if not report_entries or selected_entry_key is None:
        return 0
    for index, entry in enumerate(report_entries):
        if str(entry["entry_key"]) == selected_entry_key:
            return index
    return 0


def selected_entry_index(report_entries: list[dict[str, object]], selected_entry: dict[str, object] | None) -> int:
    if selected_entry is None:
        return 0
    return selected_entry_key_index(report_entries, str(selected_entry["entry_key"]))

def format_report_selection_option(report_entries: list[dict[str, object]], entry_key: str) -> str:
    for entry in report_entries:
        if str(entry["entry_key"]) != entry_key:
            continue
        symbol_name = str(entry["symbol_name"] or "")
        symbol = str(entry["symbol"])
        opinion = str(entry["display_opinion"])
        date = str(entry["date"])
        favorite_prefix = "★ " if bool(entry.get("is_favorite")) else ""
        if symbol_name:
            return f"{favorite_prefix}{symbol_name} ({symbol}) · {opinion} · {date}"
        return f"{favorite_prefix}{symbol} · {opinion} · {date}"
    return entry_key


def build_strategy_summary_items(service: DashboardDataService, row: pd.Series) -> list[dict[str, str]]:
    strategies = [
        ("RSI 전략", "rsi_strategy_signal", "rsi_strategy_reason"),
        ("추세 필터 전략", "trend_filter_signal", "trend_filter_reason"),
        ("평균회귀 전략", "mean_reversion_signal", "mean_reversion_reason"),
    ]
    items: list[dict[str, str]] = []
    for label, signal_key, reason_key in strategies:
        signal = str(row.get(signal_key, "unknown"))
        reason = str(row.get(reason_key, "")).strip()
        items.append(
            {
                "label": label,
                "signal": signal,
                "signal_label": state_label(service, signal),
                "reason": localize_reason(reason) if reason else "판단 근거가 아직 없습니다.",
            }
        )
    return items

def filter_report_entries(
    report_entries: list[dict[str, object]],
    query: str,
    opinion_filter: str,
    trend_filter: str,
    signal_filter: str,
    favorites_only: bool = False,
) -> list[dict[str, object]]:
    filtered = query_report_entries(report_entries, query)
    if favorites_only:
        filtered = [entry for entry in filtered if bool(entry.get("is_favorite"))]
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
    if sort_option == "즐겨찾기 우선":
        return sorted(
            report_entries,
            key=lambda entry: (
                0 if bool(entry.get("is_favorite")) else 1,
                str(entry["date"]),
                str(entry["symbol"]),
            ),
            reverse=False,
        )
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
    favorites_store: ReportFavoritesStore | None = None,
    is_favorite: bool = False,
) -> None:
    frame = frame if frame is not None else read_preview_frame(preview)
    if frame.empty:
        return
    row = frame.iloc[-1]
    opinion = str(row.get("final_opinion", "unknown"))
    opinion_label = state_label(service, opinion)
    symbol_label = format_symbol_display(preview.symbol, preview.symbol_name or str(row.get("symbol_name", "")))
    summary = localize_report_summary_from_row(service, row)
    reason = localize_reason(str(row.get("golden_cross_reason", "")))
    strategy_items = build_strategy_summary_items(service, row)
    favorites_store = favorites_store or ReportFavoritesStore()

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

        favorite_label = "★ 즐겨찾기 해제" if is_favorite else "☆ 즐겨찾기 추가"
        if st.button(favorite_label, key=f"favorite_report_{preview.symbol}_{preview.path.name}"):
            now_favorite = favorites_store.toggle(preview.symbol)
            st.session_state["action_message"] = (
                f"{symbol_label} 즐겨찾기 추가 완료" if now_favorite else f"{symbol_label} 즐겨찾기 해제 완료"
            )
            st.session_state["action_message_type"] = "success"
            st.rerun()

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

        st.markdown("#### 전략별 판단")
        for item in strategy_items:
            st.markdown(
                (
                    f"<div class='summary-box' style='margin-bottom:0.6rem;'>"
                    f"<strong>{escape(item['label'])}</strong> · "
                    f"<span style='color:{escape(state_text_color(item['signal']))};font-weight:700;'>"
                    f"{escape(item['signal_label'])}</span><br/>{escape(item['reason'])}</div>"
                ),
                unsafe_allow_html=True,
            )

        if reason:
            st.caption(f"판단 근거: {reason}")

        # Shared report-card path is also used by Watchlist, so professional chart
        # assembly here intentionally lets Watchlist inherit the upgraded stock frame.
        chart_frame = load_professional_chart_frame_for_symbol(service, preview.symbol)
        if chart_frame is None:
            chart_frame = load_indicator_frame_for_symbol(preview.symbol)
        if chart_frame is not None:
            render_chart_selector(
                chart_frame,
                dataset_name="daily_prices_indicators",
                key_prefix=f"report_{preview.symbol}_{preview.path.name}",
                height=280,
            )

        if st.toggle("리포트 상세 보기", key=f"toggle_report_detail_{preview.symbol}_{preview.path.name}"):
            st.dataframe(format_frame_for_display(frame, service), width="stretch", hide_index=True)
