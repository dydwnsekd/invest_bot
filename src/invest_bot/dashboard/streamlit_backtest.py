from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

from invest_bot.backtest import (
    DEFAULT_BACKTEST_ADAPTER_REGISTRY,
    DEFAULT_BACKTEST_RUNNER,
    check_backtest_readiness,
    list_backtest_strategy_specs,
)
from invest_bot.backtest.adapters import GOLDEN_CROSS_SIGNALS
from invest_bot.backtest.persistence import BacktestInputSources, build_context, enrich_summary, enrich_trades
from invest_bot.backtest.strategy_registry import DAILY_PRICES_INDICATORS, INVESTOR_DAILY
from invest_bot.dashboard.service import DashboardDataService
from invest_bot.dashboard.streamlit_actions import (
    require_selected_items,
    successful_symbols_from_collection_result,
    summarize_selected_items,
)
from invest_bot.dashboard.streamlit_formatters import format_frame_for_display, format_number, format_symbol_option
from invest_bot.jobs.analyze_daily_prices import generate_indicators_for_symbol
from invest_bot.jobs.collect_market_data import (
    DEFAULT_COLLECTION_LOOKBACK_DAYS,
    MIN_REQUIRED_TRADING_DAYS,
    collect_market_data_for_symbols,
)
from invest_bot.jobs.run_golden_cross_signals import generate_golden_cross_signals_for_symbol
from invest_bot.market.symbol_lookup import ResolvedSymbol, SymbolEntry, SymbolLookup


BACKTEST_SELECTED_SYMBOLS_KEY = "backtest_selected_symbols"
BACKTEST_SELECTED_STRATEGIES_KEY = "backtest_selected_strategies"
BACKTEST_RESULTS_KEY = "backtest_results"
BACKTEST_BLOCKED_REASONS_KEY = "backtest_blocked_reasons"
BACKTEST_LOOKBACK_DAYS_KEY = "backtest_prepare_days"


@dataclass(frozen=True, slots=True)
class LoadedDataset:
    dataset: str
    filename: str | None
    frame: pd.DataFrame | None


@dataclass(frozen=True, slots=True)
class LoadedBacktestInputs:
    symbol: str
    indicator: LoadedDataset
    investor: LoadedDataset
    price: LoadedDataset
    golden_cross_signal: LoadedDataset

    def readiness_datasets(self) -> dict[str, pd.DataFrame | None]:
        return {
            DAILY_PRICES_INDICATORS: self.indicator.frame,
            INVESTOR_DAILY: self.investor.frame,
        }

    def adapter_datasets(self) -> dict[str, pd.DataFrame | None]:
        return {
            DAILY_PRICES_INDICATORS: self.indicator.frame,
            INVESTOR_DAILY: self.investor.frame,
            GOLDEN_CROSS_SIGNALS: self.golden_cross_signal.frame,
        }


