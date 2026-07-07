from __future__ import annotations

from collections.abc import Callable

import streamlit as st

from invest_bot.config.settings import AppSettings
from invest_bot.dashboard.streamlit_formatters import default_selected_symbols, format_symbol_display, format_symbol_option
from invest_bot.jobs.analyze_daily_prices import generate_indicators_for_symbol
from invest_bot.jobs.collect_market_data import (
    DEFAULT_COLLECTION_LOOKBACK_DAYS,
    MIN_REQUIRED_TRADING_DAYS,
    collect_market_data_for_symbols,
)
from invest_bot.jobs.run_golden_cross_signals import generate_golden_cross_signals_for_symbol
from invest_bot.jobs.run_market_report import generate_market_report_for_symbol
from invest_bot.market.symbol_lookup import ResolvedSymbol, SymbolLookup


def render_actions_tab(
    symbol_lookup: SymbolLookup,
    schedule_status,
    *,
    settings: AppSettings,
    render_schedule_status_panel: Callable[[object], None],
) -> None:
    st.markdown('<h3 class="section-title">작업 실행</h3>', unsafe_allow_html=True)
    st.markdown(
        '<div class="section-copy">선택한 여러 종목에 대해 수집부터 리포트 생성까지 배치로 실행합니다.</div>',
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

    with st.container(border=True):
        st.markdown("#### 배치 실행")
        st.caption("종목을 여러 개 선택한 뒤 필요한 단계만 따로 돌리거나 전체 파이프라인을 한 번에 실행할 수 있습니다.")

        if available_symbols:
            selected_symbols = st.multiselect(
                "종목 선택",
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
            st.caption(
                f"선택 {len(selected_items)}개 · "
                f"{', '.join(format_symbol_option(item) for item in selected_items[:3])}"
            )
        else:
            st.caption("배치 작업을 실행하려면 종목을 하나 이상 선택해 주세요.")

        days = st.number_input(
            "수집 일수",
            min_value=MIN_REQUIRED_TRADING_DAYS,
            max_value=3650,
            value=DEFAULT_COLLECTION_LOOKBACK_DAYS,
            step=1,
        )
        st.caption(f"기본값 {DEFAULT_COLLECTION_LOOKBACK_DAYS}일 · 최소 {MIN_REQUIRED_TRADING_DAYS}거래일")

        action_row_top = st.columns(2, gap="small")
        if action_row_top[0].button("데이터 수집", width="stretch", type="primary"):
            run_collect_action(selected_items, int(days))
        if action_row_top[1].button("전체 파이프라인", width="stretch"):
            run_full_pipeline_action(selected_items, int(days), settings=settings)

        action_row_bottom = st.columns(3, gap="small")
        if action_row_bottom[0].button("지표 계산", width="stretch"):
            run_batch_symbol_action(selected_items, generate_indicators_for_symbol, "지표 계산")
        if action_row_bottom[1].button("신호 생성", width="stretch"):
            run_batch_symbol_action(selected_items, generate_golden_cross_signals_for_symbol, "골든크로스 신호 생성")
        if action_row_bottom[2].button("리포트 생성", width="stretch"):
            run_market_report_batch_action(selected_items, settings=settings)


def run_collect_action(selected_items: list[ResolvedSymbol], days: int) -> None:
    try:
        resolved_items = require_selected_items(selected_items)
        result = collect_market_data_for_symbols(symbols=[item.symbol for item in resolved_items], days=days)
        label_summary = summarize_selected_items(resolved_items)
        set_action_message(
            f"데이터 수집 완료: {label_summary} · {result['success_count']}개 성공, {result['failed_count']}개 실패",
            "success" if result["failed_count"] == 0 else "info",
        )
    except Exception as error:  # noqa: BLE001
        set_action_message(f"데이터 수집 중 오류가 발생했습니다: {error}", "error")
    st.rerun()


def run_batch_symbol_action(selected_items: list[ResolvedSymbol], callback, action_name: str) -> None:
    try:
        resolved_items = require_selected_items(selected_items)
        for item in resolved_items:
            callback(item.symbol)
        set_action_message(
            f"{action_name} 완료: {summarize_selected_items(resolved_items)} · {len(resolved_items)}개 종목 처리",
            "success",
        )
    except Exception as error:  # noqa: BLE001
        set_action_message(f"{action_name} 중 오류가 발생했습니다: {error}", "error")
    st.rerun()


def run_market_report_batch_action(selected_items: list[ResolvedSymbol], *, settings: AppSettings) -> None:
    try:
        resolved_items = require_selected_items(selected_items)
        report_results = [
            generate_market_report_for_symbol(item.symbol, delivery_target="discord", settings=settings)
            for item in resolved_items
        ]
        message, message_type = summarize_report_delivery_results(report_results, selected_items=resolved_items, action_name="시장 리포트 생성")
        set_action_message(message, message_type)
    except Exception as error:  # noqa: BLE001
        set_action_message(f"시장 리포트 생성 중 오류가 발생했습니다: {error}", "error")
    st.rerun()


def run_full_pipeline_action(selected_items: list[ResolvedSymbol], days: int, *, settings: AppSettings) -> None:
    try:
        resolved_items = require_selected_items(selected_items)
        collect_result = collect_market_data_for_symbols(symbols=[item.symbol for item in resolved_items], days=days)
        report_results: list[dict[str, object]] = []
        for symbol in successful_symbols_from_collection_result(collect_result):
            generate_indicators_for_symbol(symbol)
            generate_golden_cross_signals_for_symbol(symbol)
            report_results.append(generate_market_report_for_symbol(symbol, delivery_target="discord", settings=settings))
        delivery_problem_count = count_delivery_problems(report_results)
        if delivery_problem_count > 0:
            message, message_type = summarize_report_delivery_results(
                report_results,
                selected_items=resolved_items,
                action_name="전체 파이프라인",
            )
            set_action_message(message, message_type)
        else:
            set_action_message(
                f"전체 파이프라인 완료: {summarize_selected_items(resolved_items)} · {collect_result['symbol_count']}개 종목 처리",
                "success" if collect_result["failed_count"] == 0 else "info",
            )
    except Exception as error:  # noqa: BLE001
        set_action_message(f"전체 파이프라인 실행 중 오류가 발생했습니다: {error}", "error")
    st.rerun()


def summarize_selected_items(selected_items: list[ResolvedSymbol]) -> str:
    label_summary = ", ".join(format_symbol_display(item.symbol, item.symbol_name) for item in selected_items[:3])
    suffix = "" if len(selected_items) <= 3 else f" 외 {len(selected_items) - 3}개"
    return f"{label_summary}{suffix}"


def require_selected_items(selected_items: list[ResolvedSymbol]) -> list[ResolvedSymbol]:
    if not selected_items:
        raise ValueError("자동완성 목록에서 종목을 하나 이상 선택해 주세요.")
    return selected_items


def successful_symbols_from_collection_result(result: dict[str, object]) -> list[str]:
    successful_symbols = result.get("successful_symbols")
    if isinstance(successful_symbols, list):
        return [str(symbol) for symbol in successful_symbols]
    return []


def set_action_message(message: str, message_type: str) -> None:
    st.session_state.action_message = message
    st.session_state.action_message_type = message_type


def summarize_report_delivery_results(
    report_results: list[dict[str, object]],
    *,
    selected_items: list[ResolvedSymbol],
    action_name: str,
) -> tuple[str, str]:
    delivery_problems = describe_delivery_problems(report_results, selected_items=selected_items)
    if delivery_problems:
        return (
            f"{action_name} 완료({len(report_results)}건). Discord 전송 경고: {', '.join(delivery_problems)}",
            "warning",
        )
    return (
        f"{action_name} 완료: {summarize_selected_items(selected_items)} · {len(report_results)}개 종목 처리",
        "success",
    )


def count_delivery_problems(report_results: list[dict[str, object]]) -> int:
    count = 0
    for result in report_results:
        delivery = result.get("delivery")
        if isinstance(delivery, dict) and str(delivery.get("status", "")).strip() not in {"", "sent"}:
            count += 1
    return count


def describe_delivery_problems(
    report_results: list[dict[str, object]],
    *,
    selected_items: list[ResolvedSymbol],
) -> list[str]:
    symbol_names = {item.symbol: item.symbol_name for item in selected_items}
    problems: list[str] = []
    for result in report_results:
        delivery = result.get("delivery")
        if not isinstance(delivery, dict):
            continue
        status = str(delivery.get("status", "")).strip()
        if status in {"", "sent"}:
            continue
        symbol = str(result.get("symbol", "")).strip()
        symbol_name = symbol_names.get(symbol, "")
        label = format_symbol_display(symbol, symbol_name)
        detail = normalize_delivery_detail(status, str(delivery.get("error_detail", "")).strip())
        problems.append(f"{label} {status}({detail})")
    return problems


def normalize_delivery_detail(status: str, detail: str) -> str:
    if status == "skipped" and detail == "Discord webhook URL is not configured.":
        return "웹훅 미설정"
    return detail or "-"
