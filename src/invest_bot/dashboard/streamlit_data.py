from __future__ import annotations

import streamlit as st

from invest_bot.dashboard.service import DashboardDataService, DatasetPreview
from invest_bot.dashboard.streamlit_charts import render_chart_selector
from invest_bot.dashboard.streamlit_formatters import format_frame_for_display, format_symbol_display


def render_data_tab(snapshot, service: DashboardDataService, *, read_preview_frame) -> None:
    st.markdown('<h3 class="section-title">데이터 탐색</h3>', unsafe_allow_html=True)
    st.markdown(
        '<div class="section-copy">원본 수집 데이터와 분석 결과를 같은 규칙으로 보여 줍니다. 먼저 추천 컬럼만 보고, 필요할 때만 자세히 펼쳐 보도록 구성했습니다.</div>',
        unsafe_allow_html=True,
    )

    raw_tab, processed_tab = st.tabs(["원본 데이터", "분석 데이터"])
    with raw_tab:
        for preview in snapshot.raw_previews:
            render_dataset_preview(preview, service, read_preview_frame=read_preview_frame)
    with processed_tab:
        for preview in snapshot.processed_previews:
            render_dataset_preview(preview, service, read_preview_frame=read_preview_frame)


def render_dataset_preview(preview: DatasetPreview, service: DashboardDataService, *, read_preview_frame) -> None:
    frame = read_preview_frame(preview)
    default_columns = [column for column in preview.recommended_columns if column in frame.columns]
    if "symbol_name" in frame.columns and "symbol_name" not in default_columns:
        default_columns.insert(0, "symbol_name")
    if "symbol_name" in default_columns and "symbol" in default_columns:
        default_columns.remove("symbol")
    if not default_columns:
        default_columns = list(frame.columns[: min(6, len(frame.columns))])

    with st.container(border=True):
        title = preview.display_name
        symbol_label = format_symbol_display(preview.symbol, preview.symbol_name)
        if symbol_label:
            title = f"{title} · {symbol_label}"
        st.markdown(f"#### {title}")
        st.caption(f"{preview.summary} · {preview.path.name}")

        meta_left, meta_right = st.columns(2)
        meta_left.metric("행 수", preview.row_count)
        meta_right.metric("컬럼 수", len(preview.columns))

        if st.toggle("차트 보기", key=f"toggle_chart_{preview.name}_{preview.symbol}_{preview.path.name}"):
            render_chart_selector(
                frame,
                dataset_name=preview.name,
                key_prefix=f"{preview.name}_{preview.symbol}_{preview.path.name}",
                height=260,
            )

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
        st.dataframe(format_frame_for_display(table.head(rows), service), width="stretch", hide_index=True)
