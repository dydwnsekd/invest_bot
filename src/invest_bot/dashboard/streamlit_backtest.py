from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from html import escape
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

from invest_bot.backtest import (
    DEFAULT_BACKTEST_ADAPTER_REGISTRY,
    DEFAULT_BACKTEST_RUNNER,
    DEFAULT_MARK_TO_MARKET_INITIAL_EQUITY,
    build_daily_mark_to_market_equity_curve,
    check_backtest_readiness,
    list_backtest_strategy_specs,
)
from invest_bot.backtest.adapters import GOLDEN_CROSS_SIGNALS
from invest_bot.backtest.persistence import BacktestInputSources, build_context, enrich_summary, enrich_trades
from invest_bot.backtest.strategy_registry import DAILY_PRICES_INDICATORS, INVESTOR_DAILY
from invest_bot.dashboard.service import DashboardDataService
from invest_bot.dashboard.streamlit_collection_period import (
    collection_days_from_period,
    collection_period_bounds,
    default_collection_period,
    normalize_collection_period,
)
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
BACKTEST_COLLECTION_PERIOD_KEY = "backtest_prepare_collection_period"
BACKTEST_HISTORY_SELECTION_KEY = "backtest_history_selection"
BACKTEST_HISTORY_NONE_OPTION = "__backtest_history_none__"
BACKTEST_HISTORY_SYMBOL_FILTER_KEY = "backtest_history_symbol_filter"
BACKTEST_HISTORY_STRATEGY_FILTER_KEY = "backtest_history_strategy_filter"


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

    _render_backtest_flow_cards()

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
        min_period_date, max_period_date = collection_period_bounds()
        selected_period = st.date_input(
            "준비용 수집 조회 기간",
            value=default_collection_period(),
            min_value=min_period_date,
            max_value=max_period_date,
            key=BACKTEST_COLLECTION_PERIOD_KEY,
        )
        collection_period = normalize_collection_period(selected_period)
        lookback_days = collection_days_from_period(collection_period)
        st.caption("준비 실행은 자동으로 돌지 않습니다. 버튼을 눌렀을 때만 수집, 지표 계산, 골든크로스 신호 생성을 순서대로 수행합니다.")

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

        _render_backtest_selection_summary(selected_items, selected_strategy_ids, strategy_labels, int(lookback_days))
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

    history_results = _render_backtest_history_panel(service)
    if isinstance(history_results, dict):
        st.markdown("#### 선택한 저장 이력 결과")
        _render_results_panel(service, history_results)

    stored_results = st.session_state.get(BACKTEST_RESULTS_KEY)
    if isinstance(stored_results, dict):
        if isinstance(history_results, dict):
            st.markdown("#### 이번 세션 실행 결과")
        _render_results_panel(service, stored_results)


