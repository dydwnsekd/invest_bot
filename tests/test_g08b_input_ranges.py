from __future__ import annotations

from datetime import UTC, date, datetime
import json
from html.parser import HTMLParser
from types import SimpleNamespace

import pandas as pd
import pytest

from invest_bot.backtest import resolve_backtest_combination_settings
from invest_bot.dashboard import streamlit_backtest as dashboard
from invest_bot.dashboard.service import DashboardDataService
from invest_bot.dashboard.backtest_input_ranges import signal_input_range, format_input_range, format_preparation_selection
from invest_bot.market.storage import CsvStorage
from invest_bot.db.frame_storage import DbFrameStorage
from sqlalchemy import event
from tests.helpers import init_test_db
from tests.test_streamlit_backtest import _FakeStreamlit, _loaded_inputs


def indicator_frame():
    return pd.DataFrame({
        "date": ["2026-04-03", "2026-04-01", "2026-04-02"],
        "close": [103.0, 100.0, 101.0],
        "rsi_14": [50.0, None, 50.0],
        "ma_5": [101.0, None, 100.0],
        "ma_20": [100.0, None, 99.0],
        "ma_60": [99.0, None, 98.0],
        "momentum_20": [1.0, None, 0.0],
    }, index=[4, 4, 4])


def items():
    return [dashboard.ResolvedSymbol("005930", "005930", "삼성전자")]


def inputs():
    return {"005930": _loaded_inputs(indicator=indicator_frame())}


def readiness(**kwargs):
    return dashboard._build_readiness_payload(
        selected_items=items(), selected_strategy_ids=["rsi", "golden-cross"],
        loaded_inputs=inputs(), strategy_labels={"rsi": "RSI", "golden-cross": "Golden Cross"},
        **kwargs,
    )


def execute(**kwargs):
    return dashboard._execute_backtests(items(), ["rsi", "golden-cross"], inputs(), **kwargs)


def test_ready_preview_reports_actual_adapter_rows_without_running(monkeypatch):
    monkeypatch.setattr(dashboard.DEFAULT_BACKTEST_RUNNER, "run", lambda *a, **kw: pytest.fail("preview ran runner"))
    preview = readiness()
    assert preview["ready_count"] == 2
    for _, row in preview["input_ranges"].iterrows():
        assert row["input_start_date"] == "2026-04-01"
        assert row["input_end_date"] == "2026-04-03"
        assert row["input_row_count"] == 3  # warm-up indicator NaNs are still real price bars


def test_execution_summary_uses_runner_rows_not_trade_or_price_range():
    result = execute()
    assert result["trade_frame"].empty
    for _, row in result["summary_frame"].iterrows():
        assert row["input_start_date"] == "2026-04-01"
        assert row["input_end_date"] == "2026-04-03"
        assert row["input_row_count"] == 3


def test_preparation_selection_is_fixed_per_execution_and_combination():
    selected = (date(2025, 4, 1), date(2026, 4, 1))
    result = execute(
        preparation_period=selected,
        combination_settings=resolve_backtest_combination_settings(["rsi", "golden-cross"]),
    )
    summary = result["summary_frame"]
    assert set(summary["strategy_id"]) == {"rsi", "golden-cross", "combination-and"}
    assert set(summary["prepare_selection_start_date"]) == {"2025-04-01"}
    assert set(summary["prepare_selection_end_date"]) == {"2026-04-01"}
    assert set(summary["prepare_lookback_days"]) == {365}
    assert set(summary["input_row_count"]) == {3}


def test_legacy_results_do_not_infer_input_or_request_from_current_selection(monkeypatch, tmp_path):
    result = execute()
    result["summary_frame"] = result["summary_frame"].drop(
        columns=[column for column in result["summary_frame"] if column.startswith(("input_", "prepare_"))],
    )
    screen = _FakeStreamlit()
    screen.session_state[dashboard.BACKTEST_COLLECTION_PERIOD_KEY] = (date(2020, 1, 1), date(2030, 1, 1))
    monkeypatch.setattr(dashboard, "st", screen)
    service = DashboardDataService(raw_root=tmp_path / "raw", processed_root=tmp_path / "processed")
    dashboard._render_results_panel(service, result)
    text = " ".join(screen.markdown_calls + screen.caption_calls + screen.info_messages)
    assert "실제 입력 범위" in text
    assert "기록 없음" in text
    assert "2020-01-01" not in text


