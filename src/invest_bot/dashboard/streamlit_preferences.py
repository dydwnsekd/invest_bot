from __future__ import annotations

from collections.abc import Mapping, MutableMapping
from datetime import date, datetime
from typing import Any

import streamlit as st

from invest_bot.dashboard.streamlit_collection_period import collection_period_bounds
from invest_bot.dashboard.streamlit_data import DATASET_DISPLAY_ORDER


DASHBOARD_PREFERENCES_KEY = "dashboard_saved_preferences"
DASHBOARD_PREFERENCES_DRAFT_KEY = "dashboard_preference_draft"
DASHBOARD_PREFERENCES_VERSION = 1

_ACTION_SYMBOLS_KEY = "streamlit_selected_symbols"
_ACTION_SYMBOLS_WIDGET_KEY = "multi_symbol_picker"
_ACTION_COLLECTION_PERIOD_KEY = "action_collection_period"
_BACKTEST_SYMBOLS_KEY = "backtest_selected_symbols"
_BACKTEST_STRATEGIES_KEY = "backtest_selected_strategies"
_BACKTEST_COLLECTION_PERIOD_KEY = "backtest_prepare_collection_period"
_BACKTEST_HISTORY_SYMBOL_FILTER_KEY = "backtest_history_symbol_filter"
_BACKTEST_HISTORY_STRATEGY_FILTER_KEY = "backtest_history_strategy_filter"
_BACKTEST_PORTFOLIO_STRATEGY_KEY = "backtest_portfolio_strategy"
_REPORT_QUERY_KEY = "report_query"
_REPORT_OVERVIEW_KEY = "report_interpretation_overview_open"
_REPORT_FAVORITES_ONLY_KEY = "report_favorites_only"
_REPORT_SORT_KEY = "report_sort_option"
_WATCHLIST_QUERY_KEY = "watchlist_query"
_WATCHLIST_SORT_KEY = "watchlist_sort_option"
_INTERPRETATION_OPINION_FILTER_KEY = "interpretation_opinion_filter"
_INTERPRETATION_STRATEGY_FILTER_KEY = "interpretation_strategy_filter"
_INTERPRETATION_SORT_KEY = "interpretation_sort_option"
_DATA_SYMBOL_FILTER_KEY = "data_symbol_filter"
_DATA_COMPARISON_SYMBOLS_KEY = "data_comparison_symbols"
_DATA_COMPARISON_BASIS_KEY = "data_comparison_basis"

_STATIC_VIEW_STATE_KEYS = (
    _ACTION_SYMBOLS_KEY,
    _ACTION_SYMBOLS_WIDGET_KEY,
    _ACTION_COLLECTION_PERIOD_KEY,
    _BACKTEST_SYMBOLS_KEY,
    _BACKTEST_STRATEGIES_KEY,
    _BACKTEST_COLLECTION_PERIOD_KEY,
    _BACKTEST_HISTORY_SYMBOL_FILTER_KEY,
    _BACKTEST_HISTORY_STRATEGY_FILTER_KEY,
    _BACKTEST_PORTFOLIO_STRATEGY_KEY,
    _REPORT_QUERY_KEY,
    _REPORT_OVERVIEW_KEY,
    _REPORT_FAVORITES_ONLY_KEY,
    _REPORT_SORT_KEY,
    _WATCHLIST_QUERY_KEY,
    _WATCHLIST_SORT_KEY,
    _INTERPRETATION_OPINION_FILTER_KEY,
    _INTERPRETATION_STRATEGY_FILTER_KEY,
    _INTERPRETATION_SORT_KEY,
    _DATA_SYMBOL_FILTER_KEY,
    _DATA_COMPARISON_SYMBOLS_KEY,
    _DATA_COMPARISON_BASIS_KEY,
)

_REPORT_SORT_OPTIONS = frozenset({"최신순", "즐겨찾기 우선", "종목명순", "매수 관점 우선"})
_WATCHLIST_SORT_OPTIONS = _REPORT_SORT_OPTIONS
_INTERPRETATION_OPINION_OPTIONS = frozenset({"전체", "매수 관점", "관심 관찰", "관망", "매도 관점", "정보 부족"})
_INTERPRETATION_STRATEGY_OPTIONS = frozenset({"전체", "매수 관점", "관망", "매도 관점", "정보 부족"})
_INTERPRETATION_SORT_OPTIONS = frozenset({"최신순", "매수 관점 우선", "종목명순"})
_COMPARISON_BASIS_OPTIONS = frozenset({"indexed", "price"})
_CHART_TYPE_OPTIONS = frozenset({"close_ma", "candlestick", "volume", "rsi", "flow", "close_only"})
_TIMEFRAME_OPTIONS = frozenset({"daily", "weekly", "monthly"})
_RANGE_MODE_OPTIONS = frozenset({"preset", "custom"})
_RANGE_PRESET_OPTIONS = frozenset({"30d", "90d", "180d", "365d", "all"})
_CHART_FIELDS = ("chart_type", "timeframe", "range_mode", "range_preset", "range_dates")
_TAB_PREFERENCE_GROUPS = {
    "데이터 갱신": ("actions",),
    "투자 리포트": ("reports", "charts"),
    "관심종목": ("watchlist", "charts"),
    "백테스트": ("backtest",),
    "데이터 보기": ("data", "charts", "chart_visibility"),
}
_DATA_CHART_TABS = frozenset({"데이터 보기"})
_REPORT_CHART_TABS = frozenset({"투자 리포트", "관심종목"})
_DATASET_CHART_PREFIXES = tuple(f"{dataset_name}_" for dataset_name in DATASET_DISPLAY_ORDER)