def _render_backtest_flow_cards() -> None:
    st.markdown(
        """
        <div class="streamlit-card backtest-flow-card">
          <h3 class="section-title">전략 검증 흐름</h3>
          <div class="section-copy">종목과 전략을 먼저 고른 뒤 준비 상태를 확인하고, 결과는 수익률·승률·거래 로그 순서로 읽습니다.</div>
          <div class="backtest-step-grid">
            <div><span>1</span><strong>종목 선택</strong><p>검증할 관심 종목을 고릅니다.</p></div>
            <div><span>2</span><strong>전략 선택</strong><p>비교할 전략을 여러 개 선택합니다.</p></div>
            <div><span>3</span><strong>준비 확인</strong><p>필요 데이터와 차단 사유를 확인합니다.</p></div>
            <div><span>4</span><strong>결과 비교</strong><p>수익률, 승률, 거래 기록을 비교합니다.</p></div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_backtest_selection_summary(
    selected_items: list[ResolvedSymbol],
    selected_strategy_ids: list[str],
    strategy_labels: dict[str, str],
    lookback_days: int,
) -> None:
    symbols = ", ".join(item.symbol_name or item.symbol for item in selected_items) or "선택 없음"
    strategies = ", ".join(strategy_labels.get(strategy_id, strategy_id) for strategy_id in selected_strategy_ids) or "선택 없음"
    st.markdown(
        f"""
        <div class="selection-summary-card">
          <div><span>선택 종목</span><strong>{escape(symbols)}</strong></div>
          <div><span>선택 전략</span><strong>{escape(strategies)}</strong></div>
          <div><span>준비 조회 기간</span><strong>최근 {lookback_days}일 기준</strong></div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_backtest_history_panel(service: DashboardDataService) -> dict[str, object] | None:
    with st.container(border=True):
        st.markdown("#### 저장된 실행 이력")
        st.caption("이력을 선택하면 저장된 요약과 거래 로그만 읽습니다. 선택만으로 백테스트를 다시 실행하지 않습니다.")
        entries, load_messages = _load_backtest_history_entries(service)
        for message in load_messages:
            st.warning(message)
        if not entries:
            st.info("아직 불러올 저장된 백테스트 실행 이력이 없습니다.")
            return None

        filter_columns = st.columns(2, gap="small")
        selected_symbols = filter_columns[0].multiselect(
            "이력 종목 필터",
            options=sorted({str(entry["symbol"]) for entry in entries if entry.get("symbol")}),
            key=BACKTEST_HISTORY_SYMBOL_FILTER_KEY,
        )
        selected_strategies = filter_columns[1].multiselect(
            "이력 전략 필터",
            options=sorted({str(entry["strategy_id"]) for entry in entries if entry.get("strategy_id")}),
            format_func=lambda strategy_id: next(
                (
                    str(entry["strategy_name"])
                    for entry in entries
                    if entry.get("strategy_id") == strategy_id and entry.get("strategy_name")
                ),
                strategy_id,
            ),
            key=BACKTEST_HISTORY_STRATEGY_FILTER_KEY,
        )
        filtered_entries = _filter_backtest_history_entries(entries, selected_symbols, selected_strategies)
        if not filtered_entries:
            st.info("선택한 종목·전략 조건과 일치하는 저장 이력이 없습니다. 필터를 조정해 주세요.")
            return None

        st.dataframe(_build_backtest_history_table(filtered_entries), width="stretch", hide_index=True)
        entries_by_id = {str(entry["entry_id"]): entry for entry in filtered_entries}
        options = [BACKTEST_HISTORY_NONE_OPTION, *entries_by_id]
        if st.session_state.get(BACKTEST_HISTORY_SELECTION_KEY) not in options:
            st.session_state[BACKTEST_HISTORY_SELECTION_KEY] = BACKTEST_HISTORY_NONE_OPTION
        selected_entry_id = st.selectbox(
            "확인할 저장 이력",
            options=options,
            format_func=lambda entry_id: (
                "저장된 실행 이력을 선택하세요"
                if entry_id == BACKTEST_HISTORY_NONE_OPTION
                else _format_backtest_history_option(entries_by_id[entry_id])
            ),
            key=BACKTEST_HISTORY_SELECTION_KEY,
        )
        if selected_entry_id == BACKTEST_HISTORY_NONE_OPTION:
            return None

        selected_entry = entries_by_id.get(str(selected_entry_id))
        if selected_entry is None:
            st.warning("선택한 실행 이력을 찾을 수 없습니다. 목록을 다시 선택해 주세요.")
            return None
        result_bundle, result_messages = _load_backtest_history_result(service, selected_entry)
        for message in result_messages:
            st.warning(message)
        if result_bundle is None:
            st.warning("선택한 실행 이력의 요약 결과를 읽을 수 없습니다.")
            return None
        st.caption(
            f"저장된 실행 시각: {_format_history_timestamp(selected_entry.get('run_at'))} · "
            f"데이터 원본: {selected_entry.get('source_label') or '기록 없음'}"
        )
        return result_bundle


def _load_backtest_history_entries(service: DashboardDataService) -> tuple[list[dict[str, object]], tuple[str, ...]]:
    try:
        previews = service.list_backtest_history_previews("backtest_summaries")
    except Exception as error:  # noqa: BLE001 - history is optional dashboard context
        return [], (f"저장된 실행 이력 목록을 읽지 못했습니다: {error}",)

    entries: list[dict[str, object]] = []
    messages: list[str] = []
    for preview in previews:
        try:
            frame = service.load_preview_frame(preview)
        except Exception as error:  # noqa: BLE001 - show the artifact issue without blocking the tab
            messages.append(f"저장 이력 파일을 읽지 못했습니다 ({preview.path.name}): {error}")
            continue
        if frame.empty:
            messages.append(f"저장 이력 파일에 표시할 요약 결과가 없습니다: {preview.path.name}")
            continue
        for row_index, (_, row) in enumerate(frame.iterrows()):
            run_id = _history_text(row, "run_id")
            symbol = _history_text(row, "symbol") or str(getattr(preview, "symbol", "")).strip()
            strategy_id = _history_text(row, "strategy_id")
            strategy_name = _history_text(row, "strategy_name") or strategy_id or "전략 정보 없음"
            symbol_name = _history_text(row, "symbol_name") or str(getattr(preview, "symbol_name", "")).strip()
            source_label = _history_text(row, "signal_source_filename") or _history_text(row, "price_source_filename")
            run_at = _parse_history_run_timestamp(run_id) or getattr(preview, "created_at", None)
            entries.append(
                {
                    "entry_id": f"{preview.path.name}:{row_index}:{run_id or 'legacy'}",
                    "preview": preview,
                    "summary_frame": pd.DataFrame([row.to_dict()]),
                    "run_id": run_id,
                    "run_group_id": _history_text(row, "run_group_id"),
                    "symbol": symbol,
                    "symbol_name": symbol_name,
                    "strategy_id": strategy_id,
                    "strategy_name": strategy_name,
                    "source_label": source_label,
                    "run_at": run_at,
                }
            )
    entries.sort(key=lambda entry: entry.get("run_at") or datetime.min.replace(tzinfo=UTC), reverse=True)
    return entries, tuple(messages)


def _filter_backtest_history_entries(
    entries: list[dict[str, object]],
    selected_symbols: list[str],
    selected_strategy_ids: list[str],
) -> list[dict[str, object]]:
    symbol_filter = set(selected_symbols)
    strategy_filter = set(selected_strategy_ids)
    return [
        entry
        for entry in entries
        if (not symbol_filter or str(entry.get("symbol", "")) in symbol_filter)
        and (not strategy_filter or str(entry.get("strategy_id", "")) in strategy_filter)
    ]


def _load_backtest_history_result(
    service: DashboardDataService,
    entry: dict[str, object],
) -> tuple[dict[str, object] | None, tuple[str, ...]]:
    summary_frame = entry.get("summary_frame")
    if not isinstance(summary_frame, pd.DataFrame) or summary_frame.empty:
        return None, ("저장된 실행 이력에 요약 결과가 없습니다.",)

    summary_frame = summary_frame.copy()
    if "symbol_name" not in summary_frame.columns:
        summary_frame["symbol_name"] = str(entry.get("symbol_name", ""))
    elif summary_frame["symbol_name"].isna().all():
        summary_frame["symbol_name"] = str(entry.get("symbol_name", ""))

    messages: list[str] = []
    trade_frame, trade_messages = _load_history_trade_frame(service, str(entry.get("run_id", "")))
    messages.extend(trade_messages)
    daily_equity_frame, daily_message = _load_history_daily_equity_frame(service, summary_frame, entry, trade_frame)
    return {
        "summary_frame": summary_frame,
        "comparison_frame": _build_comparison_frame(summary_frame),
        "trade_frame": trade_frame,
        "chart_frame": _build_cumulative_trade_return_frame(trade_frame),
        "daily_equity_frame": daily_equity_frame,
        "daily_equity_notice": daily_message,
        "history_warnings": tuple(messages),
    }, tuple()


def _load_history_trade_frame(service: DashboardDataService, run_id: str) -> tuple[pd.DataFrame, tuple[str, ...]]:
    if not run_id:
        return pd.DataFrame(), ("이 실행 이력에는 run_id가 없어 연결된 거래 로그를 확인할 수 없습니다.",)
    frames: list[pd.DataFrame] = []
    messages: list[str] = []
    try:
        previews = service.list_backtest_history_previews("backtest_trades")
    except Exception as error:  # noqa: BLE001
        return pd.DataFrame(), (f"저장된 거래 로그 목록을 읽지 못했습니다: {error}",)
    for preview in previews:
        if run_id not in preview.path.name:
            continue
        try:
            frame = service.load_preview_frame(preview)
        except Exception as error:  # noqa: BLE001
            messages.append(f"거래 로그 파일을 읽지 못했습니다 ({preview.path.name}): {error}")
            continue
        if "run_id" not in frame.columns:
            messages.append(f"거래 로그에 run_id가 없어 이력과 연결할 수 없습니다: {preview.path.name}")
            continue
        matched = frame[frame["run_id"].astype(str) == run_id].copy()
        if not matched.empty:
            frames.append(matched)
    if not frames:
        messages.append("연결된 거래 로그가 없어 누적 수익률과 거래 내역은 표시하지 않습니다.")
        return pd.DataFrame(), tuple(messages)
    return pd.concat(frames, ignore_index=True), tuple(messages)


def _load_history_daily_equity_frame(
    service: DashboardDataService,
    summary_frame: pd.DataFrame,
    entry: dict[str, object],
    trade_frame: pd.DataFrame,
) -> tuple[pd.DataFrame, str | None]:
    summary_row = summary_frame.iloc[0]
    dataset = _history_text(summary_row, "signal_source_dataset")
    filename = _history_text(summary_row, "signal_source_filename")
    if not dataset or not filename:
        return pd.DataFrame(), "저장된 신호 원본 정보가 없어 이 실행 이력의 일별 평가금액은 복원할 수 없습니다."
    if Path(filename).name != filename:
        return pd.DataFrame(), "저장된 신호 원본 파일명이 올바르지 않아 일별 평가금액을 복원하지 않았습니다."
    try:
        storage = service.get_dataset_storage()
        if storage is not None:
            signal_frame = storage.load(dataset, filename)
        else:
            candidates = (service.processed_root / dataset / filename, service.raw_root / dataset / filename)
            signal_path = next((path for path in candidates if path.exists()), None)
            if signal_path is None:
                raise FileNotFoundError(filename)
            signal_frame = pd.read_csv(signal_path)
    except (FileNotFoundError, pd.errors.EmptyDataError) as error:
        return pd.DataFrame(), f"신호 원본을 찾을 수 없어 일별 평가금액을 복원하지 못했습니다: {error}"
    except Exception as error:  # noqa: BLE001
        return pd.DataFrame(), f"신호 원본을 읽지 못해 일별 평가금액을 복원하지 못했습니다: {error}"
    try:
        daily_equity_frame = build_daily_mark_to_market_equity_curve(signal_frame, trade_frame)
    except Exception as error:  # noqa: BLE001
        return pd.DataFrame(), f"저장된 신호로 일별 평가금액을 계산하지 못했습니다: {error}"
    if daily_equity_frame.empty:
        return daily_equity_frame, "저장된 신호에는 일별 평가금액을 계산할 가격 데이터가 없습니다."
    symbol = str(entry.get("symbol", ""))
    symbol_name = str(entry.get("symbol_name", ""))
    strategy_id = str(entry.get("strategy_id", ""))
    strategy_name = str(entry.get("strategy_name", ""))
    daily_equity_frame["symbol"] = symbol
    daily_equity_frame["symbol_name"] = symbol_name
    daily_equity_frame["strategy_id"] = strategy_id
    daily_equity_frame["strategy_name"] = strategy_name
    daily_equity_frame["series_label"] = f"{symbol_name or symbol} · {strategy_name or strategy_id}"
    return daily_equity_frame, None


def _build_backtest_history_table(entries: list[dict[str, object]]) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "실행 시각": _format_history_timestamp(entry.get("run_at")),
                "종목": f"{entry.get('symbol_name') or entry.get('symbol') or '정보 없음'} ({entry.get('symbol') or '-'})",
                "전략": entry.get("strategy_name") or entry.get("strategy_id") or "정보 없음",
                "데이터 원본": entry.get("source_label") or "기록 없음",
            }
            for entry in entries
        ]
    )


