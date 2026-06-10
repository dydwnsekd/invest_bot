from __future__ import annotations

from collections.abc import Callable

import streamlit as st

from invest_bot.dashboard.streamlit_formatters import (
    default_selected_symbols,
    default_single_symbol,
    format_symbol_display,
    format_symbol_option,
)
from invest_bot.jobs.analyze_daily_prices import generate_indicators_for_symbol
from invest_bot.jobs.collect_market_data import collect_market_data_for_symbols
from invest_bot.jobs.run_golden_cross_signals import generate_golden_cross_signals_for_symbol
from invest_bot.jobs.run_market_report import generate_market_report_for_symbol
from invest_bot.market.symbol_lookup import ResolvedSymbol, SymbolLookup


def render_actions_tab(
    symbol_lookup: SymbolLookup,
    schedule_status,
    *,
    render_schedule_status_panel: Callable[[object], None],
) -> None:
    st.markdown('<h3 class="section-title">작업 실행</h3>', unsafe_allow_html=True)
    st.markdown(
        '<div class="section-copy">수집부터 리포트 생성까지 필요한 작업을 여기서 바로 실행합니다.</div>',
        unsafe_allow_html=True,
    )

    if schedule_status is not None:
        render_schedule_status_panel(schedule_status)
        st.markdown("<div style='height:0.8rem'></div>", unsafe_allow_html=True)

    symbol_entries = symbol_lookup.list_entries()
    selection_map = {entry.symbol: entry for entry in symbol_entries}
    available_symbols = list(selection_map.keys())
    default_multi_symbols = default_selected_symbols(
        available_symbols,
        st.session_state.get("streamlit_selected_symbols", ["005930"]),
    )
    default_single = default_single_symbol(
        available_symbols,
        st.session_state.get("streamlit_single_symbol", "005930"),
    )

    with st.container(border=True):
        st.markdown("#### 여러 종목 작업")
        st.caption("데이터 수집과 전체 파이프라인처럼 여러 종목을 한 번에 돌리는 작업입니다.")
        if available_symbols:
            selected_symbols = st.multiselect(
                "여러 종목 선택",
                options=available_symbols,
                default=default_multi_symbols,
                format_func=lambda symbol: format_symbol_option(selection_map[symbol]),
                help="종목명 또는 종목코드를 입력하면 자동완성된 전체 목록에서 선택할 수 있습니다.",
                placeholder="예: 삼성전자, SK하이닉스",
                key="multi_symbol_picker",
            )
        else:
            selected_symbols = []
            st.warning("선택 가능한 종목 목록이 아직 없습니다. 먼저 종목 마스터 또는 stock_info 데이터를 준비해 주세요.")
        st.session_state.streamlit_selected_symbols = selected_symbols
        selected_items = [
            ResolvedSymbol(raw_input=symbol, symbol=symbol, symbol_name=selection_map[symbol].symbol_name)
            for symbol in selected_symbols
        ]
        if selected_items:
            st.caption(f"선택된 종목 {len(selected_items)}개: {', '.join(format_symbol_option(item) for item in selected_items[:4])}")
        else:
            st.caption("여러 종목 작업을 실행하려면 자동완성 목록에서 종목을 하나 이상 선택해 주세요.")
        days = st.number_input("수집 일수", min_value=1, max_value=3650, value=30, step=1)
        multi_columns = st.columns(2, gap="small")
        if multi_columns[0].button("데이터 수집", width="stretch", type="primary"):
            run_collect_action(selected_items, int(days))
        if multi_columns[1].button("전체 파이프라인", width="stretch"):
            run_full_pipeline_action(selected_items, int(days))

    st.markdown("<div style='height:0.8rem'></div>", unsafe_allow_html=True)
    with st.container(border=True):
        st.markdown("#### 한 종목 작업")
        st.caption("지표 계산, 신호 생성, 리포트 생성처럼 한 종목씩 확인하면서 실행하는 작업입니다.")
        if available_symbols:
            primary_symbol = st.selectbox(
                "한 종목 선택",
                options=available_symbols,
                index=available_symbols.index(default_single) if default_single in available_symbols else 0,
                format_func=lambda symbol: format_symbol_option(selection_map[symbol]),
                help="종목명 또는 종목코드로 검색해서 한 종목만 선택합니다.",
                key="single_symbol_picker",
            )
            st.session_state.streamlit_single_symbol = primary_symbol
            primary_item = ResolvedSymbol(
                raw_input=primary_symbol,
                symbol=primary_symbol,
                symbol_name=selection_map[primary_symbol].symbol_name,
            )
            st.caption(f"현재 선택: {format_symbol_option(primary_item)}")
        else:
            primary_item = None
            st.caption("한 종목 작업을 실행하려면 선택 가능한 종목 목록이 먼저 준비되어야 합니다.")
        single_columns = st.columns(3, gap="small")
        if single_columns[0].button("지표 계산", width="stretch"):
            run_single_symbol_action(primary_item, generate_indicators_for_symbol, "지표 계산")
        if single_columns[1].button("신호 생성", width="stretch"):
            run_single_symbol_action(primary_item, generate_golden_cross_signals_for_symbol, "골든크로스 신호 생성")
        if single_columns[2].button("리포트 생성", width="stretch"):
            run_single_symbol_action(primary_item, generate_market_report_for_symbol, "시장 리포트 생성")

    st.markdown("<div style='height:0.8rem'></div>", unsafe_allow_html=True)
    with st.container(border=True):
        st.markdown("#### 실행 가이드")
        st.markdown(
            """
            - `여러 종목 작업`: 데이터 수집, 전체 파이프라인처럼 배치 실행이 자연스러운 작업입니다.
            - `한 종목 작업`: 지표 계산, 신호 생성, 리포트 생성처럼 결과를 한 종목씩 확인하기 좋은 작업입니다.
            - `데이터 수집`: KIS에서 원본 데이터를 내려받습니다.
            - `전체 파이프라인`: 수집 후 지표 계산, 신호 생성, 리포트 생성까지 한 번에 실행합니다.
            - `지표 계산 / 신호 생성 / 리포트 생성`: 선택한 한 종목만 대상으로 실행합니다.
            """
        )


