from __future__ import annotations

from datetime import date, timedelta

import invest_bot.dashboard.streamlit_actions as actions_module
import invest_bot.dashboard.streamlit_backtest as backtest_module
import invest_bot.dashboard.streamlit_data as data_module
import invest_bot.dashboard.streamlit_preferences as preferences_module
from streamlit.testing.v1 import AppTest
from invest_bot.dashboard.streamlit_preferences import (
    DASHBOARD_PREFERENCES_DRAFT_KEY,
    DASHBOARD_PREFERENCES_KEY,
    DASHBOARD_PREFERENCES_VERSION,
    apply_dashboard_preferences,
    capture_dashboard_preferences,
    normalize_dashboard_preferences,
    reset_dashboard_preferences,
    restore_dashboard_preference_draft,
    save_dashboard_preferences,
    sync_dashboard_preference_draft,
)
from invest_bot.dashboard.streamlit_collection_period import collection_period_bounds


def _view_state() -> dict[str, object]:
    return {
        "streamlit_selected_symbols": ["005930", "000660"],
        "multi_symbol_picker": ["005930", "000660"],
        "action_collection_period": (date(2026, 1, 1), date(2026, 3, 31)),
        "report_query": "삼성전자",
        "report_interpretation_overview_open": True,
        "report_favorites_only": True,
        "report_sort_option": "매수 관점 우선",
        "interpretation_opinion_filter": "매수 관점",
        "interpretation_strategy_filter": "관망",
        "interpretation_sort_option": "종목명순",
        "watchlist_query": "SK",
        "watchlist_sort_option": "최신순",
        "data_symbol_filter": "005930",
        "data_comparison_symbols": ["005930", "000660"],
        "data_comparison_basis": "price",
        "backtest_selected_symbols": ["005930", "000660"],
        "backtest_selected_strategies": ["golden-cross", "rsi"],
        "backtest_prepare_collection_period": (date(2025, 12, 1), date(2026, 3, 31)),
        "backtest_history_symbol_filter": ["005930"],
        "backtest_history_strategy_filter": ["golden-cross"],
        "backtest_portfolio_strategy": "golden-cross",
        "data_comparison_range_mode": "custom",
        "data_comparison_range_preset": "90d",
        "data_comparison_range_dates": (date(2026, 2, 1), date(2026, 3, 31)),
        "data_comparison_range_mode_widget": "custom",
        "data_comparison_range_dates_widget_2026-02-01_2026-03-31": (date(2026, 2, 1), date(2026, 3, 31)),
        "daily_prices_005930_prices_csv_timeframe": "weekly",
        "toggle_chart_daily_prices_005930_prices.csv": True,
    }


def _dashboard_preference_navigation_test_app() -> None:
    import streamlit as st

    from invest_bot.dashboard.streamlit_preferences import (
        restore_dashboard_preference_draft,
        sync_dashboard_preference_draft,
    )

    if "selected_tab" not in st.session_state:
        st.session_state.selected_tab = "투자 리포트"
    sync_dashboard_preference_draft(st.session_state)

    if st.button("데이터 보기로 이동"):
        st.session_state.selected_tab = "데이터 보기"
        st.rerun()
    if st.button("투자 리포트로 이동"):
        st.session_state.selected_tab = "투자 리포트"
        st.rerun()

    selected_tab = st.session_state.selected_tab
    restore_dashboard_preference_draft(st.session_state, tab_name=selected_tab)
    if selected_tab == "투자 리포트":
        st.text_input("리포트 검색", key="report_query")
    else:
        st.text_input("데이터 보기 검색", key="data_symbol_filter")