class Screen(_FakeStreamlit):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.tables = []

    def dataframe(self, frame, **kwargs):
        self.tables.append(frame.copy(deep=True))
        super().dataframe(frame, **kwargs)


@pytest.fixture(autouse=True)
def no_real_execution_or_clock(monkeypatch):
    # Only pure in-memory adapter/runner execution is allowed in these fixtures.
    def forbidden(*args, **kwargs):
        pytest.fail("range display attempted collection/analysis/generation")

    for name in ("collect_market_data_for_symbols", "generate_indicators_for_symbol", "generate_golden_cross_signals_for_symbol"):
        monkeypatch.setattr(dashboard, name, forbidden)

    class Clock:
        @classmethod
        def now(cls, tz=None):
            return datetime(2026, 4, 10, 1, 2, 3, tzinfo=UTC)

    monkeypatch.setattr(dashboard, "datetime", Clock)


@pytest.mark.parametrize("length", [1, 2, 3])
def test_short_input_preview_and_runner_match_without_warmup_row_loss(monkeypatch, length):
    frame = indicator_frame().iloc[:length].copy()
    loaded = {"005930": _loaded_inputs(indicator=frame, price=pd.DataFrame({"date": ["1999-01-01"], "close": [1]}))}
    original = frame.copy(deep=True)
    strategies = ["rsi", "golden-cross"]
    settings = resolve_backtest_combination_settings(strategies)
    params = {"rsi": {"buy_threshold": 40, "sell_threshold": 60}, "golden-cross": {"short_window": 2, "long_window": 3}}
    preview = dashboard._build_readiness_payload(
        selected_items=items(), selected_strategy_ids=strategies, loaded_inputs=loaded, strategy_labels={},
        strategy_parameters=params, combination_settings=settings,
    )["input_ranges"]
    seen = []
    actual_run = dashboard.DEFAULT_BACKTEST_RUNNER.run

    def run(symbol, signal_rows):
        seen.append(signal_rows.copy(deep=True))
        return actual_run(symbol, signal_rows)

    monkeypatch.setattr(dashboard.DEFAULT_BACKTEST_RUNNER, "run", run)
    result = dashboard._execute_backtests(items(), strategies, loaded, strategy_parameters=params, combination_settings=settings)
    assert len(seen) == 3
    for index, row in result["summary_frame"].iterrows():
        expected = signal_input_range(seen[index])
        for column, value in expected.items():
            assert row[column] == value
            assert preview.iloc[index][column] == value
        assert row["input_row_count"] == length
    pd.testing.assert_frame_equal(frame, original)


def test_real_saved_adapter_and_combination_use_common_final_dates():
    # Current adapters intentionally normalize mixed string formats differently:
    # saved-signal alignment retains every verified local day; RSI may coerce a row.
    frame = indicator_frame().reset_index(drop=True)
    frame["date"] = ["2026-04-03 00:00:00", "2026-04-01 00:00:00", "2026-04-02"]
    saved = frame[["date", "close"]].assign(signal="hold")
    loaded = {"005930": _loaded_inputs(indicator=frame, golden_signal=saved)}
    strategies = ["rsi", "golden-cross"]
    settings = resolve_backtest_combination_settings(strategies)
    before = frame.copy(deep=True)
    payload = dashboard._build_readiness_payload(
        selected_items=items(), selected_strategy_ids=strategies, loaded_inputs=loaded,
        strategy_labels={}, combination_settings=settings,
    )
    result = dashboard._execute_backtests(items(), strategies, loaded, combination_settings=settings)
    preview = payload["input_ranges"].set_index("strategy_id")
    summary = result["summary_frame"].set_index("strategy_id")
    assert summary.loc["golden-cross", "input_row_count"] == 3
    assert summary.loc["rsi", "input_row_count"] == 2
    assert summary.loc["combination-and", "input_row_count"] == 2
    for strategy_id in summary.index:
        assert preview.loc[strategy_id, "input_row_count"] == summary.loc[strategy_id, "input_row_count"]
        assert preview.loc[strategy_id, "input_start_date"] == summary.loc[strategy_id, "input_start_date"]
        assert preview.loc[strategy_id, "input_end_date"] == summary.loc[strategy_id, "input_end_date"]
    pd.testing.assert_frame_equal(frame, before)