def _format_backtest_history_option(entry: dict[str, object]) -> str:
    symbol = entry.get("symbol_name") or entry.get("symbol") or "정보 없음"
    strategy = entry.get("strategy_name") or entry.get("strategy_id") or "전략 정보 없음"
    return f"{_format_history_timestamp(entry.get('run_at'))} · {symbol} · {strategy}"


def _format_history_timestamp(value: object) -> str:
    if isinstance(value, datetime):
        return value.astimezone(UTC).strftime("%Y-%m-%d %H:%M UTC")
    return "실행 시각 기록 없음"


def _parse_history_run_timestamp(run_id: str) -> datetime | None:
    timestamp = run_id.rsplit("_", 1)[-1] if "_" in run_id else ""
    try:
        return datetime.strptime(timestamp, "%Y%m%dT%H%M%SZ").replace(tzinfo=UTC)
    except ValueError:
        return None


def _history_text(row: pd.Series, column: str) -> str:
    value = row.get(column, "")
    return "" if pd.isna(value) else str(value).strip()


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
        cards = []
        for _, row in rows.head(6).iterrows():
            state_class = "ready" if str(row.get("ready")) == "준비 완료" else "blocked"
            cards.append(
                f"""
                <div class="readiness-card readiness-card-{state_class}">
                  <div class="readiness-symbol">{escape(str(row.get("symbol_name") or row.get("symbol") or ""))}</div>
                  <strong>{escape(str(row.get("strategy_name") or row.get("strategy_id") or ""))}</strong>
                  <span>{escape(str(row.get("ready", "")))}</span>
                  <p>{escape(str(row.get("blocking_reasons", "")))}</p>
                </div>
                """,
            )
        st.markdown(f'<div class="readiness-card-grid">{"".join(cards)}</div>', unsafe_allow_html=True)
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
    daily_equity_curves: list[pd.DataFrame] = []
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
            daily_equity_curve = build_daily_mark_to_market_equity_curve(
                adapter_output.signal_rows,
                raw_result.trades,
            )
            daily_equity_curve["symbol"] = item.symbol
            daily_equity_curve["symbol_name"] = item.symbol_name
            daily_equity_curve["strategy_id"] = adapter_output.strategy_id
            daily_equity_curve["strategy_name"] = adapter_output.strategy_name
            daily_equity_curve["series_label"] = f"{item.symbol_name or item.symbol} · {adapter_output.strategy_name}"
            summaries.append(summary)
            trades.append(trade_frame)
            daily_equity_curves.append(daily_equity_curve)

    summary_frame = pd.concat(summaries, ignore_index=True) if summaries else pd.DataFrame()
    trade_frame = pd.concat(trades, ignore_index=True) if trades else pd.DataFrame()
    daily_equity_frame = pd.concat(daily_equity_curves, ignore_index=True) if daily_equity_curves else pd.DataFrame()
    comparison_frame = _build_comparison_frame(summary_frame)
    chart_frame = _build_cumulative_trade_return_frame(trade_frame)

    return {
        "summary_frame": summary_frame,
        "comparison_frame": comparison_frame,
        "trade_frame": trade_frame,
        "chart_frame": chart_frame,
        "daily_equity_frame": daily_equity_frame,
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


def _numeric_row_value(row: pd.Series, key: str, default: float = 0.0) -> float:
    value = pd.to_numeric(pd.Series([row.get(key, default)]), errors="coerce").iloc[0]
    if pd.isna(value):
        return default
    return float(value)


def build_backtest_result_interpretation(row: pd.Series) -> str:
    trade_count = int(_numeric_row_value(row, "trade_count", 0.0))
    total_return = _numeric_row_value(row, "total_return_pct", 0.0)
    win_rate = _numeric_row_value(row, "win_rate_pct", 0.0)
    average_return = _numeric_row_value(row, "average_return_pct", 0.0)
    max_drawdown = _numeric_row_value(row, "max_drawdown_pct", 0.0)
    drawdown_abs = abs(max_drawdown)

    if trade_count == 0:
        return "완료된 거래가 없어 수익률보다 신호 발생 여부와 준비 데이터 상태를 먼저 확인해야 합니다."

    messages: list[str] = []
    if total_return > 0:
        if trade_count < 3:
            messages.append("총수익률은 플러스지만 거래 수가 적어 아직 신뢰도는 낮게 봐야 합니다.")
        elif win_rate < 50 and average_return > 0:
            messages.append("승률은 낮지만 평균 수익이 손실을 만회해 총수익률은 플러스입니다.")
        else:
            messages.append("총수익률이 플러스라 과거 구간에서는 전략이 유효하게 작동했습니다.")
    elif total_return < 0:
        messages.append("총수익률이 마이너스라 이 구간에서는 전략을 그대로 쓰기 어렵습니다.")
    else:
        messages.append("총수익률이 거의 0에 가까워 수수료와 슬리피지를 고려하면 우위가 약합니다.")

    if drawdown_abs >= 15:
        messages.append("최대낙폭이 커서 실제 운용 시 변동성 부담을 반드시 확인해야 합니다.")
    elif drawdown_abs >= 8:
        messages.append("최대낙폭이 중간 수준이라 손실 구간을 버틸 수 있는지 함께 봐야 합니다.")

    if trade_count < 5:
        messages.append("표본이 적으므로 더 긴 기간이나 다른 종목에서도 같은 결과가 나오는지 재검증이 필요합니다.")

    return " ".join(messages)


def _render_results_panel(service: DashboardDataService, result_bundle: dict[str, object]) -> None:
    summary_frame = result_bundle.get("summary_frame")
    comparison_frame = result_bundle.get("comparison_frame")
    trade_frame = result_bundle.get("trade_frame")
    chart_frame = result_bundle.get("chart_frame")
    daily_equity_frame = result_bundle.get("daily_equity_frame")
    daily_equity_notice = result_bundle.get("daily_equity_notice")
    history_warnings = result_bundle.get("history_warnings")

    if isinstance(history_warnings, tuple):
        for message in history_warnings:
            st.warning(str(message))

    st.markdown("#### 전략 요약 카드")
    if isinstance(summary_frame, pd.DataFrame) and not summary_frame.empty:
        cards = []
        for _, row in summary_frame.head(6).iterrows():
            label = f"{row.get('symbol_name') or row.get('symbol')} · {row.get('strategy_name')}"
            interpretation = build_backtest_result_interpretation(row)
            cards.append(
                f"""
                <div class="backtest-result-card">
                  <strong>{escape(str(label))}</strong>
                  <div class="backtest-result-value">{escape(format_number(row.get('total_return_pct', 0.0)))}%</div>
                  <p>거래 {int(row.get('trade_count', 0))}건 · 승률 {escape(format_number(row.get('win_rate_pct', 0.0)))}% · 최대낙폭 {escape(format_number(row.get('max_drawdown_pct', 0.0)))}%</p>
                  <p class="backtest-result-interpretation">{escape(interpretation)}</p>
                </div>
                """,
            )
        st.markdown(f'<div class="backtest-result-grid">{"".join(cards)}</div>', unsafe_allow_html=True)
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

    st.markdown("#### 일별 평가금액")
    st.caption(
        f"가상 초기자금 {format_number(DEFAULT_MARK_TO_MARKET_INITIAL_EQUITY)}원 · "
        "신호 다음 거래일 종가 체결 · 수수료·세금·슬리피지 미반영"
    )
    if isinstance(daily_equity_frame, pd.DataFrame) and not daily_equity_frame.empty:
        start_date = pd.to_datetime(daily_equity_frame["date"], errors="coerce").min()
        end_date = pd.to_datetime(daily_equity_frame["date"], errors="coerce").max()
        if pd.notna(start_date) and pd.notna(end_date):
            st.caption(f"평가 기간: {start_date.date().isoformat()} ~ {end_date.date().isoformat()} · 종목·전략별 개별 평가")
        daily_equity_chart = (
            alt.Chart(daily_equity_frame)
            .mark_line()
            .encode(
                x=alt.X("date:T", title="거래일"),
                y=alt.Y("equity:Q", title="평가금액(원)"),
                color=alt.Color("series_label:N", title="전략"),
                tooltip=[
                    alt.Tooltip("date:T", title="거래일"),
                    alt.Tooltip("series_label:N", title="종목 · 전략"),
                    alt.Tooltip("equity:Q", title="평가금액(원)", format=",.0f"),
                    alt.Tooltip("equity_return_pct:Q", title="누적 수익률(%)", format=".2f"),
                    alt.Tooltip("position_state:N", title="상태"),
                ],
            )
            .properties(height=320)
        )
        st.altair_chart(daily_equity_chart, width="stretch")
    else:
        st.info(
            str(daily_equity_notice)
            if isinstance(daily_equity_notice, str) and daily_equity_notice
            else "평가할 일별 가격 데이터가 없어 일별 평가금액 차트를 아직 그릴 수 없습니다."
        )

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