def test_capture_dashboard_preferences_keeps_only_supported_view_settings() -> None:
    execution_result = object()
    state = _view_state() | {
        "selected_tab": "백테스트",
        "action_message": "기존 메시지",
        "backtest_results": execution_result,
        "backtest_strategy_parameters": {"golden-cross": {"short_window": 5}},
    }

    snapshot = save_dashboard_preferences(state)

    assert snapshot["version"] == DASHBOARD_PREFERENCES_VERSION
    settings = snapshot["settings"]
    assert settings == {
        "actions": {
            "symbols": ["005930", "000660"],
            "collection_period": ["2026-01-01", "2026-03-31"],
        },
        "reports": {
            "query": "삼성전자",
            "show_interpretations": True,
            "favorites_only": True,
            "sort": "매수 관점 우선",
            "interpretation_opinion_filter": "매수 관점",
            "interpretation_strategy_filter": "관망",
            "interpretation_sort": "종목명순",
        },
        "watchlist": {"query": "SK", "sort": "최신순"},
        "data": {
            "symbol_filter": "005930",
            "comparison_symbols": ["005930", "000660"],
            "comparison_basis": "price",
        },
        "backtest": {
            "symbols": ["005930", "000660"],
            "strategies": ["golden-cross", "rsi"],
            "collection_period": ["2025-12-01", "2026-03-31"],
            "history_symbol_filter": ["005930"],
            "history_strategy_filter": ["golden-cross"],
            "portfolio_strategy": "golden-cross",
        },
        "charts": {
            "data_comparison": {
                "range_mode": "custom",
                "range_preset": "90d",
                "range_dates": ["2026-02-01", "2026-03-31"],
            },
            "daily_prices_005930_prices_csv": {"timeframe": "weekly"},
        },
        "chart_visibility": {"toggle_chart_daily_prices_005930_prices.csv": True},
    }
    assert state[DASHBOARD_PREFERENCES_KEY] == snapshot

    state["streamlit_selected_symbols"].append("035420")  # type: ignore[union-attr]
    assert settings["actions"]["symbols"] == ["005930", "000660"]  # type: ignore[index]
    assert "backtest_results" not in repr(snapshot)
    assert "backtest_strategy_parameters" not in repr(snapshot)


def test_capture_dashboard_preferences_uses_the_current_action_widget_value_before_its_mirror() -> None:
    snapshot = capture_dashboard_preferences(
        {
            "streamlit_selected_symbols": ["005930"],
            "multi_symbol_picker": ["000660"],
        }
    )

    assert snapshot["settings"] == {"actions": {"symbols": ["000660"]}}


def test_apply_dashboard_preferences_restores_supported_values_and_keeps_execution_result() -> None:
    execution_result = object()
    state = _view_state() | {"backtest_results": execution_result}
    save_dashboard_preferences(state)
    state.update(
        {
            "streamlit_selected_symbols": ["035420"],
            "multi_symbol_picker": ["035420"],
            "report_sort_option": "최신순",
            "data_comparison_basis": "indexed",
            "data_comparison_range_dates": (date(2026, 3, 1), date(2026, 3, 31)),
            "data_comparison_range_mode_widget": "preset",
            "toggle_chart_daily_prices_005930_prices.csv": False,
        }
    )

    assert apply_dashboard_preferences(state) is True

    assert state["streamlit_selected_symbols"] == ["005930", "000660"]
    assert state["multi_symbol_picker"] == ["005930", "000660"]
    assert state["action_collection_period"] == (date(2026, 1, 1), date(2026, 3, 31))
    assert state["report_sort_option"] == "매수 관점 우선"
    assert state["data_comparison_basis"] == "price"
    assert state["data_comparison_range_dates"] == (date(2026, 2, 1), date(2026, 3, 31))
    assert "data_comparison_range_mode_widget" not in state
    assert state["toggle_chart_daily_prices_005930_prices.csv"] is True
    assert state["backtest_results"] is execution_result


def test_reset_dashboard_preferences_clears_supported_view_state_only() -> None:
    execution_result = object()
    state = _view_state() | {
        "backtest_results": execution_result,
        "selected_tab": "데이터 보기",
        "action_message": "보존할 메시지",
    }
    save_dashboard_preferences(state)

    reset_dashboard_preferences(state)

    assert DASHBOARD_PREFERENCES_KEY not in state
    assert "streamlit_selected_symbols" not in state
    assert "multi_symbol_picker" not in state
    assert "report_sort_option" not in state
    assert "data_comparison_range_dates" not in state
    assert "data_comparison_range_dates_widget_2026-02-01_2026-03-31" not in state
    assert "toggle_chart_daily_prices_005930_prices.csv" not in state
    assert state["backtest_results"] is execution_result
    assert state["selected_tab"] == "데이터 보기"
    assert state["action_message"] == "보존할 메시지"