def render_backtest_tab(
    snapshot,
    service: DashboardDataService,
    *,
    symbol_lookup: SymbolLookup,
) -> None:
    st.markdown('<h3 class="section-title">백테스트</h3>', unsafe_allow_html=True)
    st.markdown(
        '<div class="section-copy">선택한 종목과 전략 조합이 실제로 준비되었는지 먼저 확인한 뒤, 사용자가 직접 준비 실행과 백테스트 실행을 제어할 수 있도록 구성했습니다.</div>',
        unsafe_allow_html=True,
    )

    symbol_entries = _resolve_symbol_entries(snapshot, symbol_lookup)
    selection_map = {entry.symbol: entry for entry in symbol_entries}
    available_symbols = list(selection_map)
    strategy_specs = list_backtest_strategy_specs()
    strategy_options = [spec.strategy_id for spec in strategy_specs]
    strategy_labels = {spec.strategy_id: spec.strategy_name for spec in strategy_specs}

    if not available_symbols:
        st.warning("선택 가능한 종목 목록이 아직 없습니다. 먼저 종목 마스터 또는 수집 데이터를 준비해 주세요.")
        return

    persisted_symbols = st.session_state.get(BACKTEST_SELECTED_SYMBOLS_KEY, ["005930"])
    default_symbols = [symbol for symbol in persisted_symbols if symbol in available_symbols] or available_symbols[:1]
    persisted_strategies = st.session_state.get(BACKTEST_SELECTED_STRATEGIES_KEY, ["golden-cross"])
    default_strategies = [strategy for strategy in persisted_strategies if strategy in strategy_options] or ["golden-cross"]

    with st.container(border=True):
        st.markdown("#### 백테스트 실행 조건")
        selector_columns = st.columns(2, gap="small")
        selected_symbols = selector_columns[0].multiselect(
            "종목 선택",
            options=available_symbols,
            default=default_symbols,
            format_func=lambda symbol: format_symbol_option(selection_map[symbol]),
            key=BACKTEST_SELECTED_SYMBOLS_KEY,
        )
        selected_strategy_ids = selector_columns[1].multiselect(
            "전략 선택",
            options=strategy_options,
            default=default_strategies,
            format_func=lambda strategy_id: f"{strategy_labels[strategy_id]} ({strategy_id})",
            key=BACKTEST_SELECTED_STRATEGIES_KEY,
        )
        lookback_days = st.number_input(
            "준비용 수집 일수",
            min_value=MIN_REQUIRED_TRADING_DAYS,
            max_value=3650,
            value=int(st.session_state.get(BACKTEST_LOOKBACK_DAYS_KEY, DEFAULT_COLLECTION_LOOKBACK_DAYS)),
            step=1,
            key=BACKTEST_LOOKBACK_DAYS_KEY,
        )
        st.caption("준비 실행은 자동으로 돌지 않습니다. 버튼을 눌렀을 때만 수집 → 지표 계산 → 골든크로스 신호 생성을 수행합니다.")

        selected_items = [
            ResolvedSymbol(raw_input=symbol, symbol=symbol, symbol_name=selection_map[symbol].symbol_name)
            for symbol in selected_symbols
        ]
        loaded_inputs = {item.symbol: _load_backtest_inputs(service, item.symbol) for item in selected_items}
        readiness_payload = _build_readiness_payload(
            selected_items=selected_items,
            selected_strategy_ids=selected_strategy_ids,
            loaded_inputs=loaded_inputs,
            strategy_labels=strategy_labels,
        )

        _render_readiness_panel(readiness_payload)

        action_columns = st.columns(2, gap="small")
        if action_columns[0].button("준비 실행", width="stretch", type="primary"):
            _run_prepare_action(selected_items, int(lookback_days))
        if action_columns[1].button("백테스트 실행", width="stretch"):
            _run_backtest_action(
                selected_items=selected_items,
                selected_strategy_ids=selected_strategy_ids,
                loaded_inputs=loaded_inputs,
            )

    stored_results = st.session_state.get(BACKTEST_RESULTS_KEY)
    if isinstance(stored_results, dict):
        _render_results_panel(service, stored_results)


def _resolve_symbol_entries(snapshot, symbol_lookup: SymbolLookup) -> list[SymbolEntry]:
    entries = list(symbol_lookup.list_entries())
    if entries:
        return entries

    symbol_names: dict[str, str] = {}
    for preview in [*getattr(snapshot, "raw_previews", []), *getattr(snapshot, "processed_previews", [])]:
        symbol = str(getattr(preview, "symbol", "")).strip()
        if not symbol:
            continue
        symbol_names.setdefault(symbol, str(getattr(preview, "symbol_name", "")).strip())
    return [SymbolEntry(symbol=symbol, symbol_name=name) for symbol, name in sorted(symbol_names.items())]


def _build_readiness_payload(
    *,
    selected_items: list[ResolvedSymbol],
    selected_strategy_ids: list[str],
    loaded_inputs: dict[str, LoadedBacktestInputs],
    strategy_labels: dict[str, str],
) -> dict[str, object]:
    rows: list[dict[str, object]] = []
    blocked_reasons: list[str] = []
    ready_count = 0
    total_count = 0

    for item in selected_items:
        readiness = check_backtest_readiness(selected_strategy_ids, loaded_inputs[item.symbol].readiness_datasets())
        for strategy_result in readiness.strategy_results:
            total_count += 1
            if strategy_result.ready:
                ready_count += 1
            else:
                blocked_reasons.extend(
                    f"{item.symbol_name or item.symbol} · {strategy_result.strategy_id}: {reason}"
                    for reason in strategy_result.blocking_reasons
                )
            rows.append(
                {
                    "symbol": item.symbol,
                    "symbol_name": item.symbol_name,
                    "strategy_id": strategy_result.strategy_id,
                    "strategy_name": strategy_labels.get(strategy_result.strategy_id, strategy_result.strategy_id),
                    "ready": "준비 완료" if strategy_result.ready else "차단",
                    "blocking_reasons": " / ".join(strategy_result.blocking_reasons) if strategy_result.blocking_reasons else "-",
                }
            )

    return {
        "rows": pd.DataFrame(rows),
        "blocked_reasons": tuple(blocked_reasons),
        "ready_count": ready_count,
        "total_count": total_count,
        "can_run": total_count > 0 and ready_count == total_count,
    }


