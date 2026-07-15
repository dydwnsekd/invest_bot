from __future__ import annotations

from html import escape

from typing import Iterable

import streamlit as st

from invest_bot.dashboard.service import DashboardDataService, DatasetPreview
from invest_bot.dashboard.streamlit_charts import render_chart_selector
from invest_bot.dashboard.streamlit_formatters import format_frame_for_display, format_symbol_display
from invest_bot.dashboard.streamlit_state import load_professional_chart_frame_for_symbol

DATASET_DISPLAY_ORDER = {
    "stock_info": 0,
    "daily_prices_summary": 1,
    "daily_prices": 2,
    "investor_daily_summary": 3,
    "investor_daily": 4,
    "daily_prices_indicators": 5,
    "golden_cross_signals": 6,
    "market_reports": 7,
    "backtest_summaries": 8,
    "backtest_trades": 9,
}


def render_data_tab(snapshot, service: DashboardDataService, *, read_preview_frame) -> None:
    st.markdown('<h3 class="section-title">데이터 탐색</h3>', unsafe_allow_html=True)
    st.markdown(
        '<div class="section-copy">종목을 먼저 고른 뒤, 지금 확인할 만한 핵심 데이터 요약부터 보고 필요할 때만 차트와 표를 펼쳐 보도록 흐름을 정리했습니다.</div>',
        unsafe_allow_html=True,
    )

    previews = sorted(
        [*snapshot.raw_previews, *snapshot.processed_previews],
        key=lambda preview: (DATASET_DISPLAY_ORDER.get(preview.name, 99), preview.display_name, preview.path.name),
    )
    if not previews:
        st.info("표시할 데이터 미리보기가 아직 없습니다. 먼저 작업 실행 탭에서 수집 또는 분석을 실행해 주세요.")
        return

    symbol_options = build_symbol_options(previews)
    selected_symbol = st.selectbox(
        "조회할 종목",
        options=symbol_options,
        format_func=lambda symbol: format_symbol_option(symbol, previews),
        key="data_symbol_filter",
    )

    selected_previews = previews_for_symbol(previews, selected_symbol)
    symbol_label = escape(format_symbol_option(selected_symbol, previews))

    overview_left, overview_right = st.columns((1.4, 1))
    with overview_left:
        st.markdown(
            f"<div class=\"summary-box\"><div class=\"muted-label\">선택된 보기</div><div><strong>{symbol_label}</strong></div><div class=\"section-copy\">핵심 데이터 {len(selected_previews)}개를 우선 정리해 보여줍니다.</div></div>",
            unsafe_allow_html=True,
        )
    with overview_right:
        st.markdown(
            "<div class=\"summary-box\"><div class=\"muted-label\">보는 순서</div><div><strong>요약 → 해석 포인트 → 상세 표/차트</strong></div><div class=\"section-copy\">표는 꼭 필요할 때만 펼쳐 확인하도록 배치했습니다.</div></div>",
            unsafe_allow_html=True,
        )

    for preview in selected_previews:
        render_dataset_summary_card(preview, service, read_preview_frame=read_preview_frame)


def build_symbol_options(previews: Iterable[DatasetPreview]) -> list[str]:
    options: list[str] = []
    seen: set[str] = set()
    for preview in previews:
        symbol = normalized_preview_symbol(preview)
        if symbol in seen:
            continue
        seen.add(symbol)
        options.append(symbol)
    return options


def normalized_preview_symbol(preview: DatasetPreview) -> str:
    return str(preview.symbol).strip() or "__COMMON__"


def format_symbol_option(symbol: str, previews: Iterable[DatasetPreview]) -> str:
    if symbol == "__COMMON__":
        return "공통 / 미분류 데이터"
    for preview in previews:
        if normalized_preview_symbol(preview) == symbol:
            return format_symbol_display(preview.symbol, preview.symbol_name)
    return symbol


def previews_for_symbol(previews: Iterable[DatasetPreview], symbol: str) -> list[DatasetPreview]:
    matched = [preview for preview in previews if normalized_preview_symbol(preview) == symbol]
    if matched:
        return matched
    return list(previews)


def render_dataset_summary_card(preview: DatasetPreview, service: DashboardDataService, *, read_preview_frame) -> None:
    frame = read_preview_frame(preview)
    quick_table = build_default_table(frame, preview)
    title = preview.display_name
    symbol_label = format_symbol_display(preview.symbol, preview.symbol_name)
    if symbol_label:
        title = f"{title} · {symbol_label}"

    safe_summary = escape(preview.summary)
    safe_purpose = escape(preview.purpose)
    safe_first_look = escape(preview.first_look)

    with st.container(border=True):
        st.markdown(f"#### {title}")
        st.markdown(
            f"<div class=\"summary-box\"><div><strong>무슨 데이터인가요?</strong></div><div>{safe_summary}</div><div style=\"margin-top:0.55rem;\"><strong>이 데이터를 왜 보나요?</strong></div><div>{safe_purpose}</div><div style=\"margin-top:0.55rem;\"><strong>먼저 볼 포인트</strong></div><div>{safe_first_look}</div></div>",
            unsafe_allow_html=True,
        )
        st.caption(f"파일: {preview.path.name}")

        meta_left, meta_center, meta_right = st.columns(3)
        meta_left.metric("행 수", preview.row_count)
        meta_center.metric("컬럼 수", len(preview.columns))
        meta_right.metric("추천 컬럼", len(quick_table.columns))

        st.markdown("**빠른 미리보기**")
        st.dataframe(format_frame_for_display(quick_table, service), width="stretch", hide_index=True)

        with st.expander("차트 · 전체 표 · 컬럼 설명 자세히 보기"):
            render_dataset_detail(preview, frame, service)


def render_dataset_detail(preview: DatasetPreview, frame, service: DashboardDataService) -> None:
    if st.toggle("차트 보기", key=f"toggle_chart_{preview.name}_{preview.symbol}_{preview.path.name}"):
        chart_frame = frame
        if (
            preview.name in {"daily_prices", "daily_prices_indicators"}
            and str(preview.symbol).strip()
        ):
            professional_frame = load_professional_chart_frame_for_symbol(service, preview.symbol)
            if professional_frame is not None:
                chart_frame = professional_frame
        render_chart_selector(
            chart_frame,
            dataset_name=preview.name,
            key_prefix=f"{preview.name}_{preview.symbol}_{preview.path.name}",
            height=260,
        )

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

    default_columns = default_columns_for_preview(preview, frame)
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

    table = frame[selected_columns] if selected_columns else frame
    st.dataframe(format_frame_for_display(table.head(rows), service), width="stretch", hide_index=True)


def default_columns_for_preview(preview: DatasetPreview, frame) -> list[str]:
    default_columns = [column for column in preview.recommended_columns if column in frame.columns]
    if "symbol_name" in frame.columns and "symbol_name" not in default_columns:
        default_columns.insert(0, "symbol_name")
    if "symbol_name" in default_columns and "symbol" in default_columns:
        default_columns.remove("symbol")
    if not default_columns:
        default_columns = list(frame.columns[: min(6, len(frame.columns))])
    return default_columns


def build_default_table(frame, preview: DatasetPreview):
    default_columns = default_columns_for_preview(preview, frame)
    table = frame[default_columns] if default_columns else frame
    return table.head(min(max(1, len(table)), 5))