def test_normalize_dashboard_preferences_safely_discards_bad_values_and_keeps_valid_siblings() -> None:
    normalized = normalize_dashboard_preferences(
        {
            "version": DASHBOARD_PREFERENCES_VERSION,
            "settings": {
                "actions": {"symbols": ["005930", 123], "collection_period": ["not-a-date", "2026-01-01"]},
                "reports": {"sort": "지원하지 않음", "favorites_only": True},
                "data": {"comparison_basis": "unsupported", "comparison_symbols": ["005930", "000660", "035420", "051910"]},
                "charts": {
                    "data_comparison": {
                        "range_mode": "unsupported",
                        "range_preset": "90d",
                        "range_dates": ["2026-03-31", "2026-02-01"],
                    }
                },
            },
        }
    )

    assert normalized == {
        "version": DASHBOARD_PREFERENCES_VERSION,
        "settings": {
            "actions": {"symbols": ["005930"]},
            "reports": {"favorites_only": True},
            "data": {"comparison_symbols": ["005930", "000660", "035420"]},
            "charts": {
                "data_comparison": {
                    "range_preset": "90d",
                    "range_dates": ["2026-02-01", "2026-03-31"],
                }
            },
        },
    }
    assert normalize_dashboard_preferences(None) is None
    assert normalize_dashboard_preferences({"version": 999, "settings": {}}) is None
    assert normalize_dashboard_preferences({"version": DASHBOARD_PREFERENCES_VERSION, "settings": []}) is None


def test_apply_partial_preferences_uses_widget_defaults_for_missing_or_invalid_fields() -> None:
    state = {
        "report_sort_option": "매수 관점 우선",
        "data_comparison_basis": "price",
        DASHBOARD_PREFERENCES_KEY: {
            "version": DASHBOARD_PREFERENCES_VERSION,
            "settings": {
                "reports": {"favorites_only": True, "sort": "지원하지 않음"},
                "data": {"comparison_basis": "지원하지 않음"},
            },
        },
    }

    assert apply_dashboard_preferences(state) is True

    assert state["report_favorites_only"] is True
    assert "report_sort_option" not in state
    assert "data_comparison_basis" not in state


def test_dashboard_preferences_are_isolated_to_the_current_session_state() -> None:
    first_session = _view_state()
    save_dashboard_preferences(first_session)
    second_session: dict[str, object] = {}

    assert capture_dashboard_preferences(second_session) == {
        "version": DASHBOARD_PREFERENCES_VERSION,
        "settings": {},
    }
    assert DASHBOARD_PREFERENCES_KEY not in second_session


def test_dashboard_preference_draft_keeps_visited_tab_values_after_widget_cleanup() -> None:
    state: dict[str, object] = {
        "streamlit_selected_symbols": ["005930", "000660"],
        "multi_symbol_picker": ["005930", "000660"],
        "action_collection_period": (date(2026, 1, 1), date(2026, 3, 31)),
    }

    sync_dashboard_preference_draft(state)
    state.pop("streamlit_selected_symbols")
    state.pop("multi_symbol_picker")
    state.pop("action_collection_period")
    state.update({"report_query": "삼성전자", "report_sort_option": "종목명순"})

    snapshot = save_dashboard_preferences(state)

    assert state[DASHBOARD_PREFERENCES_DRAFT_KEY] == snapshot
    assert snapshot["settings"] == {
        "actions": {
            "symbols": ["005930", "000660"],
            "collection_period": ["2026-01-01", "2026-03-31"],
        },
        "reports": {"query": "삼성전자", "sort": "종목명순"},
    }


def test_dashboard_preference_draft_restores_removed_tab_widgets_without_overwriting_live_values() -> None:
    state: dict[str, object] = {
        DASHBOARD_PREFERENCES_DRAFT_KEY: {
            "version": DASHBOARD_PREFERENCES_VERSION,
            "settings": {
                "reports": {
                    "query": "저장된 검색어",
                    "sort": "종목명순",
                }
            },
        },
        "report_query": "현재 탭의 새 검색어",
    }

    assert restore_dashboard_preference_draft(state, tab_name="투자 리포트") is True

    assert state["report_query"] == "현재 탭의 새 검색어"
    assert state["report_sort_option"] == "종목명순"


def test_dashboard_preference_draft_restores_a_report_query_after_actual_tab_round_trip() -> None:
    app = AppTest.from_function(_dashboard_preference_navigation_test_app).run()

    app.text_input[0].set_value("SK하이닉스").run()
    app.button[0].click().run()
    assert app.text_input[0].label == "데이터 보기 검색"

    app.button[1].click().run()

    assert app.text_input[0].label == "리포트 검색"
    assert app.text_input[0].value == "SK하이닉스"