def save_dashboard_preferences(session_state: MutableMapping[str, Any]) -> dict[str, object]:
    """Save a defensive, session-only snapshot of supported dashboard view settings."""

    snapshot = sync_dashboard_preference_draft(session_state)
    session_state[DASHBOARD_PREFERENCES_KEY] = snapshot
    return snapshot


def capture_dashboard_preferences(session_state: Mapping[str, object]) -> dict[str, object]:
    """Capture only display and selection settings, never execution output or messages."""

    raw_settings: dict[str, object] = {}

    actions: dict[str, object] = {}
    if _ACTION_SYMBOLS_WIDGET_KEY in session_state:
        actions["symbols"] = session_state[_ACTION_SYMBOLS_WIDGET_KEY]
    elif _ACTION_SYMBOLS_KEY in session_state:
        actions["symbols"] = session_state[_ACTION_SYMBOLS_KEY]
    _copy_if_present(session_state, _ACTION_COLLECTION_PERIOD_KEY, actions, "collection_period")
    _add_group(raw_settings, "actions", actions)

    reports: dict[str, object] = {}
    _copy_if_present(session_state, _REPORT_QUERY_KEY, reports, "query")
    _copy_if_present(session_state, _REPORT_OVERVIEW_KEY, reports, "show_interpretations")
    _copy_if_present(session_state, _REPORT_FAVORITES_ONLY_KEY, reports, "favorites_only")
    _copy_if_present(session_state, _REPORT_SORT_KEY, reports, "sort")
    _copy_if_present(session_state, _INTERPRETATION_OPINION_FILTER_KEY, reports, "interpretation_opinion_filter")
    _copy_if_present(session_state, _INTERPRETATION_STRATEGY_FILTER_KEY, reports, "interpretation_strategy_filter")
    _copy_if_present(session_state, _INTERPRETATION_SORT_KEY, reports, "interpretation_sort")
    _add_group(raw_settings, "reports", reports)

    watchlist: dict[str, object] = {}
    _copy_if_present(session_state, _WATCHLIST_QUERY_KEY, watchlist, "query")
    _copy_if_present(session_state, _WATCHLIST_SORT_KEY, watchlist, "sort")
    _add_group(raw_settings, "watchlist", watchlist)

    data: dict[str, object] = {}
    _copy_if_present(session_state, _DATA_SYMBOL_FILTER_KEY, data, "symbol_filter")
    _copy_if_present(session_state, _DATA_COMPARISON_SYMBOLS_KEY, data, "comparison_symbols")
    _copy_if_present(session_state, _DATA_COMPARISON_BASIS_KEY, data, "comparison_basis")
    _add_group(raw_settings, "data", data)

    backtest: dict[str, object] = {}
    _copy_if_present(session_state, _BACKTEST_SYMBOLS_KEY, backtest, "symbols")
    _copy_if_present(session_state, _BACKTEST_STRATEGIES_KEY, backtest, "strategies")
    _copy_if_present(session_state, _BACKTEST_COLLECTION_PERIOD_KEY, backtest, "collection_period")
    _copy_if_present(session_state, _BACKTEST_HISTORY_SYMBOL_FILTER_KEY, backtest, "history_symbol_filter")
    _copy_if_present(session_state, _BACKTEST_HISTORY_STRATEGY_FILTER_KEY, backtest, "history_strategy_filter")
    _copy_if_present(session_state, _BACKTEST_PORTFOLIO_STRATEGY_KEY, backtest, "portfolio_strategy")
    _add_group(raw_settings, "backtest", backtest)

    charts, chart_visibility = _capture_chart_preferences(session_state)
    _add_group(raw_settings, "charts", charts)
    _add_group(raw_settings, "chart_visibility", chart_visibility)

    normalized = normalize_dashboard_preferences(
        {"version": DASHBOARD_PREFERENCES_VERSION, "settings": raw_settings}
    )
    # The payload above is built from known keys, so this is a defensive fallback only.
    return normalized or {"version": DASHBOARD_PREFERENCES_VERSION, "settings": {}}