def _render_readiness_panel(payload: dict[str, object]) -> None:
    st.markdown("#### 준비 상태")
    summary_columns = st.columns(3, gap="small")
    summary_columns[0].metric("선택 조합", payload["total_count"])
    summary_columns[1].metric("준비 완료", payload["ready_count"])
    summary_columns[2].metric("실행 가능", "예" if payload["can_run"] else "아니오")

    rows = payload["rows"]
    if isinstance(rows, pd.DataFrame) and not rows.empty:
        st.dataframe(rows, width="stretch", hide_index=True)
    else:
        st.info("백테스트를 확인하려면 종목과 전략을 하나 이상 선택해 주세요.")

    blocked_reasons = payload["blocked_reasons"]
    if blocked_reasons:
        st.warning("실행 차단 사유\n- " + "\n- ".join(str(reason) for reason in blocked_reasons))


def _run_prepare_action(selected_items: list[ResolvedSymbol], lookback_days: int) -> None:
    try:
        resolved_items = require_selected_items(selected_items)
        collect_result = collect_market_data_for_symbols(
            symbols=[item.symbol for item in resolved_items],
            days=lookback_days,
        )
        successful_symbols = successful_symbols_from_collection_result(collect_result)
        failed_count = int(collect_result.get("failed_count", 0))
        if not successful_symbols:
            set_action_message(
                f"백테스트 준비 실패: {summarize_selected_items(resolved_items)} · 수집 성공 0개, 실패 {failed_count}개",
                "error",
            )
            st.rerun()
            return

        for symbol in successful_symbols:
            generate_indicators_for_symbol(symbol)
            generate_golden_cross_signals_for_symbol(symbol)

        st.session_state[BACKTEST_BLOCKED_REASONS_KEY] = ()
        suffix = "" if failed_count == 0 else f" · 수집 실패 {failed_count}개"
        set_action_message(
            f"백테스트 준비 완료: {summarize_selected_items(resolved_items)} · {len(successful_symbols)}개 준비 완료{suffix}",
            "success" if failed_count == 0 else "warning",
        )
    except Exception as error:  # noqa: BLE001
        set_action_message(f"백테스트 준비 중 오류가 발생했습니다: {error}", "error")
    st.rerun()


def _run_backtest_action(
    *,
    selected_items: list[ResolvedSymbol],
    selected_strategy_ids: list[str],
    loaded_inputs: dict[str, LoadedBacktestInputs],
) -> None:
    try:
        resolved_items = require_selected_items(selected_items)
        if not selected_strategy_ids:
            raise ValueError("백테스트 전략을 하나 이상 선택해 주세요.")

        blocking_reasons: list[str] = []
        for item in resolved_items:
            readiness = check_backtest_readiness(selected_strategy_ids, loaded_inputs[item.symbol].readiness_datasets())
            blocking_reasons.extend(
                f"{item.symbol_name or item.symbol} · {strategy_result.strategy_id}: {reason}"
                for strategy_result in readiness.strategy_results
                if not strategy_result.ready
                for reason in strategy_result.blocking_reasons
            )

        if blocking_reasons:
            st.session_state[BACKTEST_BLOCKED_REASONS_KEY] = tuple(blocking_reasons)
            st.session_state.pop(BACKTEST_RESULTS_KEY, None)
            set_action_message(
                f"백테스트 실행 차단: {len(blocking_reasons)}개 준비 문제를 해결한 뒤 다시 실행해 주세요.",
                "warning",
            )
            st.rerun()
            return

        st.session_state[BACKTEST_BLOCKED_REASONS_KEY] = ()
        result_bundle = _execute_backtests(resolved_items, selected_strategy_ids, loaded_inputs)
        st.session_state[BACKTEST_RESULTS_KEY] = result_bundle
        set_action_message(
            f"백테스트 실행 완료: {summarize_selected_items(resolved_items)} · 전략 {len(selected_strategy_ids)}개",
            "success",
        )
    except Exception as error:  # noqa: BLE001
        set_action_message(f"백테스트 실행 중 오류가 발생했습니다: {error}", "error")
    st.rerun()


