from __future__ import annotations

from types import SimpleNamespace

import pandas as pd
import pytest

import invest_bot.dashboard.streamlit_backtest as streamlit_backtest_module
import invest_bot.dashboard.streamlit_dashboard as streamlit_dashboard_module
from invest_bot.dashboard.service import DashboardDataService
from invest_bot.dashboard.streamlit_backtest import (
    BACKTEST_RESULTS_KEY,
    LoadedBacktestInputs,
    LoadedDataset,
)
from invest_bot.dashboard.streamlit_layout import TAB_NAMES
from invest_bot.market.symbol_lookup import SymbolEntry


class _FakeMetricColumn:
    def __init__(self, owner):
        self.owner = owner

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None

    def multiselect(self, *args, **kwargs):
        return self.owner.multiselect(*args, **kwargs)

    def number_input(self, *args, **kwargs):
        return self.owner.number_input(*args, **kwargs)

    def button(self, *args, **kwargs):
        return self.owner.button(*args, **kwargs)

    def metric(self, *args, **kwargs):
        return self.owner.metric(*args, **kwargs)


class _FakeContext:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None


class _FakeSessionState(dict):
    def __getattr__(self, name: str):
        try:
            return self[name]
        except KeyError as error:
            raise AttributeError(name) from error

    def __setattr__(self, name: str, value) -> None:
        self[name] = value


class _FakeStreamlit:
    def __init__(self, *, multiselect_queue: list[list[str]] | None = None, button_values: dict[str, bool] | None = None):
        self.multiselect_queue = list(multiselect_queue or [])
        self.button_values = button_values or {}
        self.session_state = _FakeSessionState()
        self.warning_messages: list[str] = []
        self.info_messages: list[str] = []
        self.success_messages: list[str] = []
        self.error_messages: list[str] = []
        self.markdown_calls: list[str] = []
        self.caption_calls: list[str] = []
        self.metric_calls: list[tuple[str, object]] = []
        self.multiselect_labels: list[str] = []
        self.button_labels: list[str] = []
        self.number_input_labels: list[str] = []
        self.dataframe_calls = 0
        self.altair_chart_calls: list[object] = []

    def markdown(self, body: str, *args, **kwargs) -> None:
        self.markdown_calls.append(body)

    def caption(self, body: str, *args, **kwargs) -> None:
        self.caption_calls.append(body)

    def warning(self, message: str) -> None:
        self.warning_messages.append(message)

    def info(self, message: str) -> None:
        self.info_messages.append(message)

    def success(self, message: str) -> None:
        self.success_messages.append(message)

    def error(self, message: str) -> None:
        self.error_messages.append(message)

    def container(self, **kwargs):
        return _FakeContext()

    def columns(self, spec, **kwargs):
        count = spec if isinstance(spec, int) else len(spec)
        return [_FakeMetricColumn(self) for _ in range(count)]

    def multiselect(self, label: str, options: list[str], default=None, key: str | None = None, **kwargs):
        self.multiselect_labels.append(label)
        value = self.multiselect_queue.pop(0) if self.multiselect_queue else (default or [])
        if key is not None:
            self.session_state[key] = value
        return value

    def number_input(self, label: str, value=0, key: str | None = None, **kwargs):
        self.number_input_labels.append(label)
        if key is not None:
            self.session_state[key] = value
        return value

    def button(self, label: str, key: str | None = None, **kwargs):
        self.button_labels.append(label)
        return self.button_values.get(key or label, False)

    def metric(self, label: str, value=None, *args, **kwargs) -> None:
        self.metric_calls.append((label, value))

    def dataframe(self, *args, **kwargs) -> None:
        self.dataframe_calls += 1

    def altair_chart(self, chart, *args, **kwargs) -> None:
        self.altair_chart_calls.append(chart)

    def rerun(self) -> None:
        return None


def _loaded_inputs(
    *,
    indicator: pd.DataFrame | None = None,
    investor: pd.DataFrame | None = None,
    price: pd.DataFrame | None = None,
    golden_signal: pd.DataFrame | None = None,
) -> LoadedBacktestInputs:
    return LoadedBacktestInputs(
        symbol="005930",
        indicator=LoadedDataset("daily_prices_indicators", "005930_indicators.csv", indicator),
        investor=LoadedDataset("investor_daily", "005930_investor.csv", investor),
        price=LoadedDataset("daily_prices", "005930_prices.csv", price),
        golden_cross_signal=LoadedDataset("golden_cross_signals", "005930_signals.csv", golden_signal),
    )