def load_dashboard_preferences(session_state: Mapping[str, object]) -> dict[str, object] | None:
    return normalize_dashboard_preferences(session_state.get(DASHBOARD_PREFERENCES_KEY))


def sync_dashboard_preference_draft(session_state: MutableMapping[str, Any]) -> dict[str, object]:
    """Keep a non-widget draft so settings survive tab changes in one Streamlit session."""

    current = capture_dashboard_preferences(session_state)
    previous = normalize_dashboard_preferences(session_state.get(DASHBOARD_PREFERENCES_DRAFT_KEY))
    snapshot = _merge_dashboard_preference_snapshots(previous, current)
    session_state[DASHBOARD_PREFERENCES_DRAFT_KEY] = snapshot
    return snapshot


def restore_dashboard_preference_draft(
    session_state: MutableMapping[str, Any],
    *,
    tab_name: str | None = None,
) -> bool:
    """Hydrate missing active-tab widget state from the current-session draft.

    Streamlit removes widgets that are not rendered during a tab change.  Unlike an
    explicit saved-settings apply, this only fills keys that are now absent, so a
    live value from the currently open tab is never overwritten.
    """

    snapshot = normalize_dashboard_preferences(session_state.get(DASHBOARD_PREFERENCES_DRAFT_KEY))
    if snapshot is None:
        return False

    settings = snapshot["settings"]
    assert isinstance(settings, Mapping)
    groups = tuple(settings) if tab_name is None else _TAB_PREFERENCE_GROUPS.get(tab_name, ())

    if "actions" in groups:
        _apply_actions(session_state, settings.get("actions"), only_missing=True)
    if "reports" in groups:
        _apply_reports(session_state, settings.get("reports"), only_missing=True)
    if "watchlist" in groups:
        _apply_watchlist(session_state, settings.get("watchlist"), only_missing=True)
    if "data" in groups:
        _apply_data(session_state, settings.get("data"), only_missing=True)
    if "backtest" in groups:
        _apply_backtest(session_state, settings.get("backtest"), only_missing=True)
    if "charts" in groups:
        _apply_charts(session_state, settings.get("charts"), only_missing=True, tab_name=tab_name)
    if "chart_visibility" in groups:
        _apply_chart_visibility(
            session_state,
            settings.get("chart_visibility"),
            only_missing=True,
            tab_name=tab_name,
        )
    return True


def normalize_dashboard_preferences(payload: object) -> dict[str, object] | None:
    """Return a schema-safe snapshot or ``None`` when it cannot be read safely."""

    if not isinstance(payload, Mapping):
        return None
    version = payload.get("version")
    if isinstance(version, bool) or version != DASHBOARD_PREFERENCES_VERSION:
        return None
    raw_settings = payload.get("settings")
    if not isinstance(raw_settings, Mapping):
        return None

    settings: dict[str, object] = {}
    _add_group(settings, "actions", _normalize_actions(raw_settings.get("actions")))
    _add_group(settings, "reports", _normalize_reports(raw_settings.get("reports")))
    _add_group(settings, "watchlist", _normalize_watchlist(raw_settings.get("watchlist")))
    _add_group(settings, "data", _normalize_data(raw_settings.get("data")))
    _add_group(settings, "backtest", _normalize_backtest(raw_settings.get("backtest")))
    _add_group(settings, "charts", _normalize_charts(raw_settings.get("charts")))
    _add_group(settings, "chart_visibility", _normalize_chart_visibility(raw_settings.get("chart_visibility")))
    return {"version": DASHBOARD_PREFERENCES_VERSION, "settings": settings}


def apply_dashboard_preferences(session_state: MutableMapping[str, Any]) -> bool:
    """Restore a saved snapshot before dashboard widgets render in the current run."""

    snapshot = load_dashboard_preferences(session_state)
    if snapshot is None:
        session_state.pop(DASHBOARD_PREFERENCES_KEY, None)
        return False

    _clear_supported_view_state(session_state)
    settings = snapshot["settings"]
    assert isinstance(settings, Mapping)

    _apply_actions(session_state, settings.get("actions"))
    _apply_reports(session_state, settings.get("reports"))
    _apply_watchlist(session_state, settings.get("watchlist"))
    _apply_data(session_state, settings.get("data"))
    _apply_backtest(session_state, settings.get("backtest"))
    _apply_charts(session_state, settings.get("charts"))
    _apply_chart_visibility(session_state, settings.get("chart_visibility"))

    # Keep the normalized form so a partially corrupt old payload cannot be applied again.
    session_state[DASHBOARD_PREFERENCES_KEY] = snapshot
    session_state[DASHBOARD_PREFERENCES_DRAFT_KEY] = snapshot
    return True