def _execute_backtests(
    selected_items: list[ResolvedSymbol],
    selected_strategy_ids: list[str],
    loaded_inputs: dict[str, LoadedBacktestInputs],
) -> dict[str, object]:
    summaries: list[pd.DataFrame] = []
    trades: list[pd.DataFrame] = []
    batch_now = datetime.now(UTC)

    for item in selected_items:
        inputs = loaded_inputs[item.symbol]
        for strategy_id in selected_strategy_ids:
            adapter_output = DEFAULT_BACKTEST_ADAPTER_REGISTRY.build_signal_rows(strategy_id, inputs.adapter_datasets())
            raw_result = DEFAULT_BACKTEST_RUNNER.run(item.symbol, adapter_output.signal_rows)
            context = build_context(
                symbol=item.symbol,
                strategy_id=adapter_output.strategy_id,
                strategy_name=adapter_output.strategy_name,
                input_sources=_build_input_sources_for_strategy(strategy_id, inputs),
                now=batch_now,
            )
            summary = enrich_summary(raw_result.summary, context)
            summary["symbol_name"] = item.symbol_name
            trade_frame = enrich_trades(raw_result.trades, context)
            trade_frame["symbol_name"] = item.symbol_name
            summaries.append(summary)
            trades.append(trade_frame)

    summary_frame = pd.concat(summaries, ignore_index=True) if summaries else pd.DataFrame()
    trade_frame = pd.concat(trades, ignore_index=True) if trades else pd.DataFrame()
    comparison_frame = _build_comparison_frame(summary_frame)
    chart_frame = _build_cumulative_trade_return_frame(trade_frame)

    return {
        "summary_frame": summary_frame,
        "comparison_frame": comparison_frame,
        "trade_frame": trade_frame,
        "chart_frame": chart_frame,
        "selected_symbols": [item.symbol for item in selected_items],
        "selected_strategy_ids": list(selected_strategy_ids),
        "generated_at": batch_now.isoformat(),
    }


def _build_input_sources_for_strategy(strategy_id: str, inputs: LoadedBacktestInputs) -> BacktestInputSources:
    return BacktestInputSources(
        indicator_source_dataset=DAILY_PRICES_INDICATORS,
        indicator_source_filename=inputs.indicator.filename,
        signal_source_dataset=GOLDEN_CROSS_SIGNALS if strategy_id == "golden-cross" and inputs.golden_cross_signal.filename else None,
        signal_source_filename=inputs.golden_cross_signal.filename if strategy_id == "golden-cross" else None,
        investor_source_dataset=INVESTOR_DAILY,
        investor_source_filename=inputs.investor.filename,
        price_source_dataset="daily_prices",
        price_source_filename=inputs.price.filename,
    )


def _build_comparison_frame(summary_frame: pd.DataFrame) -> pd.DataFrame:
    if summary_frame.empty:
        return pd.DataFrame()
    columns = [
        "symbol",
        "symbol_name",
        "strategy_id",
        "strategy_name",
        "trade_count",
        "win_rate_pct",
        "average_return_pct",
        "total_return_pct",
        "max_drawdown_pct",
        "buy_signal_count",
        "sell_signal_count",
    ]
    return summary_frame[[column for column in columns if column in summary_frame.columns]].copy()


def _build_cumulative_trade_return_frame(trade_frame: pd.DataFrame) -> pd.DataFrame:
    if trade_frame.empty:
        return pd.DataFrame(columns=["trade_sequence", "cumulative_return_pct", "series_label"])

    working = trade_frame.copy()
    working["entry_date"] = pd.to_datetime(working["entry_date"], errors="coerce")
    working["return_pct"] = pd.to_numeric(working["return_pct"], errors="coerce").fillna(0.0)
    working = working.sort_values(["symbol", "strategy_id", "entry_date"]).reset_index(drop=True)
    working["trade_sequence"] = working.groupby(["symbol", "strategy_id"]).cumcount() + 1
    working["cumulative_return_pct"] = (
        working.groupby(["symbol", "strategy_id"])["return_pct"]
        .transform(lambda series: ((1.0 + (series / 100.0)).cumprod() - 1.0) * 100.0)
    )
    working["series_label"] = working.apply(
        lambda row: f"{row.get('symbol_name') or row['symbol']} · {row['strategy_name']}",
        axis=1,
    )
    return working[["trade_sequence", "cumulative_return_pct", "series_label"]].copy()


