from __future__ import annotations

from collections.abc import Callable
from html import escape

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

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
CANDIDATE_PENDING_SELECTION_SUFFIX = "__candidate_pending"
CANDIDATE_SCROLL_SUFFIX = "__scroll_to_detail"
REPORT_DETAIL_ANCHOR_ID = "selected-report-detail"
REPORT_STRATEGY_SIGNAL_KEYS = (
    "golden_cross_signal",
    "rsi_strategy_signal",
    "trend_filter_signal",
    "mean_reversion_signal",
)
REPORT_CORE_DATA_KEYS = ("close", "ma_5", "ma_20", "rsi_14")

def render_reports_tab(
    snapshot,
    service: DashboardDataService | None = None,
    *,
    read_preview_frame: Callable[[object], pd.DataFrame],
    load_indicator_frame_for_symbol: Callable[[str], pd.DataFrame | None],
    favorites_store: ReportFavoritesStore | None = None,
) -> None:
    st.markdown('<h3 class="section-title">투자 리포트</h3>', unsafe_allow_html=True)
    st.markdown(
        '<div class="section-copy">보고 싶은 종목을 선택해 최종 의견, 전략별 판단, 차트, 상세 데이터를 집중해서 읽습니다.</div>',
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

    show_overview = st.toggle("해석 모아보기 열기", value=False, key="report_interpretation_overview_open")
    if show_overview:
        st.caption("현재 리포트 검색 조건에 맞는 종목들의 최종 의견과 전략별 판단을 한 번에 비교합니다.")
        from invest_bot.dashboard.streamlit_interpretations import render_interpretations_panel

        render_interpretations_panel(report_entries, service, show_reason_expander=False)

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

    render_report_candidate_cards(
        visible_entries[:4],
        service=service,
        total_count=len(visible_entries),
        selection_key=REPORT_SELECTION_KEY,
        key_prefix="report_candidate",
    )

    selected_entry_key = resolve_report_selection_from_state(visible_entries, REPORT_SELECTION_KEY)
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
    render_scroll_anchor_if_requested(REPORT_SELECTION_KEY)
    render_market_report_card(
        selected_entry["preview"],
        service,
        frame=selected_entry["frame"],
        read_preview_frame=read_preview_frame,
        load_indicator_frame_for_symbol=load_indicator_frame_for_symbol,
        favorites_store=favorites_store,
        is_favorite=bool(selected_entry["is_favorite"]),
    )


def render_report_candidate_cards(
    report_entries: list[dict[str, object]],
    *,
    service: DashboardDataService | None = None,
    total_count: int | None = None,
    selection_key: str | None = None,
    key_prefix: str = "report_candidate",
) -> None:
    with st.container(border=True):
        st.markdown('<h3 class="section-title">리포트 후보</h3>', unsafe_allow_html=True)
        st.markdown(
            '<div class="section-copy">현재 조건에서 먼저 볼 만한 종목을 카드로 요약했습니다. 자세한 본문은 아래 선택한 1건만 표시합니다.</div>',
            unsafe_allow_html=True,
        )
        st.caption(f"검색 결과 {total_count if total_count is not None else len(report_entries)}건 · 후보 카드는 최대 4건까지 표시")
    if not report_entries:
        return

    card_columns = st.columns(min(len(report_entries), 4), gap="small")
    for index, entry in enumerate(report_entries):
        column = card_columns[index % len(card_columns)]
        with column:
            symbol_label = format_symbol_display(str(entry["symbol"]), str(entry["symbol_name"]))
            favorite = "관심종목" if bool(entry.get("is_favorite")) else "일반"
            entry_frame = entry.get("frame")
            entry_row = entry_frame.iloc[-1] if isinstance(entry_frame, pd.DataFrame) and not entry_frame.empty else None
            candidate_summary = (
                localize_report_summary_from_row(service, entry_row)
                if service is not None and entry_row is not None
                else str(entry.get("summary", ""))
            )
            st.markdown(
                f"""
                <div class="symbol-focus-card">
                  <div class="symbol-focus-topline">{escape(favorite)} · {escape(str(entry["date"]))}</div>
                  <strong>{escape(symbol_label)}</strong>
                  <div class="symbol-focus-badges">
                    <span>{escape(str(entry["display_opinion"]))}</span>
                    <span>{escape(str(entry["display_trend"]))}</span>
                  </div>
                  <p>{escape(candidate_summary)}</p>
                </div>
                """,
                unsafe_allow_html=True,
            )
            if selection_key is not None and st.button(
                "이 종목 보기",
                key=build_candidate_select_button_key(key_prefix, entry),
                width="stretch",
            ):
                st.session_state[build_candidate_pending_selection_key(selection_key)] = str(entry["entry_key"])
                st.rerun()


def build_candidate_select_button_key(key_prefix: str, entry: dict[str, object]) -> str:
    raw_key = f"{key_prefix}_{entry.get('entry_key', '')}"
    safe_key = "".join(char if char.isalnum() else "_" for char in raw_key)
    return safe_key[:180]


def build_candidate_pending_selection_key(selection_key: str) -> str:
    return f"{selection_key}{CANDIDATE_PENDING_SELECTION_SUFFIX}"


def build_candidate_scroll_key(selection_key: str) -> str:
    return f"{selection_key}{CANDIDATE_SCROLL_SUFFIX}"


def render_scroll_anchor_if_requested(selection_key: str) -> None:
    st.markdown(f'<div id="{REPORT_DETAIL_ANCHOR_ID}"></div>', unsafe_allow_html=True)
    if not st.session_state.pop(build_candidate_scroll_key(selection_key), False):
        return
    components.html(
        f"""
        <script>
        const anchor = window.parent.document.getElementById("{REPORT_DETAIL_ANCHOR_ID}");
        if (anchor) {{
          anchor.scrollIntoView({{ behavior: "smooth", block: "start" }});
        }}
        </script>
        """,
        height=0,
        width=0,
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
                "date": format_report_date(row.get("date", "")),
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


def format_report_date(value: object) -> str:
    parsed = pd.to_datetime(value, errors="coerce")
    if pd.isna(parsed):
        return str(value).strip()
    return parsed.strftime("%Y-%m-%d")


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


def resolve_report_selection_from_state(
    report_entries: list[dict[str, object]],
    selection_key: str,
) -> str | None:
    pending_key = build_candidate_pending_selection_key(selection_key)
    pending_entry_key = st.session_state.pop(pending_key, None)
    if pending_entry_key is not None and get_report_entry_by_key(report_entries, str(pending_entry_key)) is not None:
        st.session_state[selection_key] = str(pending_entry_key)
        st.session_state[build_candidate_scroll_key(selection_key)] = True
    return resolve_selected_report_key(report_entries, st.session_state.get(selection_key))


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


def build_report_decision_context(row: pd.Series) -> dict[str, str]:
    """Describe observable report agreement and data coverage without implying return confidence."""
    counts = {"buy": 0, "sell": 0, "neutral": 0, "unknown": 0}
    for key in REPORT_STRATEGY_SIGNAL_KEYS:
        signal = str(row.get(key, "unknown")).strip().lower()
        if signal == "buy":
            counts["buy"] += 1
        elif signal == "sell":
            counts["sell"] += 1
        elif signal in {"hold", "watch"}:
            counts["neutral"] += 1
        else:
            counts["unknown"] += 1

    if counts["buy"] and counts["sell"]:
        agreement_label = "전략 혼재"
    elif counts["neutral"] >= max(counts["buy"], counts["sell"]):
        agreement_label = "관망 우세"
    elif counts["buy"] > counts["sell"]:
        agreement_label = "매수 방향 우세"
    elif counts["sell"] > counts["buy"]:
        agreement_label = "매도 방향 우세"
    else:
        agreement_label = "방향 신호 없음"
    agreement_detail = f"매수 {counts['buy']} · 관망 {counts['neutral']} · 매도 {counts['sell']}"
    if counts["unknown"]:
        agreement_detail += f" · 정보 부족 {counts['unknown']}"

    core_available = sum(_report_value_available(row.get(key)) for key in REPORT_CORE_DATA_KEYS)
    investor_flow = str(row.get("investor_flow", "unknown")).strip().lower()
    flow_detail = "수급 확인" if investor_flow not in {"", "unknown", "nan", "none"} else "수급 정보 부족"
    return {
        "agreement_label": agreement_label,
        "agreement_detail": agreement_detail,
        "data_detail": f"핵심 지표 {core_available}/{len(REPORT_CORE_DATA_KEYS)} · {flow_detail}",
    }


def build_report_evidence(row: pd.Series, strategy_items: list[dict[str, str]]) -> dict[str, str]:
    positive = [f"{item['label']}: {item['reason']}" for item in strategy_items if item["signal"] == "buy"]
    risks = [f"{item['label']}: {item['reason']}" for item in strategy_items if item["signal"] == "sell"]
    trend = str(row.get("trend_state", "unknown")).strip().lower()
    if trend == "bullish":
        positive.append("추세: 상승 우세")
    elif trend == "bearish":
        risks.append("추세: 하락 우세")
    if str(row.get("investor_flow", "unknown")).strip().lower() in {"", "unknown", "nan", "none"}:
        risks.append("수급: 정보 부족")

    opinion = str(row.get("final_opinion", "unknown")).strip().lower()
    if opinion == "buy":
        reassessment = "종가가 20일선 아래로 내려가거나 매도 신호가 나오면 다시 확인"
    elif opinion == "sell":
        reassessment = "5일선이 20일선을 상향 돌파하거나 추세가 개선되면 다시 확인"
    else:
        reassessment = "새 전략 신호 또는 최신 기준일이 반영되면 다시 확인"
    return {
        "positive": " · ".join(positive) if positive else "뚜렷한 매수 근거가 없습니다.",
        "risk": " · ".join(risks) if risks else "강한 하락 또는 데이터 부족 신호는 없습니다.",
        "reassessment": reassessment,
    }


def _report_value_available(value: object) -> bool:
    if value is None or isinstance(value, str) and not value.strip():
        return False
    return not bool(pd.isna(value))


def conflicting_directional_signals(row: pd.Series) -> tuple[bool, set[str]]:
    """Return whether strategy signals and the final opinion contain both buy and sell."""
    directions = {str(row.get(key, "")).strip().lower() for key in REPORT_STRATEGY_SIGNAL_KEYS}
    final_opinion = str(row.get("final_opinion", "")).strip().lower()
    if final_opinion in {"buy", "sell"}:
        directions.add(final_opinion)
    directions.discard("")
    return {"buy", "sell"}.issubset(directions), directions

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
    decision_context = build_report_decision_context(row)
    evidence = build_report_evidence(row, strategy_items)
    has_conflict, _ = conflicting_directional_signals(row)
    favorites_store = favorites_store or ReportFavoritesStore()

    with st.container(border=True):
        st.markdown(
            f"""
            <div class="report-focus-card">
              <div class="report-focus-header">
                <div>
                  <div class="muted-label">{escape(symbol_label or "종목 정보 없음")}</div>
                  <h3 class="section-title">{escape(preview.symbol_name or str(row.get("symbol_name", "")) or preview.symbol)}</h3>
                </div>
                <div class="badge badge-{escape(opinion)}">종합 신호 · {escape(opinion_label)}</div>
              </div>
              <div class="report-focus-summary">{escape(summary)}</div>
              <div class="report-decision-grid">
                <div><span>전략 합의도</span><strong>{escape(decision_context['agreement_label'])}</strong><p>{escape(decision_context['agreement_detail'])}</p></div>
                <div><span>판단 데이터</span><strong>{escape(decision_context['data_detail'])}</strong><p>수익 가능성 신뢰도가 아닌, 표시 데이터의 충족 상태입니다.</p></div>
                <div><span>기준일</span><strong>{escape(format_report_date(row.get("date", "")) or "정보 없음")}</strong><p>기준일이 오래되면 데이터 갱신 후 다시 확인합니다.</p></div>
              </div>
              <div class="report-focus-meta">
                <div><span>추세</span><strong>{escape(state_label(service, str(row.get("trend_state", "unknown"))))}</strong></div>
                <div><span>골든크로스</span><strong>{escape(state_label(service, str(row.get("golden_cross_signal", "unknown"))))}</strong></div>
                <div><span>수급</span><strong>{escape(state_label(service, str(row.get("investor_flow", "unknown"))))}</strong></div>
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

        detail_columns = st.columns(4)
        detail_columns[0].metric("종가", format_number(row.get("close")))
        detail_columns[1].metric("5일선", format_number(row.get("ma_5")))
        detail_columns[2].metric("20일선", format_number(row.get("ma_20")))
        detail_columns[3].metric("RSI 14", format_number(row.get("rsi_14")))

        st.markdown("#### 전략별 판단")
        if has_conflict:
            st.warning("전략 신호가 서로 엇갈립니다. 종합 신호는 참고 정보이며 단독 매매 결정으로 사용하지 마세요.")
        st.markdown(
            f"""
            <div class="report-evidence-grid">
              <div><span>상승 근거</span><p>{escape(evidence['positive'])}</p></div>
              <div><span>위험 요인</span><p>{escape(evidence['risk'])}</p></div>
              <div><span>재평가 기준</span><p>{escape(evidence['reassessment'])}</p></div>
            </div>
            """,
            unsafe_allow_html=True,
        )
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