def reset_dashboard_preferences(session_state: MutableMapping[str, Any]) -> None:
    """Remove a snapshot and its supported widget state without touching execution results."""

    _clear_supported_view_state(session_state)
    session_state.pop(DASHBOARD_PREFERENCES_KEY, None)
    session_state.pop(DASHBOARD_PREFERENCES_DRAFT_KEY, None)


def count_dashboard_preference_values(snapshot: Mapping[str, object]) -> int:
    settings = snapshot.get("settings")
    if not isinstance(settings, Mapping):
        return 0
    total = 0
    for group_name, group in settings.items():
        if not isinstance(group, Mapping):
            continue
        if group_name == "charts":
            total += sum(len(value) for value in group.values() if isinstance(value, Mapping))
        else:
            total += len(group)
    return total


def render_dashboard_preferences_panel() -> None:
    """Render the sidebar controls for an in-session dashboard settings snapshot."""

    session_state = st.session_state
    stored_raw = session_state.get(DASHBOARD_PREFERENCES_KEY)
    snapshot = load_dashboard_preferences(session_state)
    unreadable_snapshot = stored_raw is not None and snapshot is None
    if unreadable_snapshot:
        session_state.pop(DASHBOARD_PREFERENCES_KEY, None)

    with st.container(border=True):
        st.markdown("#### 화면 설정")
        st.caption("종목 선택, 기간, 검색·정렬·필터, 차트 표시 기준을 현재 화면용 복원 지점으로 저장합니다.")
        st.caption("탭을 이동하는 동안 현재 선택값은 자동으로 유지됩니다.")
        st.caption("저장한 설정은 현재 브라우저 세션에만 보관되며, 서버 파일·DB·다른 사용자에게 저장하지 않습니다.")
        st.caption("새 브라우저 세션이나 서버 재시작 뒤에는 기본 설정으로 돌아갑니다.")

        if unreadable_snapshot:
            st.warning("저장한 화면 설정을 읽을 수 없어 삭제했습니다. 현재 화면은 기본 동작으로 계속 사용할 수 있습니다.")
        elif snapshot is None:
            st.caption("저장한 화면 설정이 아직 없습니다.")
        else:
            count = count_dashboard_preference_values(snapshot)
            st.caption(f"저장한 항목 {count}개 · 적용 버튼을 눌렀을 때만 현재 화면에 다시 반영합니다.")

        st.caption("백테스트 결과와 실험 파라미터·조합 가중치는 저장하거나 변경하지 않습니다.")
        save_clicked = st.button("현재 설정 저장", key="dashboard_preferences_save", width="stretch")
        apply_clicked = st.button(
            "저장한 설정 적용",
            key="dashboard_preferences_apply",
            width="stretch",
            disabled=snapshot is None,
        )
        reset_clicked = st.button(
            "설정 초기화",
            key="dashboard_preferences_reset",
            width="stretch",
            disabled=snapshot is None,
        )

        if save_clicked:
            saved = save_dashboard_preferences(session_state)
            _set_preferences_feedback(f"현재 화면 설정 {count_dashboard_preference_values(saved)}개를 이 브라우저 세션에 저장했습니다.")
            st.rerun()
        elif apply_clicked:
            if apply_dashboard_preferences(session_state):
                _set_preferences_feedback("저장한 화면 설정을 적용했습니다. 지원하지 않는 값은 기본 설정으로 되돌렸습니다.")
            else:
                _set_preferences_feedback("저장한 화면 설정을 읽을 수 없어 기본 설정으로 계속 표시합니다.", "warning")
            st.rerun()
        elif reset_clicked:
            reset_dashboard_preferences(session_state)
            _set_preferences_feedback("저장한 화면 설정과 현재 세션의 지원되는 보기 설정을 초기화했습니다.")
            st.rerun()


def _set_preferences_feedback(message: str, message_type: str = "success") -> None:
    st.session_state["action_message"] = message
    st.session_state["action_message_type"] = message_type


def _copy_if_present(source: Mapping[str, object], source_key: str, target: dict[str, object], target_key: str) -> None:
    if source_key in source:
        target[target_key] = source[source_key]


def _add_group(target: dict[str, object], name: str, values: Mapping[str, object]) -> None:
    if values:
        target[name] = dict(values)


def _capture_chart_preferences(session_state: Mapping[str, object]) -> tuple[dict[str, object], dict[str, object]]:
    charts: dict[str, dict[str, object]] = {}
    chart_visibility: dict[str, object] = {}
    for raw_key, value in session_state.items():
        if not isinstance(raw_key, str):
            continue
        chart_key = _split_chart_state_key(raw_key)
        if chart_key is not None:
            prefix, field = chart_key
            charts.setdefault(prefix, {})[field] = value
        elif _is_managed_chart_visibility_key(raw_key):
            chart_visibility[raw_key] = value
    return charts, chart_visibility