@pytest.mark.parametrize("dates, closes, count, excluded", [
    (["2026-04-03", "2026-04-01", "bad", None], [100, "101", 5, 6], 2, 2),
    (["2026-04-01", "2026-04-02", "2026-04-03", "2026-04-04"], [0, -1, "inf", "bad"], 0, 4),
    ([pd.Timestamp("2026-04-01 23:00:00-09:00"), pd.Timestamp("2026-04-02 01:00:00+09:00")], [100, 101], 2, 0),
    (["2026-04-01", "2026-04-02"], [None, True], 0, 2),
    ([], [], 0, 0),
])
def test_valid_daily_range_is_positional_and_read_only(dates, closes, count, excluded):
    frame = pd.DataFrame({"date": dates, "close": closes}, index=[7] * len(dates))
    frame.attrs["origin"] = {"values": [1]}
    before = frame.copy(deep=True)
    result = signal_input_range(frame)
    assert result["input_row_count"] == count
    assert result["input_excluded_rows"] == excluded
    if count:
        assert result["input_start_date"] == "2026-04-01"
    else:
        assert result["input_start_date"] is None and result["input_end_date"] is None
        assert "확인 불가" in format_input_range(result)
    pd.testing.assert_frame_equal(frame, before)
    assert frame.attrs == before.attrs
    json.dumps(result, allow_nan=False)


@pytest.mark.parametrize("kind", ["duplicate", "missing", "empty", "invalid-parameters", "adapter-error"])
def test_blocked_or_unavailable_preview_does_not_change_gate_or_run(monkeypatch, kind):
    frame = indicator_frame()
    params = None
    if kind == "duplicate":
        frame = pd.concat([frame, frame.iloc[:1]], ignore_index=True)
    elif kind == "missing":
        frame = frame.drop(columns=["rsi_14"])
    elif kind == "empty":
        frame = frame.iloc[:0]
    elif kind == "invalid-parameters":
        params = {}
    elif kind == "adapter-error":
        def fail(*args, **kwargs):
            raise ValueError("injected private adapter failure")
        monkeypatch.setattr(dashboard.DEFAULT_BACKTEST_ADAPTER_REGISTRY, "build_signal_rows", fail)
    loaded = {"005930": _loaded_inputs(indicator=frame)}
    gate = dashboard.check_backtest_readiness(["rsi"], loaded["005930"].readiness_datasets())
    monkeypatch.setattr(dashboard.DEFAULT_BACKTEST_RUNNER, "run", lambda *a, **kw: pytest.fail("preview ran runner"))
    payload = dashboard._build_readiness_payload(
        selected_items=items(), selected_strategy_ids=["rsi"], loaded_inputs=loaded,
        strategy_labels={}, strategy_parameters=params,
    )
    row = payload["input_ranges"].iloc[0]
    assert row["input_range_status"] == "unavailable"
    assert row["input_row_count"] is None
    assert payload["can_run"] == gate.ready_to_run
    assert "injected private" not in format_input_range(row)
    screen = Screen()
    monkeypatch.setattr(dashboard, "st", screen)
    dashboard._render_readiness_panel(payload)
    assert "확인 불가" in screen.tables[-1].iloc[0]["실제 입력 범위"]


def test_parameter_change_uses_actual_adapter_and_execution_failure_clears_stale(monkeypatch):
    frame = indicator_frame()
    saved = frame[["date", "close"]].iloc[:1].assign(signal="hold")
    loaded = {"005930": _loaded_inputs(indicator=frame, golden_signal=saved)}
    kwargs = dict(selected_items=items(), selected_strategy_ids=["golden-cross"], loaded_inputs=loaded, strategy_labels={})
    default = dashboard._build_readiness_payload(**kwargs)["input_ranges"].iloc[0]
    assert default["input_range_status"] == "unavailable"
    custom = {"golden-cross": {"short_window": 2, "long_window": 3}}
    preview = dashboard._build_readiness_payload(**kwargs, strategy_parameters=custom)["input_ranges"].iloc[0]
    result = dashboard._execute_backtests(items(), ["golden-cross"], loaded, strategy_parameters=custom)
    assert preview["input_row_count"] == result["summary_frame"].iloc[0]["input_row_count"] == 3
    screen = Screen()
    screen.session_state[dashboard.BACKTEST_RESULTS_KEY] = result
    monkeypatch.setattr(dashboard, "st", screen)
    dashboard._run_backtest_action(
        selected_items=items(), selected_strategy_ids=["golden-cross"], loaded_inputs=loaded,
        strategy_parameters={}, combination_settings=None,
    )
    assert dashboard.BACKTEST_RESULTS_KEY not in screen.session_state
    assert screen.session_state["action_message_type"] == "error"