def test_dashboard_preference_draft_keeps_action_widget_and_mirror_aligned_when_one_is_missing() -> None:
    state: dict[str, object] = {
        DASHBOARD_PREFERENCES_DRAFT_KEY: {
            "version": DASHBOARD_PREFERENCES_VERSION,
            "settings": {"actions": {"symbols": ["005930", "000660"]}},
        },
        "streamlit_selected_symbols": ["035420"],
    }

    assert restore_dashboard_preference_draft(state, tab_name="데이터 갱신") is True

    assert state["streamlit_selected_symbols"] == ["035420"]
    assert state["multi_symbol_picker"] == ["035420"]


def test_dashboard_preference_draft_restores_chart_state_only_for_the_active_tab() -> None:
    state: dict[str, object] = {
        DASHBOARD_PREFERENCES_DRAFT_KEY: {
            "version": DASHBOARD_PREFERENCES_VERSION,
            "settings": {
                "charts": {
                    "data_comparison": {"range_preset": "90d"},
                    "report_005930_market_reports.csv": {"timeframe": "weekly"},
                }
            },
        }
    }

    assert restore_dashboard_preference_draft(state, tab_name="투자 리포트") is True

    assert state["report_005930_market_reports.csv_timeframe"] == "weekly"
    assert "data_comparison_range_preset" not in state

    assert restore_dashboard_preference_draft(state, tab_name="데이터 보기") is True

    assert state["data_comparison_range_preset"] == "90d"


def test_dashboard_preference_draft_does_not_hydrate_tabs_without_supported_settings() -> None:
    state: dict[str, object] = {
        DASHBOARD_PREFERENCES_DRAFT_KEY: {
            "version": DASHBOARD_PREFERENCES_VERSION,
            "settings": {"actions": {"symbols": ["005930"]}},
        }
    }

    assert restore_dashboard_preference_draft(state, tab_name="홈") is True

    assert "streamlit_selected_symbols" not in state
    assert "multi_symbol_picker" not in state


def test_chart_preference_capture_ignores_unmanaged_state_keys() -> None:
    snapshot = capture_dashboard_preferences(
        {
            "data_comparison_range_preset": "90d",
            "report_005930_market_reports.csv_timeframe": "weekly",
            "unrelated_range_preset": "30d",
            "unrelated_timeframe": "monthly",
            "toggle_chart_daily_prices_005930_prices.csv": True,
            "toggle_chart_unrelated": True,
        }
    )

    assert snapshot["settings"] == {
        "charts": {
            "data_comparison": {"range_preset": "90d"},
            "report_005930_market_reports.csv": {"timeframe": "weekly"},
        },
        "chart_visibility": {"toggle_chart_daily_prices_005930_prices.csv": True},
    }


def test_apply_dashboard_preferences_clamps_saved_collection_period_to_current_bounds() -> None:
    _minimum_date, maximum_date = collection_period_bounds()
    future_start = maximum_date + timedelta(days=3)
    future_end = maximum_date + timedelta(days=7)
    state: dict[str, object] = {
        DASHBOARD_PREFERENCES_KEY: {
            "version": DASHBOARD_PREFERENCES_VERSION,
            "settings": {
                "actions": {"collection_period": [future_start.isoformat(), future_end.isoformat()]},
                "backtest": {"collection_period": [future_start.isoformat(), future_end.isoformat()]},
            },
        }
    }

    assert apply_dashboard_preferences(state) is True

    assert state["action_collection_period"] == (maximum_date, maximum_date)
    assert state["backtest_prepare_collection_period"] == (maximum_date, maximum_date)


def test_reset_dashboard_preferences_does_not_clear_unmanaged_widget_state() -> None:
    state = _view_state() | {"unrelated_range_widget_state": "keep"}
    save_dashboard_preferences(state)

    reset_dashboard_preferences(state)

    assert state["unrelated_range_widget_state"] == "keep"