def _split_chart_state_key(key: str) -> tuple[str, str] | None:
    for field in _CHART_FIELDS:
        suffix = f"_{field}"
        if key.endswith(suffix):
            prefix = key[: -len(suffix)]
            if _chart_owner_tabs(prefix):
                return (prefix, field)
    return None


def _is_safe_chart_prefix(value: object) -> bool:
    return isinstance(value, str) and bool(value) and len(value) <= 256 and all(character.isprintable() for character in value)


def _chart_owner_tabs(prefix: object) -> frozenset[str]:
    """Return the dashboard tabs that actually construct a known chart prefix."""

    if not _is_safe_chart_prefix(prefix):
        return frozenset()
    if prefix == "data_comparison" or any(prefix.startswith(candidate) for candidate in _DATASET_CHART_PREFIXES):
        return _DATA_CHART_TABS
    if _is_report_chart_prefix(prefix):
        return _REPORT_CHART_TABS
    return frozenset()


def _is_report_chart_prefix(prefix: str) -> bool:
    if not prefix.startswith("report_"):
        return False
    symbol, separator, _source_name = prefix.removeprefix("report_").partition("_")
    return bool(separator and symbol.isdigit())


def _is_managed_chart_visibility_key(key: object) -> bool:
    if not isinstance(key, str) or not key.startswith("toggle_chart_"):
        return False
    prefix = key.removeprefix("toggle_chart_")
    return bool(_chart_owner_tabs(prefix) & _DATA_CHART_TABS)


def _merge_dashboard_preference_snapshots(
    previous: Mapping[str, object] | None,
    current: Mapping[str, object],
) -> dict[str, object]:
    previous_settings = previous.get("settings") if isinstance(previous, Mapping) else None
    current_settings = current.get("settings")
    merged_settings: dict[str, object] = {}

    if isinstance(previous_settings, Mapping):
        for group_name, values in previous_settings.items():
            if isinstance(values, Mapping):
                merged_settings[str(group_name)] = _copy_preference_group(values)

    if isinstance(current_settings, Mapping):
        for group_name, values in current_settings.items():
            if not isinstance(values, Mapping):
                continue
            existing = merged_settings.get(str(group_name))
            merged_settings[str(group_name)] = _merge_preference_group(existing, values)

    normalized = normalize_dashboard_preferences(
        {"version": DASHBOARD_PREFERENCES_VERSION, "settings": merged_settings}
    )
    return normalized or {"version": DASHBOARD_PREFERENCES_VERSION, "settings": {}}


def _copy_preference_group(values: Mapping[object, object]) -> dict[str, object]:
    return {
        str(key): _copy_preference_group(value) if isinstance(value, Mapping) else list(value) if isinstance(value, list) else value
        for key, value in values.items()
    }


def _merge_preference_group(existing: object, incoming: Mapping[object, object]) -> dict[str, object]:
    merged = _copy_preference_group(existing) if isinstance(existing, Mapping) else {}
    for key, value in incoming.items():
        normalized_key = str(key)
        if isinstance(value, Mapping):
            merged[normalized_key] = _merge_preference_group(merged.get(normalized_key), value)
        else:
            merged[normalized_key] = list(value) if isinstance(value, list) else value
    return merged


def _normalize_actions(raw: object) -> dict[str, object]:
    if not isinstance(raw, Mapping):
        return {}
    result: dict[str, object] = {}
    _copy_normalized_string_list(raw, "symbols", result)
    _copy_normalized_period(raw, "collection_period", result)
    return result


def _normalize_reports(raw: object) -> dict[str, object]:
    if not isinstance(raw, Mapping):
        return {}
    result: dict[str, object] = {}
    _copy_normalized_text(raw, "query", result)
    _copy_normalized_bool(raw, "show_interpretations", result)
    _copy_normalized_bool(raw, "favorites_only", result)
    _copy_normalized_choice(raw, "sort", result, _REPORT_SORT_OPTIONS)
    _copy_normalized_choice(raw, "interpretation_opinion_filter", result, _INTERPRETATION_OPINION_OPTIONS)
    _copy_normalized_choice(raw, "interpretation_strategy_filter", result, _INTERPRETATION_STRATEGY_OPTIONS)
    _copy_normalized_choice(raw, "interpretation_sort", result, _INTERPRETATION_SORT_OPTIONS)
    return result