def test_current_selection_does_not_rewrite_frozen_execution_or_call_runner(monkeypatch, tmp_path):
    selected = (date(2025, 4, 1), date(2026, 4, 1))
    loaded = inputs()
    screen = Screen(multiselect_queue=[["005930"], ["rsi"]], button_values={"백테스트 실행": True})
    screen.session_state[dashboard.BACKTEST_COLLECTION_PERIOD_KEY] = selected
    monkeypatch.setattr(dashboard, "st", screen)
    monkeypatch.setattr(dashboard, "_load_backtest_inputs", lambda *args: loaded["005930"])
    monkeypatch.setattr(dashboard, "_render_backtest_history_panel", lambda *args: None)
    service = DashboardDataService(raw_root=tmp_path / "raw", processed_root=tmp_path / "processed")
    lookup = SimpleNamespace(list_entries=lambda: [dashboard.SymbolEntry("005930", "삼성전자")])
    dashboard.render_backtest_tab(SimpleNamespace(raw_previews=[], processed_previews=[]), service, symbol_lookup=lookup)
    frozen = screen.session_state[dashboard.BACKTEST_RESULTS_KEY]["summary_frame"].copy(deep=True)
    assert frozen.iloc[0]["prepare_lookback_days"] == 365
    assert any("수집 실행 증거 아님" in body for body in screen.markdown_calls)
    screen.button_values = {}
    screen.session_state[dashboard.BACKTEST_COLLECTION_PERIOD_KEY] = (date(2024, 1, 1), date(2024, 1, 2))
    screen.multiselect_queue = [["005930"], ["golden-cross"]]
    monkeypatch.setattr(dashboard.DEFAULT_BACKTEST_RUNNER, "run", lambda *a, **kw: pytest.fail("selection ran runner"))
    dashboard.render_backtest_tab(SimpleNamespace(raw_previews=[], processed_previews=[]), service, symbol_lookup=lookup)
    pd.testing.assert_frame_equal(screen.session_state[dashboard.BACKTEST_RESULTS_KEY]["summary_frame"], frozen)
    result_table = [table for table in screen.tables if "준비용 선택 범위" in table][-1]
    assert "2025-04-01 ~ 2026-04-01" in result_table.iloc[0]["준비용 선택 범위"]
    assert result_table.iloc[0]["실제 입력 범위"] == "2026-04-01 ~ 2026-04-03 · 유효 고유 일봉 3개"
    assert "평가 기간:" in " ".join(screen.caption_calls)
    assert "입력 기간 필터나 수집 실행 증거가 아니며" in " ".join(screen.caption_calls)


@pytest.mark.parametrize("storage_kind", ["csv", "sqlite"])
def test_additive_metadata_survives_existing_storage_and_history_without_live_recalculation(monkeypatch, tmp_path, storage_kind):
    selected = (date(2025, 4, 1), date(2026, 4, 1))
    result = execute(preparation_period=selected)
    summary = result["summary_frame"]
    filename = "005930_20260410T010203Z_backtest_summary.csv"
    if storage_kind == "sqlite":
        url = f"sqlite:///{tmp_path / 'history.db'}"
        init_test_db(url)
        storage = DbFrameStorage(url)
        service = DashboardDataService(dataset_storage=storage)
    else:
        storage = CsvStorage(tmp_path / "processed")
        service = DashboardDataService(raw_root=tmp_path / "raw", processed_root=storage.root_dir)
    storage.save("backtest_summaries", filename, summary)
    monkeypatch.setattr(service, "_load_symbol_name_map", lambda: {})
    entries, _ = dashboard._load_backtest_history_entries(service)
    monkeypatch.setattr(dashboard.DEFAULT_BACKTEST_RUNNER, "run", lambda *a, **kw: pytest.fail("history ran runner"))
    for entry in entries:
        bundle, messages = dashboard._load_backtest_history_result(service, entry)
        assert bundle is not None and not messages
        row = bundle["summary_frame"].iloc[0]
        assert format_input_range(row) == "2026-04-01 ~ 2026-04-03 · 유효 고유 일봉 3개"
        assert "2025-04-01 ~ 2026-04-01" in format_preparation_selection(row)
        assert "365일" in format_preparation_selection(row)