def test_backtest_tab_is_registered_in_sidebar_contract() -> None:
    assert "백테스트" in TAB_NAMES


def test_render_backtest_tab_shows_blocked_feedback_for_unready_selection(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_st = _FakeStreamlit(
        multiselect_queue=[["005930"], ["golden-cross", "investor-flow-custom"]],
        button_values={"백테스트 실행": True},
    )
    fake_st.session_state[BACKTEST_RESULTS_KEY] = {"summary_frame": pd.DataFrame([{"strategy_id": "stale"}])}
    indicator_frame = pd.DataFrame(
        [
            {"date": "2026-04-01", "close": 100, "ma_5": 98, "ma_20": 99, "ma_60": 97, "rsi_14": 50, "momentum_20": 0},
            {"date": "2026-04-02", "close": 101, "ma_5": 100, "ma_20": 99, "ma_60": 97, "rsi_14": 45, "momentum_20": 1},
        ]
    )

    monkeypatch.setattr(streamlit_backtest_module, "st", fake_st)
    monkeypatch.setattr(
        streamlit_backtest_module,
        "_load_backtest_inputs",
        lambda service, symbol: _loaded_inputs(indicator=indicator_frame, investor=None),
    )

    streamlit_backtest_module.render_backtest_tab(
        SimpleNamespace(raw_previews=[], processed_previews=[]),
        DashboardDataService(),
        symbol_lookup=SimpleNamespace(list_entries=lambda: [SymbolEntry(symbol="005930", symbol_name="삼성전자")]),
    )

    assert fake_st.multiselect_labels == ["종목 선택", "전략 선택"]
    assert fake_st.session_state["action_message_type"] == "warning"
    assert "백테스트 실행 차단" in str(fake_st.session_state["action_message"])
    assert BACKTEST_RESULTS_KEY not in fake_st.session_state
    assert fake_st.dataframe_calls >= 1
    assert any("investor-flow-custom" in message for message in fake_st.warning_messages)


def test_render_backtest_tab_runs_and_renders_result_sections(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_st = _FakeStreamlit(
        multiselect_queue=[["005930"], ["golden-cross", "rsi"]],
        button_values={"백테스트 실행": True},
    )
    indicator_frame = pd.DataFrame(
        [
            {"date": "2026-04-01", "close": 100, "ma_5": 98, "ma_20": 99, "ma_60": 97, "rsi_14": 50, "momentum_20": 0},
            {"date": "2026-04-02", "close": 101, "ma_5": 100, "ma_20": 99, "ma_60": 97, "rsi_14": 25, "momentum_20": 2},
            {"date": "2026-04-03", "close": 103, "ma_5": 101, "ma_20": 100, "ma_60": 98, "rsi_14": 55, "momentum_20": 4},
            {"date": "2026-04-04", "close": 107, "ma_5": 99, "ma_20": 100, "ma_60": 98, "rsi_14": 75, "momentum_20": -2},
            {"date": "2026-04-05", "close": 110, "ma_5": 98, "ma_20": 100, "ma_60": 98, "rsi_14": 50, "momentum_20": -1},
        ]
    )
    golden_signal_frame = pd.DataFrame(
        [
            {"date": "2026-04-01", "close": 100, "signal": "hold", "signal_reason": "hold"},
            {"date": "2026-04-02", "close": 101, "signal": "buy", "signal_reason": "buy"},
            {"date": "2026-04-03", "close": 103, "signal": "hold", "signal_reason": "hold"},
            {"date": "2026-04-04", "close": 107, "signal": "sell", "signal_reason": "sell"},
            {"date": "2026-04-05", "close": 110, "signal": "hold", "signal_reason": "hold"},
        ]
    )
    investor_frame = pd.DataFrame(
        [
            {"trade_date": "2026-04-01", "foreign_net_qty": 10, "institutional_net_qty": 5},
            {"trade_date": "2026-04-02", "foreign_net_qty": 11, "institutional_net_qty": 6},
            {"trade_date": "2026-04-03", "foreign_net_qty": 12, "institutional_net_qty": 7},
            {"trade_date": "2026-04-04", "foreign_net_qty": 9, "institutional_net_qty": 4},
            {"trade_date": "2026-04-05", "foreign_net_qty": 8, "institutional_net_qty": 3},
        ]
    )

    monkeypatch.setattr(streamlit_backtest_module, "st", fake_st)
    monkeypatch.setattr(
        streamlit_backtest_module,
        "_load_backtest_inputs",
        lambda service, symbol: _loaded_inputs(
            indicator=indicator_frame,
            investor=investor_frame,
            price=indicator_frame[["date", "close"]].copy(),
            golden_signal=golden_signal_frame,
        ),
    )

    streamlit_backtest_module.render_backtest_tab(
        SimpleNamespace(raw_previews=[], processed_previews=[]),
        DashboardDataService(),
        symbol_lookup=SimpleNamespace(list_entries=lambda: [SymbolEntry(symbol="005930", symbol_name="삼성전자")]),
    )

    result_bundle = fake_st.session_state[BACKTEST_RESULTS_KEY]
    assert fake_st.session_state["action_message_type"] == "success"
    assert isinstance(result_bundle["summary_frame"], pd.DataFrame)
    assert len(result_bundle["summary_frame"]) == 2
    assert not result_bundle["comparison_frame"].empty
    assert not result_bundle["trade_frame"].empty
    assert not result_bundle["chart_frame"].empty
    assert fake_st.dataframe_calls >= 3
    assert len(fake_st.altair_chart_calls) == 1
    assert any("전략 요약 카드" in body for body in fake_st.markdown_calls)
    assert any("전략 비교표" in body for body in fake_st.markdown_calls)
    assert any("거래 순서 누적 수익률" in body for body in fake_st.markdown_calls)
    assert any("거래 로그" in body for body in fake_st.markdown_calls)


def test_render_backtest_tab_prepare_button_wires_collect_analyze_and_signal(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_st = _FakeStreamlit(
        multiselect_queue=[["005930"], ["golden-cross"]],
        button_values={"준비 실행": True},
    )
    calls: list[tuple[str, str | int | tuple[str, ...]]] = []

    monkeypatch.setattr(streamlit_backtest_module, "st", fake_st)
    monkeypatch.setattr(
        streamlit_backtest_module,
        "_load_backtest_inputs",
        lambda service, symbol: _loaded_inputs(indicator=None, investor=None),
    )
    monkeypatch.setattr(
        streamlit_backtest_module,
        "collect_market_data_for_symbols",
        lambda *, symbols, days: calls.append(("collect", tuple(symbols), days)) or {"successful_symbols": ["005930"], "failed_count": 0},
    )
    monkeypatch.setattr(
        streamlit_backtest_module,
        "generate_indicators_for_symbol",
        lambda symbol: calls.append(("indicators", symbol)),
    )
    monkeypatch.setattr(
        streamlit_backtest_module,
        "generate_golden_cross_signals_for_symbol",
        lambda symbol: calls.append(("signals", symbol)),
    )

    streamlit_backtest_module.render_backtest_tab(
        SimpleNamespace(raw_previews=[], processed_previews=[]),
        DashboardDataService(),
        symbol_lookup=SimpleNamespace(list_entries=lambda: [SymbolEntry(symbol="005930", symbol_name="삼성전자")]),
    )

    assert calls == [
        ("collect", ("005930",), streamlit_backtest_module.DEFAULT_COLLECTION_LOOKBACK_DAYS),
        ("indicators", "005930"),
        ("signals", "005930"),
    ]
    assert fake_st.session_state["action_message_type"] == "success"
    assert "백테스트 준비 완료" in str(fake_st.session_state["action_message"])


def test_execute_backtests_reuses_one_batch_run_group_id(monkeypatch: pytest.MonkeyPatch) -> None:
    real_datetime = streamlit_backtest_module.datetime

    class _SteppedDateTime:
        calls = 0

        @classmethod
        def now(cls, tz=None):
            values = [
                real_datetime(2026, 7, 20, 1, 2, 3, tzinfo=streamlit_backtest_module.UTC),
                real_datetime(2026, 7, 20, 1, 2, 4, tzinfo=streamlit_backtest_module.UTC),
                real_datetime(2026, 7, 20, 1, 2, 5, tzinfo=streamlit_backtest_module.UTC),
            ]
            value = values[min(cls.calls, len(values) - 1)]
            cls.calls += 1
            return value

    indicator_frame = pd.DataFrame(
        [
            {"date": "2026-04-01", "close": 100, "ma_5": 98, "ma_20": 99, "ma_60": 97, "rsi_14": 50, "momentum_20": 0},
            {"date": "2026-04-02", "close": 101, "ma_5": 100, "ma_20": 99, "ma_60": 97, "rsi_14": 25, "momentum_20": 2},
            {"date": "2026-04-03", "close": 103, "ma_5": 101, "ma_20": 100, "ma_60": 98, "rsi_14": 55, "momentum_20": 4},
            {"date": "2026-04-04", "close": 107, "ma_5": 99, "ma_20": 100, "ma_60": 98, "rsi_14": 75, "momentum_20": -2},
            {"date": "2026-04-05", "close": 110, "ma_5": 98, "ma_20": 100, "ma_60": 98, "rsi_14": 50, "momentum_20": -1},
        ]
    )
    golden_signal_frame = pd.DataFrame(
        [
            {"date": "2026-04-01", "close": 100, "signal": "hold", "signal_reason": "hold"},
            {"date": "2026-04-02", "close": 101, "signal": "buy", "signal_reason": "buy"},
            {"date": "2026-04-03", "close": 103, "signal": "hold", "signal_reason": "hold"},
            {"date": "2026-04-04", "close": 107, "signal": "sell", "signal_reason": "sell"},
            {"date": "2026-04-05", "close": 110, "signal": "hold", "signal_reason": "hold"},
        ]
    )
    investor_frame = pd.DataFrame(
        [
            {"trade_date": "2026-04-01", "foreign_net_qty": 10, "institutional_net_qty": 5},
            {"trade_date": "2026-04-02", "foreign_net_qty": 11, "institutional_net_qty": 6},
            {"trade_date": "2026-04-03", "foreign_net_qty": 12, "institutional_net_qty": 7},
            {"trade_date": "2026-04-04", "foreign_net_qty": 9, "institutional_net_qty": 4},
            {"trade_date": "2026-04-05", "foreign_net_qty": 8, "institutional_net_qty": 3},
        ]
    )

    monkeypatch.setattr(streamlit_backtest_module, "datetime", _SteppedDateTime)

    result = streamlit_backtest_module._execute_backtests(
        [SimpleNamespace(symbol="005930", symbol_name="삼성전자")],
        ["golden-cross", "rsi"],
        {
            "005930": _loaded_inputs(
                indicator=indicator_frame,
                investor=investor_frame,
                price=indicator_frame[["date", "close"]].copy(),
                golden_signal=golden_signal_frame,
            )
        },
    )

    summary_frame = result["summary_frame"]
    assert list(summary_frame["run_group_id"].unique()) == ["backtest_group_20260720T010203Z"]
    assert set(summary_frame["run_id"].unique()) == {
        "005930_golden-cross_20260720T010203Z",
        "005930_rsi_20260720T010203Z",
    }
    assert result["generated_at"] == "2026-07-20T01:02:03+00:00"
    assert _SteppedDateTime.calls == 1



def test_streamlit_dashboard_main_routes_backtest_tab(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_st = SimpleNamespace(
        session_state=_FakeSessionState(selected_tab="백테스트", action_message=None, action_message_type="info"),
        set_page_config=lambda **kwargs: None,
    )
    captured: dict[str, object] = {}
    settings = SimpleNamespace()
    snapshot = SimpleNamespace()

    monkeypatch.setattr(streamlit_dashboard_module, "st", fake_st)
    monkeypatch.setattr(streamlit_dashboard_module, "_apply_custom_style", lambda: None)
    monkeypatch.setattr(streamlit_dashboard_module, "_render_sidebar", lambda *args, **kwargs: None)
    monkeypatch.setattr(streamlit_dashboard_module, "_render_header", lambda: None)
    monkeypatch.setattr(streamlit_dashboard_module, "_render_action_feedback", lambda: None)
    monkeypatch.setattr(streamlit_dashboard_module, "_load_optional_schedule_status", lambda: None)
    monkeypatch.setattr(streamlit_dashboard_module, "_read_preview_frame", lambda service, preview: None)
    monkeypatch.setattr(streamlit_dashboard_module, "_load_indicator_frame_for_symbol", lambda service, symbol: None)
    monkeypatch.setattr(streamlit_dashboard_module, "SymbolLookup", lambda: "lookup")
    monkeypatch.setattr(
        streamlit_dashboard_module.AppSettings,
        "from_file",
        classmethod(lambda cls: settings),
    )

    class _FakeService:
        def __init__(self, *, settings):
            captured["settings"] = settings

        def build_snapshot(self):
            return snapshot

        def load_test_report(self):
            return None

    monkeypatch.setattr(streamlit_dashboard_module, "DashboardDataService", _FakeService)
    monkeypatch.setattr(
        streamlit_dashboard_module,
        "_render_backtest_tab",
        lambda passed_snapshot, service, *, symbol_lookup: captured.update(
            {"snapshot": passed_snapshot, "service": service, "symbol_lookup": symbol_lookup}
        ),
    )

    streamlit_dashboard_module.main()

    assert captured["settings"] is settings
    assert captured["snapshot"] is snapshot
    assert captured["symbol_lookup"] == "lookup"
