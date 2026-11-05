"""Independent G08b integration checks, with no real services or source mutation."""
from __future__ import annotations

import copy
import math
from datetime import UTC, date, datetime
from html.parser import HTMLParser
from types import SimpleNamespace

import pandas as pd
import pytest
from sqlalchemy import event

from invest_bot.backtest import resolve_backtest_combination_settings
from invest_bot.dashboard import streamlit_backtest as app
from invest_bot.dashboard.service import DashboardDataService
from invest_bot.db.frame_storage import DbFrameStorage
from invest_bot.market.storage import CsvStorage
from tests.helpers import init_test_db
from tests.test_streamlit_backtest import _FakeStreamlit

FIELDS = (
    "input_range_status", "input_range_reason", "input_start_date", "input_end_date",
    "input_row_count", "input_excluded_rows", "prepare_selection_start_date",
    "prepare_selection_end_date", "prepare_lookback_days",
)
PERIOD = (date(2025, 5, 4), date(2026, 5, 4))


class Screen(_FakeStreamlit):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.tables = []

    def dataframe(self, frame, **kwargs):
        self.tables.append(frame.copy(deep=True))
        super().dataframe(frame, **kwargs)


class Text(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.parts, self.tags = [], []
        self.feed(html)

    def handle_data(self, value):
        self.parts.append(value)

    def handle_starttag(self, tag, attrs):
        self.tags.append(tag)

    @property
    def value(self):
        return " ".join(self.parts)


def notes(screen):
    return [html for html in screen.markdown_calls if 'data-backtest-input-range="true"' in html]


def indicators(*, offset=0, mixed=False, invalid_close=False):
    values = ["2026-05-06", "2026-05-04", "2026-05-05"]
    if mixed:
        values = ["2026-05-06 00:00:00", "2026-05-04", "2026-05-05 00:00:00"]
    frame = pd.DataFrame({
        "date": values, "close": [106.0 + offset, 100.0 + offset, 102.0 + offset],
        "rsi_14": [50.0, None, 50.0], "ma_5": [103.0, None, 101.0],
        "ma_20": [102.0, None, 100.0], "ma_60": [101.0, None, 99.0],
        "momentum_20": [1.0, None, 1.0],
    }, index=[7, 7, 7])
    if invalid_close:
        frame.loc[:, "close"] = [0, 100, 102]
    frame.attrs["synthetic_origin"] = {"keep": [1, 2]}
    return frame


def loaded(symbol="005930", *, frame=None):
    frame = indicators() if frame is None else frame
    return app.LoadedBacktestInputs(
        symbol=symbol,
        indicator=app.LoadedDataset("daily_prices_indicators", f"{symbol}_indicators.csv", frame),
        investor=app.LoadedDataset("investor_daily", None, None),
        price=app.LoadedDataset("daily_prices", f"{symbol}_raw.csv",
                               pd.DataFrame({"date": ["1995-01-01"], "close": [1]})),
        golden_cross_signal=app.LoadedDataset("golden_cross_signals", f"{symbol}_saved.csv",
                                             frame[["date", "close"]].assign(signal="hold")),
    )


def items(symbols=("005930",)):
    return [app.ResolvedSymbol(s, s, "QA " + s) for s in symbols]


@pytest.fixture(autouse=True)
def side_effect_boundary(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("range-only path called collection, generation or settings loader")
    for name in ("collect_market_data_for_symbols", "generate_indicators_for_symbol",
                 "generate_golden_cross_signals_for_symbol"):
        monkeypatch.setattr(app, name, forbidden)

    class FixedClock:
        @classmethod
        def now(cls, tz=None):
            return datetime(2026, 11, 5, 1, 2, 3, tzinfo=UTC)
    monkeypatch.setattr(app, "datetime", FixedClock)


def independent_range(frame):
    days = []
    for value, close in zip(frame["date"], frame["close"]):
        stamp = pd.Timestamp(value)
        if pd.isna(stamp) or isinstance(close, bool):
            continue
        try:
            number = float(close)
        except (ValueError, TypeError):
            continue
        if math.isfinite(number) and number > 0:
            days.append(stamp.date())
    assert len(days) == len(set(days))
    return min(days).isoformat(), max(days).isoformat(), len(days), len(frame)-len(days)


@pytest.mark.parametrize("mixed", [False, True])
def test_real_preview_runner_and_combiner_with_two_symbols_and_hold_rows(monkeypatch, mixed):
    symbols = ("005930", "000660")
    frames = {s: indicators(offset=i*100, mixed=mixed) for i, s in enumerate(symbols)}
    originals = {s: copy.deepcopy(f) for s, f in frames.items()}
    sources = {s: loaded(s, frame=f) for s, f in frames.items()}
    strategies = ["rsi", "golden-cross"]
    combination = resolve_backtest_combination_settings(strategies)
    seen, raw_results = [], []
    original_run = app.DEFAULT_BACKTEST_RUNNER.run

    def run(symbol, signal_rows):
        seen.append((symbol, signal_rows.copy(deep=True)))
        result = original_run(symbol, signal_rows)
        raw_results.append(copy.deepcopy(result.summary))
        return result

    monkeypatch.setattr(app.DEFAULT_BACKTEST_RUNNER, "run", run)
    preview = app._build_readiness_payload(selected_items=items(symbols), selected_strategy_ids=strategies,
        loaded_inputs=sources, strategy_labels={}, combination_settings=combination, preparation_period=PERIOD)
    assert seen == [] and preview["can_run"] is True
    result = app._execute_backtests(items(symbols), strategies, sources,
                                    combination_settings=combination, preparation_period=PERIOD)
    assert len(seen) == 6
    summary = result["summary_frame"].reset_index(drop=True)
    expected = preview["input_ranges"].set_index(["symbol", "strategy_id"])
    for n, record in summary.iterrows():
        symbol, frame = seen[n]
        start, end, count, excluded = independent_range(frame)
        assert symbol == record["symbol"]
        for field, value in zip(("input_start_date","input_end_date","input_row_count","input_excluded_rows"),
                                (start,end,count,excluded)):
            assert record[field] == value == expected.loc[(symbol, record.strategy_id), field]
        assert record.input_start_date != "1995-01-01"
        assert record.prepare_selection_start_date == "2025-05-04" and record.prepare_lookback_days == 365
        assert set(frame.signal) == {"hold"}  # Warm-up hold still counts as a valid price bar.
        for column in raw_results[n].columns:
            pd.testing.assert_series_equal(raw_results[n][column].reset_index(drop=True),
                summary.loc[[n], column].reset_index(drop=True), check_dtype=False, check_names=False)
    if mixed:
        for symbol in symbols:
            rows = summary[summary.symbol == symbol].set_index("strategy_id")
            assert rows.loc["golden-cross", "input_row_count"] == 3
            assert rows.loc["rsi", "input_row_count"] == rows.loc["combination-and", "input_row_count"] == 2
            assert rows.loc["golden-cross", "input_start_date"] == "2026-05-04"
            assert rows.loc["rsi", "input_start_date"] == rows.loc["combination-and", "input_start_date"] == "2026-05-05"
    for symbol in symbols:
        pd.testing.assert_frame_equal(frames[symbol], originals[symbol])
        assert frames[symbol].attrs == originals[symbol].attrs


def test_raw_source_rows_and_valid_display_count_stay_distinct():
    source = loaded(frame=indicators(invalid_close=True))
    result = app._execute_backtests(items(), ["rsi"], {"005930": source}, preparation_period=PERIOD)
    record = result["summary_frame"].iloc[0]
    assert record["source_rows"] == 3
    assert record["input_row_count"] == 2 and record["input_excluded_rows"] == 1
    assert record["input_start_date"] == "2026-05-04" and record["input_end_date"] == "2026-05-05"



def test_full_renderer_explicit_run_then_selection_and_source_change_do_not_rewrite_result(monkeypatch, tmp_path):
    symbols = ("005930", "000660")
    sources = {s: loaded(s) for s in symbols}
    service = DashboardDataService(raw_root=tmp_path/"raw", processed_root=tmp_path/"processed")
    lookup = SimpleNamespace(list_entries=lambda: [app.SymbolEntry(s, "QA "+s) for s in symbols])
    screen = Screen(multiselect_queue=[list(symbols), ["rsi"]], button_values={"백테스트 실행": True})
    screen.session_state[app.BACKTEST_COLLECTION_PERIOD_KEY] = PERIOD
    monkeypatch.setattr(app, "st", screen)
    monkeypatch.setattr(app, "_load_backtest_inputs", lambda service, symbol: sources[symbol])
    monkeypatch.setattr(app, "_render_backtest_history_panel", lambda service: None)
    original = app.DEFAULT_BACKTEST_RUNNER.run
    calls = []

    def run(symbol, rows):
        calls.append(symbol)
        return original(symbol, rows)

    monkeypatch.setattr(app.DEFAULT_BACKTEST_RUNNER, "run", run)
    snapshot = SimpleNamespace(raw_previews=[], processed_previews=[])
    app.render_backtest_tab(snapshot, service, symbol_lookup=lookup)
    assert calls == list(symbols)
    frozen = copy.deepcopy(screen.session_state[app.BACKTEST_RESULTS_KEY]["summary_frame"])
    screen.button_values.clear()
    screen.multiselect_queue = [list(symbols), ["rsi"]]
    screen.session_state[app.BACKTEST_COLLECTION_PERIOD_KEY] = (date(2024, 1, 1), date(2024, 1, 2))
    sources["005930"] = loaded("005930", frame=indicators().assign(date=["2030-01-03", "2030-01-01", "2030-01-02"]))
    screen.markdown_calls.clear()
    app.render_backtest_tab(snapshot, service, symbol_lookup=lookup)
    assert calls == list(symbols)
    pd.testing.assert_frame_equal(screen.session_state[app.BACKTEST_RESULTS_KEY]["summary_frame"], frozen)
    texts = [Text(note).value for note in notes(screen)]
    assert len(texts) == 4
    assert any("2030-01-01" in t and "2024-01-01" in t for t in texts)
    result_text = texts[-2:]
    assert all("2025-05-04" in t and "2026-05-04" in t and "365일" in t for t in result_text)
    assert all("2030" not in t and "2024" not in t for t in result_text)


def canonical(row):
    result = {}
    for field in FIELDS:
        value = row[field]
        if value is None or pd.isna(value) or value == "":
            result[field] = None
        elif field in {"input_row_count", "input_excluded_rows", "prepare_lookback_days"}:
            result[field] = int(value)
        else:
            result[field] = str(value)
    return result


@pytest.mark.parametrize("kind", ["csv", "sqlite"])
def test_actual_history_roundtrip_keeps_all_nine_fields_without_adapter_or_runner(monkeypatch, tmp_path, kind):
    strategies = ["rsi", "golden-cross"]
    result = app._execute_backtests(items(), strategies, {"005930": loaded()},
        combination_settings=resolve_backtest_combination_settings(strategies), preparation_period=PERIOD)
    summary = result["summary_frame"]
    expected = {row.strategy_id: canonical(row) for _, row in summary.iterrows()}
    if kind == "sqlite":
        url = f"sqlite:///{tmp_path/'qa-history.db'}"
        init_test_db(url)
        storage = DbFrameStorage(url)
        service = DashboardDataService(dataset_storage=storage)
    else:
        storage = CsvStorage(tmp_path/"processed")
        service = DashboardDataService(raw_root=tmp_path/"raw", processed_root=storage.root_dir)
    # Explicit consumer persistence only: product dashboard execution did not save.
    storage.save("backtest_summaries", "005930_20261105T010203Z_backtest_summary.csv", summary)
    monkeypatch.setattr(service, "_load_symbol_name_map", lambda: {})

    def forbidden(*args, **kwargs):
        pytest.fail("history metadata was reconstructed by live execution")

    monkeypatch.setattr(app.DEFAULT_BACKTEST_RUNNER, "run", forbidden)
    monkeypatch.setattr(app.DEFAULT_BACKTEST_ADAPTER_REGISTRY, "build_signal_rows", forbidden)
    entries, _ = app._load_backtest_history_entries(service)
    actual = {}
    screen = Screen()
    monkeypatch.setattr(app, "st", screen)
    screen.session_state[app.BACKTEST_COLLECTION_PERIOD_KEY] = (date(2020,1,1),date(2030,1,1))
    for entry in entries:
        bundle, messages = app._load_backtest_history_result(service, entry)
        assert bundle is not None and not messages
        for _, row in bundle["summary_frame"].iterrows():
            actual[row.strategy_id] = canonical(row)
        app._render_results_panel(service, bundle)
    assert actual == expected
    assert len(notes(screen)) == 3
    assert all("365일" in Text(note).value and "2020" not in Text(note).value for note in notes(screen))


@pytest.mark.parametrize("case,patch,expected", [
    ("legacy", None, "기록 없음"),
    ("partial", {"input_end_date": None}, "확인 불가"),
    ("missing-count", {"input_row_count": None}, "확인 불가"),
    ("fraction-count", {"input_row_count": 3.5}, "확인 불가"),
    ("bool-count", {"input_row_count": True}, "확인 불가"),
    ("integer-record", {"input_start_date": 20260504, "input_end_date": 20260506,
        "input_row_count": "3", "prepare_selection_start_date": 20250504,
        "prepare_selection_end_date": 20260504, "prepare_lookback_days": "365"}, "유효 고유 일봉 3개"),
    ("empty", {"input_range_status": "empty", "input_row_count": 0,
        "input_start_date": None, "input_end_date": None}, "유효한 입력 일봉 0개"),
    ("reason", {"input_range_status": "unavailable",
        "input_range_reason": '<img src=x onerror="alert(1)">'}, '<img src=x onerror="alert(1)">'),
])
def test_real_result_renderer_handles_legacy_partial_and_scalar_metadata_without_inference(monkeypatch, tmp_path, case, patch, expected):
    result = app._execute_backtests(items(), ["rsi"], {"005930": loaded()}, preparation_period=PERIOD)
    if patch is None:
        result["summary_frame"] = result["summary_frame"].drop(columns=list(FIELDS))
    else:
        for field, value in patch.items():
            # A heterogeneous row models a partially written legacy record.
            result["summary_frame"][field] = pd.Series([value], dtype=object)
    screen = Screen()
    monkeypatch.setattr(app, "st", screen)
    screen.session_state[app.BACKTEST_COLLECTION_PERIOD_KEY] = (date(2020,1,1),date(2030,1,1))
    service = DashboardDataService(raw_root=tmp_path/"raw", processed_root=tmp_path/"processed")
    app._render_results_panel(service, result)
    note = notes(screen)[0]
    parsed = Text(note)
    assert expected in parsed.value and "2020" not in parsed.value and "2030" not in parsed.value
    assert set(parsed.tags) <= {"div", "p", "strong", "br"}
    assert "\n" not in note and "overflow-wrap:anywhere" in note
    if patch is None:
        assert "2025-05-04" not in parsed.value and "2026-05-06" not in parsed.value


def test_real_source_loader_budget_then_memory_preview_and_renderer_are_read_only(monkeypatch, tmp_path):
    url = f"sqlite:///{tmp_path/'qa-inputs.db'}"
    init_test_db(url)
    storage = DbFrameStorage(url)
    frame = indicators().reset_index(drop=True)
    for dataset, content in [
        ("daily_prices_indicators", frame),
        ("daily_prices", frame[["date", "close"]]),
        ("investor_daily", frame[["date"]].assign(foreign_net_qty=1, institutional_net_qty=2)),
        ("golden_cross_signals", frame[["date", "close"]].assign(signal="hold")),
    ]:
        storage.save(dataset, f"005930_{dataset}.csv", content)
    service = DashboardDataService(dataset_storage=storage)
    engine = storage.repository.session_factory.kw["bind"]
    statements = []

    def observe(conn, cursor, statement, parameters, context, executemany):
        statements.append(statement)

    event.listen(engine, "before_cursor_execute", observe)
    try:
        memory = {"005930": app._load_backtest_inputs(service, "005930")}
        assert len(statements) == 8 and all(s.lstrip().upper().startswith("SELECT") for s in statements)
        statements.clear()

        def forbidden(*args, **kwargs):
            pytest.fail("preview performed an execution or write")

        monkeypatch.setattr(storage, "save", forbidden)
        monkeypatch.setattr(app.DEFAULT_BACKTEST_RUNNER, "run", forbidden)
        screen = Screen()
        monkeypatch.setattr(app, "st", screen)
        payload = app._build_readiness_payload(selected_items=items(), selected_strategy_ids=["rsi", "golden-cross"],
            loaded_inputs=memory, strategy_labels={}, preparation_period=PERIOD,
            combination_settings=resolve_backtest_combination_settings(["rsi","golden-cross"]))
        app._render_readiness_panel(payload)
        assert statements == []
        assert len(notes(screen)) == 3
        assert all("현재 메모리 입력" in t or "실제 입력" in t for t in screen.markdown_calls if "#### 실제 입력" in t)
    finally:
        event.remove(engine, "before_cursor_execute", observe)


def test_parameter_failure_clears_stale_bundle_without_collecting(monkeypatch):
    screen = Screen()
    sentinel = {"summary_frame": pd.DataFrame({"stale":[1]})}
    screen.session_state[app.BACKTEST_RESULTS_KEY] = sentinel
    monkeypatch.setattr(app, "st", screen)
    source = loaded()
    app._run_backtest_action(selected_items=items(), selected_strategy_ids=["golden-cross"],
        loaded_inputs={"005930":source}, strategy_parameters={"golden-cross":{"short_window":0,"long_window":3}},
        combination_settings=None, preparation_period=PERIOD)
    assert app.BACKTEST_RESULTS_KEY not in screen.session_state
    assert screen.session_state["action_message_type"] == "error"


def test_empty_parameter_map_preserves_defaults_without_inventing_selection(monkeypatch):
    screen = Screen()
    monkeypatch.setattr(app, "st", screen)
    app._run_backtest_action(selected_items=items(), selected_strategy_ids=["golden-cross"],
        loaded_inputs={"005930":loaded()}, strategy_parameters={}, combination_settings=None)
    assert screen.session_state["action_message_type"] == "success"
    record = screen.session_state[app.BACKTEST_RESULTS_KEY]["summary_frame"].iloc[0]
    assert record["input_row_count"] == 3
    assert record["prepare_selection_start_date"] is None
    assert record["prepare_selection_end_date"] is None
    assert record["prepare_lookback_days"] is None


def test_real_adapter_runner_keep_local_day_instead_of_utc_day():
    frame = indicators().iloc[:2].copy()
    frame["date"] = [pd.Timestamp("2026-05-04 23:30:00-09:00"), pd.Timestamp("2026-05-05 23:30:00-09:00")]
    source = loaded(frame=frame)
    original = copy.deepcopy(frame)
    preview = app._build_readiness_payload(selected_items=items(), selected_strategy_ids=["rsi"],
        loaded_inputs={"005930":source}, strategy_labels={}, preparation_period=PERIOD)
    result = app._execute_backtests(items(), ["rsi"], {"005930":source}, preparation_period=PERIOD)
    for row in [preview["input_ranges"].iloc[0], result["summary_frame"].iloc[0]]:
        assert row["input_start_date"] == "2026-05-04" and row["input_end_date"] == "2026-05-05"
        assert row["input_row_count"] == 2
    pd.testing.assert_frame_equal(frame, original)
    assert frame.attrs == original.attrs


@pytest.mark.parametrize("kind", ["empty", "duplicate"])
def test_preview_gate_and_stale_result_boundary_with_real_invalid_sources(monkeypatch, kind):
    frame = indicators()
    frame = frame.iloc[:0].copy() if kind == "empty" else pd.concat([frame, frame.iloc[:1]], ignore_index=True)
    source = loaded(frame=frame)
    expected_gate = app.check_backtest_readiness(["rsi"], source.readiness_datasets()).ready_to_run
    screen = Screen()
    screen.session_state[app.BACKTEST_RESULTS_KEY] = {"stale":True}
    monkeypatch.setattr(app, "st", screen)
    monkeypatch.setattr(app.DEFAULT_BACKTEST_RUNNER, "run", lambda *a, **k: pytest.fail("invalid preview reached runner"))
    payload = app._build_readiness_payload(selected_items=items(), selected_strategy_ids=["rsi"],
        loaded_inputs={"005930":source}, strategy_labels={}, preparation_period=PERIOD)
    assert payload["can_run"] == expected_gate
    assert payload["input_ranges"].iloc[0]["input_range_status"] == "unavailable"
    app._render_readiness_panel(payload)
    assert "확인 불가" in Text(notes(screen)[0]).value
    app._run_backtest_action(selected_items=items(), selected_strategy_ids=["rsi"],
        loaded_inputs={"005930":source}, strategy_parameters={"rsi":{"buy_threshold":30,"sell_threshold":70}},
        combination_settings=None, preparation_period=PERIOD)
    assert app.BACKTEST_RESULTS_KEY not in screen.session_state