def test_preview_uses_only_memory_and_multiple_symbol_ranges_do_not_leak(monkeypatch):
    first = indicator_frame()
    second = first.iloc[:1].copy()
    loaded = {"005930": _loaded_inputs(indicator=first), "000660": _loaded_inputs(indicator=second)}
    before = {key: value.indicator.frame.copy(deep=True) for key, value in loaded.items()}
    selected_items = items() + [dashboard.ResolvedSymbol("000660", "000660", "SK하이닉스")]
    monkeypatch.setattr(dashboard, "_load_backtest_inputs", lambda *a: pytest.fail("preview reloaded source"))
    monkeypatch.setattr(dashboard.DEFAULT_BACKTEST_RUNNER, "run", lambda *a: pytest.fail("preview ran runner"))
    payload = dashboard._build_readiness_payload(
        selected_items=selected_items, selected_strategy_ids=["rsi"], loaded_inputs=loaded, strategy_labels={},
    )
    by_symbol = payload["input_ranges"].set_index("symbol")
    assert by_symbol.loc["005930", "input_row_count"] == 3
    assert by_symbol.loc["000660", "input_row_count"] == 1
    for key in loaded:
        pd.testing.assert_frame_equal(loaded[key].indicator.frame, before[key])


def test_existing_source_load_budget_and_zero_queries_or_writes_for_range_preview(monkeypatch, tmp_path):
    url = f"sqlite:///{tmp_path / 'ranges.db'}"
    init_test_db(url)
    storage = DbFrameStorage(url)
    frame = indicator_frame()
    for dataset, content in (
        ("daily_prices_indicators", frame), ("daily_prices", frame[["date", "close"]]),
        ("investor_daily", pd.DataFrame({"date": frame["date"], "foreign_net_qty": 1, "institutional_net_qty": 1})),
        ("golden_cross_signals", frame[["date", "close"]].assign(signal="hold")),
    ):
        storage.save(dataset, f"005930_{dataset}.csv", content.reset_index(drop=True))
    service = DashboardDataService(dataset_storage=storage)
    selects = []
    engine = storage.repository.session_factory.kw["bind"]

    def observe(conn, cursor, statement, parameters, context, executemany):
        selects.append(statement)

    event.listen(engine, "before_cursor_execute", observe)
    try:
        loaded = {"005930": dashboard._load_backtest_inputs(service, "005930")}
        assert len(selects) == 8  # existing four sources, each latest + load
        assert all(statement.lstrip().upper().startswith("SELECT") for statement in selects)
        selects.clear()
        monkeypatch.setattr(storage, "save", lambda *a, **kw: pytest.fail("preview saved output"))
        monkeypatch.setattr(dashboard.DEFAULT_BACKTEST_RUNNER, "run", lambda *a, **kw: pytest.fail("preview ran runner"))
        payload = dashboard._build_readiness_payload(
            selected_items=items(), selected_strategy_ids=["rsi", "golden-cross"],
            loaded_inputs=loaded, strategy_labels={},
            combination_settings=resolve_backtest_combination_settings(["rsi", "golden-cross"]),
        )
        screen = Screen()
        monkeypatch.setattr(dashboard, "st", screen)
        dashboard._render_readiness_panel(payload)
        assert selects == []
        assert set(payload["input_ranges"]["input_row_count"]) == {3}
        assert len(screen.tables[-1]) == 3
    finally:
        event.remove(engine, "before_cursor_execute", observe)