def _normalize_watchlist(raw: object) -> dict[str, object]:
    if not isinstance(raw, Mapping):
        return {}
    result: dict[str, object] = {}
    _copy_normalized_text(raw, "query", result)
    _copy_normalized_choice(raw, "sort", result, _WATCHLIST_SORT_OPTIONS)
    return result


def _normalize_data(raw: object) -> dict[str, object]:
    if not isinstance(raw, Mapping):
        return {}
    result: dict[str, object] = {}
    _copy_normalized_text(raw, "symbol_filter", result)
    _copy_normalized_string_list(raw, "comparison_symbols", result, max_items=3)
    _copy_normalized_choice(raw, "comparison_basis", result, _COMPARISON_BASIS_OPTIONS)
    return result


def _normalize_backtest(raw: object) -> dict[str, object]:
    if not isinstance(raw, Mapping):
        return {}
    result: dict[str, object] = {}
    _copy_normalized_string_list(raw, "symbols", result)
    _copy_normalized_string_list(raw, "strategies", result)
    _copy_normalized_period(raw, "collection_period", result)
    _copy_normalized_string_list(raw, "history_symbol_filter", result)
    _copy_normalized_string_list(raw, "history_strategy_filter", result)
    _copy_normalized_text(raw, "portfolio_strategy", result)
    return result


def _normalize_charts(raw: object) -> dict[str, object]:
    if not isinstance(raw, Mapping):
        return {}
    normalized: dict[str, object] = {}
    for prefix, raw_values in raw.items():
        if not _chart_owner_tabs(prefix) or not isinstance(raw_values, Mapping):
            continue
        values: dict[str, object] = {}
        _copy_normalized_choice(raw_values, "chart_type", values, _CHART_TYPE_OPTIONS)
        _copy_normalized_choice(raw_values, "timeframe", values, _TIMEFRAME_OPTIONS)
        _copy_normalized_choice(raw_values, "range_mode", values, _RANGE_MODE_OPTIONS)
        _copy_normalized_choice(raw_values, "range_preset", values, _RANGE_PRESET_OPTIONS)
        _copy_normalized_period(raw_values, "range_dates", values)
        _add_group(normalized, prefix, values)
    return normalized


def _normalize_chart_visibility(raw: object) -> dict[str, object]:
    if not isinstance(raw, Mapping):
        return {}
    return {
        key: value
        for key, value in raw.items()
        if _is_managed_chart_visibility_key(key) and isinstance(value, bool)
    }


def _copy_normalized_text(source: Mapping[str, object], key: str, target: dict[str, object]) -> None:
    if key not in source or not isinstance(source[key], str):
        return
    target[key] = source[key].strip()[:200]


def _copy_normalized_bool(source: Mapping[str, object], key: str, target: dict[str, object]) -> None:
    if key in source and isinstance(source[key], bool):
        target[key] = source[key]


def _copy_normalized_choice(
    source: Mapping[str, object],
    key: str,
    target: dict[str, object],
    options: frozenset[str],
) -> None:
    value = source.get(key)
    if isinstance(value, str) and value in options:
        target[key] = value


def _copy_normalized_string_list(
    source: Mapping[str, object],
    key: str,
    target: dict[str, object],
    *,
    max_items: int = 50,
) -> None:
    if key not in source:
        return
    normalized = _normalize_string_list(source[key], max_items=max_items)
    if normalized is not None:
        target[key] = normalized


def _normalize_string_list(value: object, *, max_items: int) -> list[str] | None:
    if not isinstance(value, (list, tuple)):
        return None
    values: list[str] = []
    for item in value:
        if not isinstance(item, str):
            continue
        normalized = item.strip()
        if normalized and normalized not in values:
            values.append(normalized[:100])
        if len(values) >= max_items:
            break
    return values


def _copy_normalized_period(source: Mapping[str, object], key: str, target: dict[str, object]) -> None:
    if key not in source:
        return
    normalized = _normalize_date_pair(source[key])
    if normalized is not None:
        target[key] = normalized


def _normalize_date_pair(value: object) -> list[str] | None:
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        return None
    start_date = _coerce_date(value[0])
    end_date = _coerce_date(value[1])
    if start_date is None or end_date is None:
        return None
    if start_date > end_date:
        start_date, end_date = end_date, start_date
    return [start_date.isoformat(), end_date.isoformat()]


def _coerce_date(value: object) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            return date.fromisoformat(value)
        except ValueError:
            return None
    return None


def _clear_supported_view_state(session_state: MutableMapping[str, Any]) -> None:
    for key in _STATIC_VIEW_STATE_KEYS:
        session_state.pop(key, None)
    chart_prefixes, visibility_keys = _managed_chart_state_keys(session_state)
    for prefix in chart_prefixes:
        for field in _CHART_FIELDS:
            session_state.pop(f"{prefix}_{field}", None)
        _clear_chart_widget_mirrors(session_state, prefix)
    for key in visibility_keys:
        session_state.pop(key, None)