def run_collect_action(selected_items: list[ResolvedSymbol], days: int) -> None:
    try:
        resolved_items = require_selected_items(selected_items)
        result = collect_market_data_for_symbols(symbols=[item.symbol for item in resolved_items], days=days)
        label_summary = ", ".join(format_symbol_display(item.symbol, item.symbol_name) for item in resolved_items[:3])
        suffix = "" if len(resolved_items) <= 3 else f" 외 {len(resolved_items) - 3}개"
        set_action_message(
            f"데이터 수집 완료: {label_summary}{suffix} · {result['success_count']}개 성공, {result['failed_count']}개 실패",
            "success" if result["failed_count"] == 0 else "info",
        )
    except Exception as error:  # noqa: BLE001
        set_action_message(f"데이터 수집 중 오류가 발생했습니다: {error}", "error")
    st.rerun()


def run_single_symbol_action(selected_item: ResolvedSymbol | None, callback, action_name: str) -> None:
    try:
        resolved = require_single_selected_item(selected_item)
        result = callback(resolved.symbol)
        set_action_message(
            f"{action_name} 완료: {format_symbol_display(resolved.symbol, resolved.symbol_name)} · {result['saved_path']}",
            "success",
        )
    except Exception as error:  # noqa: BLE001
        set_action_message(f"{action_name} 중 오류가 발생했습니다: {error}", "error")
    st.rerun()


def run_full_pipeline_action(selected_items: list[ResolvedSymbol], days: int) -> None:
    try:
        resolved_items = require_selected_items(selected_items)
        collect_result = collect_market_data_for_symbols(symbols=[item.symbol for item in resolved_items], days=days)
        for symbol in collect_result["symbols"]:
            generate_indicators_for_symbol(symbol)
            generate_golden_cross_signals_for_symbol(symbol)
            generate_market_report_for_symbol(symbol)
        label_summary = ", ".join(format_symbol_display(item.symbol, item.symbol_name) for item in resolved_items[:3])
        suffix = "" if len(resolved_items) <= 3 else f" 외 {len(resolved_items) - 3}개"
        set_action_message(
            f"전체 파이프라인 완료: {label_summary}{suffix} · {collect_result['symbol_count']}개 종목 처리",
            "success" if collect_result["failed_count"] == 0 else "info",
        )
    except Exception as error:  # noqa: BLE001
        set_action_message(f"전체 파이프라인 실행 중 오류가 발생했습니다: {error}", "error")
    st.rerun()


def require_selected_items(selected_items: list[ResolvedSymbol]) -> list[ResolvedSymbol]:
    if not selected_items:
        raise ValueError("자동완성 목록에서 종목을 하나 이상 선택해 주세요.")
    return selected_items


def require_single_selected_item(selected_item: ResolvedSymbol | None) -> ResolvedSymbol:
    if selected_item is None:
        raise ValueError("단일 작업을 실행하려면 대상 종목을 하나 선택해 주세요.")
    return selected_item


def set_action_message(message: str, message_type: str) -> None:
    st.session_state.action_message = message
    st.session_state.action_message_type = message_type