def test_old_action_call_keeps_existing_execute_kwargs_when_request_is_not_supplied(monkeypatch):
    calls = []

    def old_execute(selected_items, selected_strategy_ids, loaded_inputs, *, strategy_parameters, combination_settings):
        calls.append((selected_items, selected_strategy_ids))
        return {"legacy": True}

    screen = Screen()
    monkeypatch.setattr(dashboard, "st", screen)
    monkeypatch.setattr(dashboard, "_execute_backtests", old_execute)
    dashboard._run_backtest_action(
        selected_items=items(), selected_strategy_ids=["rsi"], loaded_inputs=inputs(),
        strategy_parameters={}, combination_settings=None,
    )
    assert calls
    assert screen.session_state[dashboard.BACKTEST_RESULTS_KEY] == {"legacy": True}
    assert screen.session_state["action_message_type"] == "success"


@pytest.mark.parametrize("frame", [
    pd.DataFrame({"date": ["2026-04-01", "2026-04-01 12:00:00"], "close": [100, None]}),
    pd.DataFrame({"close": [100]}),
])
def test_range_helper_does_not_hide_duplicate_days_or_invent_missing_dates(frame):
    result = signal_input_range(frame)
    assert result["input_range_status"] == "unavailable"
    assert result["input_row_count"] is None
    assert result["input_start_date"] is None and result["input_end_date"] is None
    assert "확인 불가" in format_input_range(result)


class RangeNoteParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.tags = []
        self.text = []

    def handle_starttag(self, tag, attrs):
        self.tags.append(tag)

    def handle_data(self, data):
        self.text.append(data)


@pytest.mark.parametrize("stage", ["preparation", "result"])
@pytest.mark.parametrize("kind", ["normal", "legacy", "escape"])
def test_ui01_real_renderers_provide_complete_wrapping_range_notes(monkeypatch, tmp_path, stage, kind):
    selected = (date(2025, 4, 1), date(2026, 4, 1))
    settings = resolve_backtest_combination_settings(["rsi", "golden-cross"])
    screen = Screen()
    monkeypatch.setattr(dashboard, "st", screen)
    if stage == "preparation":
        payload = readiness(preparation_period=selected, combination_settings=settings)
        ranges = payload["input_ranges"]
    else:
        bundle = execute(preparation_period=selected, combination_settings=settings)
        ranges = bundle["summary_frame"]
    if kind == "legacy":
        ranges.drop(columns=[column for column in ranges if column.startswith(("input_", "prepare_"))], inplace=True)
    elif kind == "escape":
        ranges["symbol_name"] = '가상 <img src=x onerror="alert(1)"> & 종목'
        ranges["strategy_name"] = '전략 <script>unsafe()</script> "인용"'
        ranges["input_range_status"] = "unavailable"
        ranges["input_range_reason"] = '관측 누락 <svg onload="bad()"> & 확인'
    if stage == "preparation":
        dashboard._render_readiness_panel(payload)
    else:
        service = DashboardDataService(raw_root=tmp_path / "raw", processed_root=tmp_path / "processed")
        dashboard._render_results_panel(service, bundle)
    notes = [body for body in screen.markdown_calls if 'data-backtest-input-range="true"' in body]
    assert len(notes) == 3  # every single strategy and the combination, not only head(1)
    for note in notes:
        assert note.startswith('<div class="summary-box"')
        assert len(note.splitlines()) == 1  # no indented Markdown code after joining HTML blocks
        assert "white-space:normal" in note and "overflow-wrap:anywhere" in note
        parser = RangeNoteParser()
        parser.feed(note)
        text = " ".join(parser.text)
        for label in ("종목", "전략", "실제 입력 범위", "준비용 선택 범위"):
            assert label in text
        if kind == "normal":
            for value in ("2026-04-01", "2026-04-03", "유효 고유 일봉 3개", "2025-04-01", "준비용 조회 옵션 365일", "수집 실행 증거 아님"):
                assert value in text
        elif kind == "legacy":
            assert "기록 없음 (실행 당시 입력 범위 미기록)" in text
            assert "기록 없음 (실행 당시 준비용 선택 범위 미기록)" in text
            assert "2025-04-01" not in text
        else:
            assert "확인 불가" in text and "관측 누락" in text
            assert "<img" not in note and "<script" not in note and "<svg" not in note
            assert "&lt;img" in note and "&quot;" in note and "&amp;" in note
            assert '가상 <img src=x onerror="alert(1)"> & 종목' in text
            assert set(parser.tags) <= {"div", "p", "strong", "br"}