def _managed_chart_state_keys(session_state: Mapping[str, object]) -> tuple[set[str], set[str]]:
    snapshots = [capture_dashboard_preferences(session_state)]
    for state_key in (DASHBOARD_PREFERENCES_DRAFT_KEY, DASHBOARD_PREFERENCES_KEY):
        snapshot = normalize_dashboard_preferences(session_state.get(state_key))
        if snapshot is not None:
            snapshots.append(snapshot)

    prefixes: set[str] = set()
    visibility_keys: set[str] = set()
    for snapshot in snapshots:
        settings = snapshot.get("settings")
        if not isinstance(settings, Mapping):
            continue
        charts = settings.get("charts")
        if isinstance(charts, Mapping):
            prefixes.update(prefix for prefix in charts if _chart_owner_tabs(prefix))
        visibility = settings.get("chart_visibility")
        if isinstance(visibility, Mapping):
            visibility_keys.update(
                key for key in visibility if _is_managed_chart_visibility_key(key)
            )
    return prefixes, visibility_keys


def _clear_chart_widget_mirrors(session_state: MutableMapping[str, Any], prefix: str) -> None:
    mirror_prefixes = (
        f"{prefix}_range_mode_widget",
        f"{prefix}_range_preset_widget",
        f"{prefix}_range_dates_widget",
    )
    for raw_key in list(session_state):
        if isinstance(raw_key, str) and raw_key.startswith(mirror_prefixes):
            session_state.pop(raw_key, None)


def _apply_actions(
    session_state: MutableMapping[str, Any],
    raw: object,
    *,
    only_missing: bool = False,
) -> None:
    if not isinstance(raw, Mapping):
        return
    symbols = raw.get("symbols")
    if isinstance(symbols, list):
        _apply_action_symbols(session_state, symbols, only_missing=only_missing)
    _apply_collection_period(
        session_state,
        _ACTION_COLLECTION_PERIOD_KEY,
        raw.get("collection_period"),
        only_missing=only_missing,
    )


def _apply_action_symbols(
    session_state: MutableMapping[str, Any],
    saved_symbols: list[object],
    *,
    only_missing: bool,
) -> None:
    """Keep the action widget and its legacy mirror aligned during draft recovery."""

    symbols = _current_action_symbols(session_state) if only_missing else None
    resolved_symbols = symbols if symbols is not None else list(saved_symbols)
    _apply_value(session_state, _ACTION_SYMBOLS_KEY, resolved_symbols, only_missing=only_missing)
    _apply_value(session_state, _ACTION_SYMBOLS_WIDGET_KEY, resolved_symbols, only_missing=only_missing)


def _current_action_symbols(session_state: Mapping[str, object]) -> list[object] | None:
    for key in (_ACTION_SYMBOLS_WIDGET_KEY, _ACTION_SYMBOLS_KEY):
        value = session_state.get(key)
        if isinstance(value, (list, tuple)):
            return list(value)
    return None


def _apply_reports(
    session_state: MutableMapping[str, Any],
    raw: object,
    *,
    only_missing: bool = False,
) -> None:
    if not isinstance(raw, Mapping):
        return
    _apply_if_present(session_state, _REPORT_QUERY_KEY, raw, "query", only_missing=only_missing)
    _apply_if_present(session_state, _REPORT_OVERVIEW_KEY, raw, "show_interpretations", only_missing=only_missing)
    _apply_if_present(session_state, _REPORT_FAVORITES_ONLY_KEY, raw, "favorites_only", only_missing=only_missing)
    _apply_if_present(session_state, _REPORT_SORT_KEY, raw, "sort", only_missing=only_missing)
    _apply_if_present(
        session_state,
        _INTERPRETATION_OPINION_FILTER_KEY,
        raw,
        "interpretation_opinion_filter",
        only_missing=only_missing,
    )
    _apply_if_present(
        session_state,
        _INTERPRETATION_STRATEGY_FILTER_KEY,
        raw,
        "interpretation_strategy_filter",
        only_missing=only_missing,
    )
    _apply_if_present(session_state, _INTERPRETATION_SORT_KEY, raw, "interpretation_sort", only_missing=only_missing)


def _apply_watchlist(
    session_state: MutableMapping[str, Any],
    raw: object,
    *,
    only_missing: bool = False,
) -> None:
    if not isinstance(raw, Mapping):
        return
    _apply_if_present(session_state, _WATCHLIST_QUERY_KEY, raw, "query", only_missing=only_missing)
    _apply_if_present(session_state, _WATCHLIST_SORT_KEY, raw, "sort", only_missing=only_missing)