def _render_results_panel(service: DashboardDataService, result_bundle: dict[str, object]) -> None:
    summary_frame = result_bundle.get("summary_frame")
    comparison_frame = result_bundle.get("comparison_frame")
    trade_frame = result_bundle.get("trade_frame")
    chart_frame = result_bundle.get("chart_frame")

    st.markdown("#### 전략 요약 카드")
    if isinstance(summary_frame, pd.DataFrame) and not summary_frame.empty:
        card_columns = st.columns(min(len(summary_frame), 3) or 1, gap="small")
        for index, (_, row) in enumerate(summary_frame.iterrows()):
            column = card_columns[index % len(card_columns)]
            label = f"{row.get('symbol_name') or row.get('symbol')} · {row.get('strategy_name')}"
            value = f"{format_number(row.get('total_return_pct', 0.0))}%"
            delta = f"거래 {int(row.get('trade_count', 0))}건 / 승률 {format_number(row.get('win_rate_pct', 0.0))}%"
            column.metric(label, value, delta=delta)
    else:
        st.info("표시할 백테스트 결과가 아직 없습니다.")
        return

    st.markdown("#### 전략 비교표")
    st.dataframe(format_frame_for_display(comparison_frame, service), width="stretch", hide_index=True)

    st.markdown("#### 거래 순서 누적 수익률")
    if isinstance(chart_frame, pd.DataFrame) and not chart_frame.empty:
        chart = (
            alt.Chart(chart_frame)
            .mark_line(point=True)
            .encode(
                x=alt.X("trade_sequence:Q", title="거래 순서"),
                y=alt.Y("cumulative_return_pct:Q", title="누적 수익률(%)"),
                color=alt.Color("series_label:N", title="전략"),
                tooltip=["series_label:N", "trade_sequence:Q", "cumulative_return_pct:Q"],
            )
            .properties(height=320)
        )
        st.altair_chart(chart, width="stretch")
    else:
        st.info("완료된 거래가 없어 누적 수익률 차트를 아직 그릴 수 없습니다.")

    st.markdown("#### 거래 로그")
    if isinstance(trade_frame, pd.DataFrame) and not trade_frame.empty:
        trade_display = trade_frame[
            [
                column
                for column in (
                    "symbol",
                    "symbol_name",
                    "strategy_id",
                    "strategy_name",
                    "entry_signal_date",
                    "entry_date",
                    "entry_price",
                    "exit_signal_date",
                    "exit_date",
                    "exit_price",
                    "return_pct",
                    "holding_days",
                    "exit_reason",
                )
                if column in trade_frame.columns
            ]
        ].copy()
        st.dataframe(format_frame_for_display(trade_display, service), width="stretch", hide_index=True)
    else:
        st.info("이번 실행에서 생성된 거래 로그가 없습니다.")


def _load_backtest_inputs(service: DashboardDataService, symbol: str) -> LoadedBacktestInputs:
    return LoadedBacktestInputs(
        symbol=symbol,
        indicator=_load_latest_dataset(service, DAILY_PRICES_INDICATORS, symbol, root=service.processed_root),
        investor=_load_latest_dataset(service, INVESTOR_DAILY, symbol, root=service.raw_root),
        price=_load_latest_dataset(service, "daily_prices", symbol, root=service.raw_root),
        golden_cross_signal=_load_latest_dataset(service, GOLDEN_CROSS_SIGNALS, symbol, root=service.processed_root),
    )


def _load_latest_dataset(
    service: DashboardDataService,
    dataset: str,
    symbol: str,
    *,
    root: Path,
) -> LoadedDataset:
    storage = service.get_dataset_storage()
    filename = None
    if storage is not None:
        filename = storage.latest_filename(dataset, symbol)
    else:
        dataset_dir = root / dataset
        if dataset_dir.exists():
            matches = sorted(dataset_dir.glob(f"{symbol}_*.csv"), key=lambda item: item.stat().st_mtime, reverse=True)
            if matches:
                filename = matches[0].name

    if filename is None:
        return LoadedDataset(dataset=dataset, filename=None, frame=None)

    try:
        frame = storage.load(dataset, filename) if storage is not None else pd.read_csv(root / dataset / filename)
    except (FileNotFoundError, pd.errors.EmptyDataError):
        frame = None
    return LoadedDataset(dataset=dataset, filename=filename, frame=frame)


def set_action_message(message: str, message_type: str) -> None:
    st.session_state.action_message = message
    st.session_state.action_message_type = message_type
