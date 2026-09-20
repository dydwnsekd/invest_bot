from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime

import pandas as pd

from invest_bot.dashboard.service import DashboardDataService


BACKTEST_HISTORY_SELECTION_KEY = "backtest_history_selection"
BACKTEST_HISTORY_NONE_OPTION = "__backtest_history_none__"
BACKTEST_HISTORY_SYMBOL_FILTER_KEY = "backtest_history_symbol_filter"
BACKTEST_HISTORY_STRATEGY_FILTER_KEY = "backtest_history_strategy_filter"


def render_backtest_history_panel(
    service: DashboardDataService,
    *,
    load_result: Callable[
        [DashboardDataService, dict[str, object]],
        tuple[dict[str, object] | None, tuple[str, ...]],
    ],
    st_api,
) -> dict[str, object] | None:
    with st_api.container(border=True):
        st_api.markdown("#### 저장된 실행 이력")
        st_api.caption("이력을 선택하면 저장된 요약과 거래 로그만 읽습니다. 선택만으로 백테스트를 다시 실행하지 않습니다.")
        entries, load_messages = load_backtest_history_entries(service)
        for message in load_messages:
            st_api.warning(message)
        if not entries:
            st_api.info("아직 불러올 저장된 백테스트 실행 이력이 없습니다.")
            return None

        filter_columns = st_api.columns(2, gap="small")
        symbol_options = sorted({str(entry["symbol"]) for entry in entries if entry.get("symbol")})
        strategy_options = sorted({str(entry["strategy_id"]) for entry in entries if entry.get("strategy_id")})
        sanitize_multiselect_state(
            st_api.session_state,
            BACKTEST_HISTORY_SYMBOL_FILTER_KEY,
            symbol_options,
            [],
        )
        sanitize_multiselect_state(
            st_api.session_state,
            BACKTEST_HISTORY_STRATEGY_FILTER_KEY,
            strategy_options,
            [],
        )
        selected_symbols = filter_columns[0].multiselect(
            "이력 종목 필터",
            options=symbol_options,
            key=BACKTEST_HISTORY_SYMBOL_FILTER_KEY,
        )
        selected_strategies = filter_columns[1].multiselect(
            "이력 전략 필터",
            options=strategy_options,
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
        filtered_entries = filter_backtest_history_entries(entries, selected_symbols, selected_strategies)
        if not filtered_entries:
            st_api.info("선택한 종목·전략 조건과 일치하는 저장 이력이 없습니다. 필터를 조정해 주세요.")
            return None

        st_api.dataframe(build_backtest_history_table(filtered_entries), width="stretch", hide_index=True)
        entries_by_id = {str(entry["entry_id"]): entry for entry in filtered_entries}
        options = [BACKTEST_HISTORY_NONE_OPTION, *entries_by_id]
        if st_api.session_state.get(BACKTEST_HISTORY_SELECTION_KEY) not in options:
            st_api.session_state[BACKTEST_HISTORY_SELECTION_KEY] = BACKTEST_HISTORY_NONE_OPTION
        selected_entry_id = st_api.selectbox(
            "확인할 저장 이력",
            options=options,
            format_func=lambda entry_id: (
                "저장된 실행 이력을 선택하세요"
                if entry_id == BACKTEST_HISTORY_NONE_OPTION
                else format_backtest_history_option(entries_by_id[entry_id])
            ),
            key=BACKTEST_HISTORY_SELECTION_KEY,
        )
        if selected_entry_id == BACKTEST_HISTORY_NONE_OPTION:
            return None

        selected_entry = entries_by_id.get(str(selected_entry_id))
        if selected_entry is None:
            st_api.warning("선택한 실행 이력을 찾을 수 없습니다. 목록을 다시 선택해 주세요.")
            return None
        result_bundle, result_messages = load_result(service, selected_entry)
        for message in result_messages:
            st_api.warning(message)
        if result_bundle is None:
            st_api.warning("선택한 실행 이력의 요약 결과를 읽을 수 없습니다.")
            return None
        st_api.caption(
            f"저장된 실행 시각: {format_history_timestamp(selected_entry.get('run_at'))} · "
            f"데이터 원본: {selected_entry.get('source_label') or '기록 없음'}"
        )
        return result_bundle


def sanitize_multiselect_state(
    session_state,
    key: str,
    options: list[str],
    fallback: list[str],
) -> None:
    if key not in session_state:
        return
    current = session_state.get(key)
    if not isinstance(current, (list, tuple)):
        session_state[key] = list(fallback)
        return
    normalized: list[str] = []
    for value in current:
        if isinstance(value, str) and value in options and value not in normalized:
            normalized.append(value)
    if normalized != list(current):
        session_state[key] = normalized or list(fallback)


def load_backtest_history_entries(
    service: DashboardDataService,
) -> tuple[list[dict[str, object]], tuple[str, ...]]:
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
            run_id = history_text(row, "run_id")
            symbol = history_text(row, "symbol") or str(getattr(preview, "symbol", "")).strip()
            strategy_id = history_text(row, "strategy_id")
            strategy_name = history_text(row, "strategy_name") or strategy_id or "전략 정보 없음"
            symbol_name = history_text(row, "symbol_name") or str(getattr(preview, "symbol_name", "")).strip()
            source_label = history_text(row, "signal_source_filename") or history_text(row, "price_source_filename")
            run_at = parse_history_run_timestamp(run_id) or getattr(preview, "created_at", None)
            entries.append(
                {
                    "entry_id": f"{preview.path.name}:{row_index}:{run_id or 'legacy'}",
                    "preview": preview,
                    "summary_frame": pd.DataFrame([row.to_dict()]),
                    "run_id": run_id,
                    "run_group_id": history_text(row, "run_group_id"),
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


def filter_backtest_history_entries(
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


def build_backtest_history_table(entries: list[dict[str, object]]) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "실행 시각": format_history_timestamp(entry.get("run_at")),
                "종목": f"{entry.get('symbol_name') or entry.get('symbol') or '정보 없음'} ({entry.get('symbol') or '-'})",
                "전략": entry.get("strategy_name") or entry.get("strategy_id") or "정보 없음",
                "데이터 원본": entry.get("source_label") or "기록 없음",
            }
            for entry in entries
        ]
    )


def format_backtest_history_option(entry: dict[str, object]) -> str:
    symbol = entry.get("symbol_name") or entry.get("symbol") or "정보 없음"
    strategy = entry.get("strategy_name") or entry.get("strategy_id") or "전략 정보 없음"
    return f"{format_history_timestamp(entry.get('run_at'))} · {symbol} · {strategy}"


def format_history_timestamp(value: object) -> str:
    if isinstance(value, datetime):
        return value.astimezone(UTC).strftime("%Y-%m-%d %H:%M UTC")
    return "실행 시각 기록 없음"


def parse_history_run_timestamp(run_id: str) -> datetime | None:
    timestamp = run_id.rsplit("_", 1)[-1] if "_" in run_id else ""
    try:
        return datetime.strptime(timestamp, "%Y%m%dT%H%M%SZ").replace(tzinfo=UTC)
    except ValueError:
        return None


def history_text(row: pd.Series, column: str) -> str:
    value = row.get(column, "")
    return "" if pd.isna(value) else str(value).strip()