def _apply_data(
    session_state: MutableMapping[str, Any],
    raw: object,
    *,
    only_missing: bool = False,
) -> None:
    if not isinstance(raw, Mapping):
        return
    _apply_if_present(session_state, _DATA_SYMBOL_FILTER_KEY, raw, "symbol_filter", only_missing=only_missing)
    _apply_if_present(
        session_state,
        _DATA_COMPARISON_SYMBOLS_KEY,
        raw,
        "comparison_symbols",
        only_missing=only_missing,
    )
    _apply_if_present(session_state, _DATA_COMPARISON_BASIS_KEY, raw, "comparison_basis", only_missing=only_missing)


def _apply_backtest(
    session_state: MutableMapping[str, Any],
    raw: object,
    *,
    only_missing: bool = False,
) -> None:
    if not isinstance(raw, Mapping):
        return
    _apply_if_present(session_state, _BACKTEST_SYMBOLS_KEY, raw, "symbols", only_missing=only_missing)
    _apply_if_present(session_state, _BACKTEST_STRATEGIES_KEY, raw, "strategies", only_missing=only_missing)
    _apply_collection_period(
        session_state,
        _BACKTEST_COLLECTION_PERIOD_KEY,
        raw.get("collection_period"),
        only_missing=only_missing,
    )
    _apply_if_present(
        session_state,
        _BACKTEST_HISTORY_SYMBOL_FILTER_KEY,
        raw,
        "history_symbol_filter",
        only_missing=only_missing,
    )
    _apply_if_present(
        session_state,
        _BACKTEST_HISTORY_STRATEGY_FILTER_KEY,
        raw,
        "history_strategy_filter",
        only_missing=only_missing,
    )
    _apply_if_present(
        session_state,
        _BACKTEST_PORTFOLIO_STRATEGY_KEY,
        raw,
        "portfolio_strategy",
        only_missing=only_missing,
    )


def _apply_charts(
    session_state: MutableMapping[str, Any],
    raw: object,
    *,
    only_missing: bool = False,
    tab_name: str | None = None,
) -> None:
    if not isinstance(raw, Mapping):
        return
    for prefix, values in raw.items():
        if not isinstance(prefix, str) or not isinstance(values, Mapping):
            continue
        if tab_name is not None and tab_name not in _chart_owner_tabs(prefix):
            continue
        for field in ("chart_type", "timeframe", "range_mode", "range_preset"):
            if field in values:
                _apply_value(session_state, f"{prefix}_{field}", values[field], only_missing=only_missing)
        _apply_period(
            session_state,
            f"{prefix}_range_dates",
            values.get("range_dates"),
            only_missing=only_missing,
        )


def _apply_chart_visibility(
    session_state: MutableMapping[str, Any],
    raw: object,
    *,
    only_missing: bool = False,
    tab_name: str | None = None,
) -> None:
    if not isinstance(raw, Mapping):
        return
    for key, value in raw.items():
        if not _is_managed_chart_visibility_key(key) or not isinstance(value, bool):
            continue
        if tab_name is not None and tab_name not in _DATA_CHART_TABS:
            continue
        _apply_value(session_state, key, value, only_missing=only_missing)


def _apply_if_present(
    session_state: MutableMapping[str, Any],
    session_key: str,
    source: Mapping[str, object],
    source_key: str,
    *,
    only_missing: bool = False,
) -> None:
    if source_key not in source:
        return
    _apply_value(session_state, session_key, source[source_key], only_missing=only_missing)


def _apply_value(
    session_state: MutableMapping[str, Any],
    session_key: str,
    value: object,
    *,
    only_missing: bool,
) -> None:
    if only_missing and session_key in session_state:
        return
    session_state[session_key] = list(value) if isinstance(value, list) else value


def _apply_period(
    session_state: MutableMapping[str, Any],
    session_key: str,
    value: object,
    *,
    only_missing: bool = False,
) -> None:
    normalized = _normalize_date_pair(value)
    if normalized is None:
        return
    _apply_value(
        session_state,
        session_key,
        (date.fromisoformat(normalized[0]), date.fromisoformat(normalized[1])),
        only_missing=only_missing,
    )


def _apply_collection_period(
    session_state: MutableMapping[str, Any],
    session_key: str,
    value: object,
    *,
    only_missing: bool = False,
) -> None:
    normalized = _normalize_date_pair(value)
    if normalized is None:
        return
    minimum_date, maximum_date = collection_period_bounds()
    start_date = min(max(date.fromisoformat(normalized[0]), minimum_date), maximum_date)
    end_date = min(max(date.fromisoformat(normalized[1]), minimum_date), maximum_date)
    if start_date > end_date:
        start_date, end_date = end_date, start_date
    _apply_value(session_state, session_key, (start_date, end_date), only_missing=only_missing)