def test_dynamic_symbol_and_strategy_sanitizers_fall_back_to_current_options(monkeypatch) -> None:
    fake_st = _FakeStreamlit(button_values={})
    fake_st.session_state.update(
        {
            "streamlit_selected_symbols": ["없는종목"],
            "multi_symbol_picker": ["없는종목", "005930"],
            "data_comparison_symbols": ["없는종목"],
            "backtest_selected_symbols": ["없는종목"],
            "backtest_selected_strategies": ["없는전략"],
        }
    )
    monkeypatch.setattr(actions_module, "st", fake_st)
    monkeypatch.setattr(data_module, "st", fake_st)
    monkeypatch.setattr(backtest_module, "st", fake_st)

    actions_module._sanitize_action_symbol_selection_state(["005930", "000660"])
    data_module._sanitize_comparison_symbol_selection(["005930", "000660"], ["005930", "000660"])
    backtest_module._sanitize_multiselect_state("backtest_selected_symbols", ["005930", "000660"], ["005930"])
    backtest_module._sanitize_multiselect_state("backtest_selected_strategies", ["golden-cross"], ["golden-cross"])

    assert fake_st.session_state["streamlit_selected_symbols"] == ["005930"]
    assert fake_st.session_state["multi_symbol_picker"] == ["005930"]
    assert fake_st.session_state["data_comparison_symbols"] == ["005930", "000660"]
    assert fake_st.session_state["backtest_selected_symbols"] == ["005930"]
    assert fake_st.session_state["backtest_selected_strategies"] == ["golden-cross"]


class _FakeContext:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None


class _FakeColumn:
    def __init__(self, owner: "_FakeStreamlit") -> None:
        self.owner = owner

    def button(self, *args, **kwargs) -> bool:
        return self.owner.button(*args, **kwargs)


class _FakeStreamlit:
    def __init__(self, *, button_values: dict[str, bool]) -> None:
        self.session_state: dict[str, object] = _view_state()
        self.button_values = button_values
        self.markdown_calls: list[str] = []
        self.caption_calls: list[str] = []
        self.warning_messages: list[str] = []
        self.rerun_calls = 0

    def container(self, **kwargs):
        return _FakeContext()

    def markdown(self, body: str, **kwargs) -> None:
        self.markdown_calls.append(body)

    def caption(self, body: str, **kwargs) -> None:
        self.caption_calls.append(body)

    def warning(self, message: str) -> None:
        self.warning_messages.append(message)

    def columns(self, count: int, **kwargs):
        return [_FakeColumn(self) for _ in range(count)]

    def button(self, label: str, *, key: str | None = None, **kwargs) -> bool:
        return self.button_values.get(key or label, False)

    def rerun(self) -> None:
        self.rerun_calls += 1


def test_preferences_panel_explains_session_scope_and_saves_current_settings(monkeypatch) -> None:
    fake_st = _FakeStreamlit(button_values={"dashboard_preferences_save": True})
    monkeypatch.setattr(preferences_module, "st", fake_st)

    preferences_module.render_dashboard_preferences_panel()

    captions = " ".join(fake_st.caption_calls)
    assert "현재 브라우저 세션" in captions
    assert "서버 파일·DB·다른 사용자" in captions
    assert "백테스트 결과와 실험 파라미터" in captions
    assert DASHBOARD_PREFERENCES_KEY in fake_st.session_state
    assert fake_st.session_state["action_message_type"] == "success"
    assert fake_st.rerun_calls == 1


def test_preferences_panel_applies_resets_and_discards_unreadable_snapshots(monkeypatch) -> None:
    fake_st = _FakeStreamlit(button_values={"dashboard_preferences_apply": True})
    save_dashboard_preferences(fake_st.session_state)
    fake_st.session_state["report_sort_option"] = "최신순"
    monkeypatch.setattr(preferences_module, "st", fake_st)

    preferences_module.render_dashboard_preferences_panel()

    assert fake_st.session_state["report_sort_option"] == "매수 관점 우선"
    assert fake_st.session_state["action_message_type"] == "success"
    assert fake_st.rerun_calls == 1

    corrupted_st = _FakeStreamlit(button_values={})
    corrupted_st.session_state[DASHBOARD_PREFERENCES_KEY] = {"version": 999, "settings": {}}
    monkeypatch.setattr(preferences_module, "st", corrupted_st)

    preferences_module.render_dashboard_preferences_panel()

    assert DASHBOARD_PREFERENCES_KEY not in corrupted_st.session_state
    assert corrupted_st.warning_messages == [
        "저장한 화면 설정을 읽을 수 없어 삭제했습니다. 현재 화면은 기본 동작으로 계속 사용할 수 있습니다."
    ]
