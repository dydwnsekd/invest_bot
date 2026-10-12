from __future__ import annotations

from copy import deepcopy
from datetime import date, datetime, timedelta, timezone
from math import nextafter, inf
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import pytest

from invest_bot.backtest import DEFAULT_BACKTEST_RUNNER, GOLDEN_CROSS_SIGNALS, build_daily_mark_to_market_equity_curve, build_strategy_signal_rows
from invest_bot.backtest.persistence import input_sources_from_frame
from invest_bot.backtest.strategy_registry import DAILY_PRICES_INDICATORS
from invest_bot.config.settings import AppSettings
from invest_bot.dashboard import streamlit_backtest as ui
from invest_bot.db.frame_storage import DbFrameStorage
from invest_bot.jobs import generate_backtest as job
from invest_bot.jobs.generate_backtest import BacktestRequest, GoldenCrossBacktestGenerator
from invest_bot.jobs.run_backtest import run_backtest_for_symbol
from invest_bot.market.storage import CsvStorage, SavedDataset
from tests.test_streamlit_backtest import _FakeStreamlit


SYMBOL = "005930"
SIGNAL_FILE = "005930_declared.csv"
CURRENT_FILE = "005930_selected.csv"


@pytest.fixture(autouse=True)
def deny_operational_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    def denied(*_args: object, **_kwargs: object) -> None:
        pytest.fail("independent G04 fixture attempted operational config/DB/API work")
    monkeypatch.setattr(AppSettings, "from_file", denied)
    monkeypatch.setattr(DbFrameStorage, "from_settings", denied)
    for name in ("collect_market_data_for_symbols", "generate_indicators_for_symbol", "generate_golden_cross_signals_for_symbol"):
        monkeypatch.setattr(ui, name, denied)


def _saved() -> pd.DataFrame:
    frame = pd.DataFrame({
        "date": ["2026-04-01", "2026-04-02", "2026-04-03", "2026-04-06"],
        "close": [95.0, 100.0, 50.0, 120.0],
        "signal": ["BUY", "hold", "hold", "SELL"],
        "signal_reason": ["archived buy", "dip hold", "deep dip", "archived sell"],
    })
    frame.attrs = {"fixture": {"immutable": ["saved", 1]}}
    return frame


def _current() -> pd.DataFrame:
    frame = _saved()[["date", "close"]].copy()
    return frame.assign(ma_5=[94.0, 99.0, 50.0, 121.0], ma_20=[96.0, 98.0, 60.0, 110.0],
                        rsi_14=[50.0] * 4, momentum_20=[0.0] * 4)


def _build(saved: pd.DataFrame, current: pd.DataFrame, parameters: dict | None = None) -> pd.DataFrame:
    return build_strategy_signal_rows("golden-cross", {GOLDEN_CROSS_SIGNALS: saved, DAILY_PRICES_INDICATORS: current}, parameters=parameters)


def _unchanged(frame: pd.DataFrame, before: pd.DataFrame, attrs: dict) -> None:
    pd.testing.assert_frame_equal(frame, before)
    assert frame.attrs == attrs


def _bad_saved(kind: str) -> pd.DataFrame:
    saved = _saved()
    if kind == "old":
        saved["date"] = ["2026-03-25", "2026-03-26", "2026-03-27", "2026-03-30"]
    elif kind == "internal-missing":
        saved = saved.iloc[[0, 1, 3]].copy()
    elif kind in {"internal-extra", "outside-extra"}:
        row = pd.DataFrame({"date": ["2026-04-04" if kind == "internal-extra" else "2026-04-07"], "close": [110.0], "signal": ["hold"]})
        saved = pd.concat([saved, row], ignore_index=True)
    elif kind == "same-range-swapped-day":
        saved.loc[2, "date"] = "2026-04-04"
    elif kind == "ulp-close":
        saved.loc[1, "close"] = nextafter(100.0, inf)
    else:
        raise AssertionError(kind)
    return saved


@pytest.mark.parametrize("kind", ["old", "internal-missing", "internal-extra", "outside-extra", "same-range-swapped-day", "ulp-close"])
@pytest.mark.parametrize("parameters", [None, {"short_window": "5", "long_window": 20.0}])
def test_adapter_rejects_entire_date_set_or_exact_price_difference(kind: str, parameters: dict | None) -> None:
    saved, current = _bad_saved(kind), _current()
    before_saved, before_current = saved.copy(deep=True), current.copy(deep=True)
    attrs_saved, attrs_current = deepcopy(saved.attrs), deepcopy(current.attrs)
    with pytest.raises(ValueError, match="close mismatch" if kind == "ulp-close" else "trading dates") as error:
        _build(saved, current, parameters)
    assert GOLDEN_CROSS_SIGNALS in str(error.value)
    assert DAILY_PRICES_INDICATORS in str(error.value)
    _unchanged(saved, before_saved, attrs_saved)
    _unchanged(current, before_current, attrs_current)


@pytest.mark.parametrize("invalid", [None, float("nan"), inf, -inf, 0, -10, "", "NaN", True, complex(100, 0)])
def test_matching_invalid_prices_on_both_sides_are_rejected(invalid: object) -> None:
    saved, current = _saved(), _current()
    for frame in (saved, current):
        frame["close"] = frame["close"].astype(object)
        frame.iloc[1, frame.columns.get_loc("close")] = invalid
    with pytest.raises(ValueError, match="invalid close.*2026-04-02"):
        _build(saved, current)


@pytest.mark.parametrize("invalid", [pd.NaT, None, "", "not-a-date", "2026-02-30"])
def test_matching_invalid_dates_on_both_sides_cannot_fake_alignment(invalid: object) -> None:
    saved, current = _saved(), _current()
    for frame in (saved, current):
        frame["date"] = frame["date"].astype(object)
        frame.iloc[1, frame.columns.get_loc("date")] = invalid
    with pytest.raises(ValueError, match="invalid trading dates"):
        _build(saved, current)


@pytest.mark.parametrize("source", ["saved", "current"])
def test_duplicate_rejection_precedes_bad_price_and_missing_day_filter(source: str) -> None:
    saved, current = _saved(), _current()
    frame = saved if source == "saved" else current
    frame.loc[1, "date"] = "2026-04-01 15:30:00"
    frame.loc[1, "close"] = float("nan")
    frame.index = [4, 4, 4, 4]
    with pytest.raises(ValueError, match="duplicate trading dates: 2026-04-01"):
        _build(saved, current)


def _represented_dates(kind: str) -> list[object]:
    if kind == "string":
        return ["2026-04-01", "2026-04-02", "2026-04-03", "2026-04-06"]
    if kind == "date":
        return [date(2026, 4, day) for day in (1, 2, 3, 6)]
    if kind == "datetime":
        return [datetime(2026, 4, day) for day in (1, 2, 3, 6)]
    if kind == "timestamp":
        return [pd.Timestamp(value) for value in _represented_dates("string")]
    offsets = ["2026-04-01 00:30:00+09:00", "2026-04-02 23:30:00-04:00", "2026-04-03 12:00:00+01:00", "2026-04-06 09:00:00+09:00"]
    if kind == "offset-strings":
        return offsets
    if kind == "offset-timestamps":
        return [pd.Timestamp(value) for value in offsets]
    return [date(2026, 4, 1), datetime(2026, 4, 2, 23, 30, tzinfo=timezone(timedelta(hours=-4))),
            pd.Timestamp(offsets[2]), offsets[3]]


@pytest.mark.parametrize("kind", ["string", "date", "datetime", "timestamp", "offset-strings", "offset-timestamps", "mixed"])
def test_row_price_association_and_real_runner_preserved_with_repeated_indexes(kind: str) -> None:
    saved, current = _saved(), _current()
    saved["date"] = pd.Series(_represented_dates(kind), dtype=object)
    current["date"] = pd.Series(_represented_dates("mixed"), dtype=object)
    current["close"] = ["95.00", "1e2", "50", "120.0"]
    saved, current = saved.iloc[[2, 0, 3, 1]].copy(), current.iloc[[3, 1, 0, 2]].copy()
    saved.index = [8, 8, -2, 8]
    current.index = pd.MultiIndex.from_tuples([("a", 1), ("a", 1), ("b", 3), ("a", 1)])
    before_saved, before_current = saved.copy(deep=True), current.copy(deep=True)
    attrs_saved, attrs_current = deepcopy(saved.attrs), deepcopy(current.attrs)
    rows = _build(saved, current)
    assert rows["date"].map(lambda value: value.date()).tolist() == [date(2026, 4, day) for day in (1, 2, 3, 6)]
    assert rows["close"].tolist() == [95.0, 100.0, 50.0, 120.0]
    assert rows["signal_reason"].tolist() == _saved()["signal_reason"].tolist()
    assert rows["signal"].tolist() == ["buy", "hold", "hold", "sell"]
    result = DEFAULT_BACKTEST_RUNNER.run(SYMBOL, rows)
    curve = build_daily_mark_to_market_equity_curve(rows, result.trades, initial_equity=1.0)
    assert result.summary.iloc[0]["final_equity"] == pytest.approx(1.2)
    assert result.summary.iloc[0]["max_drawdown_pct"] == pytest.approx(50.0)
    assert result.trades.iloc[0]["entry_price"] == 100.0
    assert result.trades.iloc[0]["exit_reason"] == "sell_signal_final_close"
    assert curve["equity"].tolist() == [1.0, 1.0, 0.5, 1.2]
    _unchanged(saved, before_saved, attrs_saved)
    _unchanged(current, before_current, attrs_current)


@pytest.mark.parametrize("parameters", [{"short_window": 2, "long_window": 3}, {"short_window": 3, "long_window": 7}])
def test_custom_windows_do_not_inspect_unused_corrupt_saved_signals(parameters: dict) -> None:
    current = _current()
    corrupt = _saved().assign(date="invalid", close=float("nan"))
    expected = build_strategy_signal_rows("golden-cross", {DAILY_PRICES_INDICATORS: current}, parameters=parameters)
    pd.testing.assert_frame_equal(_build(corrupt, current, parameters), expected)


@pytest.mark.parametrize("strategy", ["rsi", "momentum"])
def test_other_strategies_ignore_saved_golden_cross_mismatch(strategy: str) -> None:
    current = _current()
    expected = build_strategy_signal_rows(strategy, {DAILY_PRICES_INDICATORS: current})
    actual = build_strategy_signal_rows(strategy, {DAILY_PRICES_INDICATORS: current, GOLDEN_CROSS_SIGNALS: _bad_saved("old")})
    pd.testing.assert_frame_equal(actual, expected)


class _MemoryStorage:
    def __init__(self, frames: dict, latest: dict | None = None) -> None:
        self.frames = frames
        self.latest = latest if latest is not None else {GOLDEN_CROSS_SIGNALS: SIGNAL_FILE, DAILY_PRICES_INDICATORS: CURRENT_FILE}
        self.loads: list[tuple[str, str]] = []
        self.lookups: list[tuple[str, str]] = []
        self.saved: list[tuple[str, str, pd.DataFrame]] = []

    def latest_filename(self, dataset: str, symbol: str) -> str | None:
        self.lookups.append((dataset, symbol))
        assert symbol == SYMBOL
        return self.latest.get(dataset)

    def load(self, dataset: str, filename: str) -> pd.DataFrame:
        self.loads.append((dataset, filename))
        value = self.frames.get((dataset, filename), FileNotFoundError(filename))
        if isinstance(value, Exception):
            raise value
        return value

    def save(self, dataset: str, filename: str, frame: pd.DataFrame) -> SavedDataset:
        self.saved.append((dataset, filename, frame.copy(deep=True)))
        return SavedDataset(dataset, Path("/memory-only") / filename, len(frame))


def _forbid_downstream(monkeypatch: pytest.MonkeyPatch, owner: object) -> list[str]:
    calls: list[str] = []
    def forbidden(name: str):
        def callback(*_args: object, **_kwargs: object) -> None:
            calls.append(name)
            raise RuntimeError(f"QA forbidden downstream {name}")
        return callback
    monkeypatch.setattr(DEFAULT_BACKTEST_RUNNER, "run", forbidden("runner"))
    monkeypatch.setattr(owner, "build_context", forbidden("context"))
    return calls


@pytest.mark.parametrize("explicit", [False, True])
@pytest.mark.parametrize("problem", ["missing", "empty", "zero-byte", "malformed", "internal-date", "ulp-close", "invalid-date", "invalid-close"])
def test_generator_selected_bad_indicator_fails_before_runner_context_or_save(
    monkeypatch: pytest.MonkeyPatch, explicit: bool, problem: str
) -> None:
    current: pd.DataFrame | Exception = _current()
    if problem == "empty":
        current = current.iloc[:0]
    elif problem == "zero-byte":
        current = pd.errors.EmptyDataError("synthetic zero-byte")
    elif problem == "malformed":
        current = pd.DataFrame({"date": ["2026-04-01"], "close": [95.0]})
    elif problem == "internal-date":
        current.loc[2, "date"] = "2026-04-04"
    elif problem == "ulp-close":
        current.loc[1, "close"] = nextafter(100.0, inf)
    elif problem == "invalid-date":
        current.loc[1, "date"] = "invalid"
    elif problem == "invalid-close":
        current.loc[1, "close"] = float("nan")
    frames = {(GOLDEN_CROSS_SIGNALS, SIGNAL_FILE): _saved(), (DAILY_PRICES_INDICATORS, "005930_old_good.csv"): _current()}
    if problem != "missing":
        frames[(DAILY_PRICES_INDICATORS, CURRENT_FILE)] = current
    storage = _MemoryStorage(frames)
    generator = GoldenCrossBacktestGenerator(processed_storage=storage)
    calls = _forbid_downstream(monkeypatch, job)
    with pytest.raises((ValueError, FileNotFoundError)):
        if explicit:
            generator.load_signal_frame(BacktestRequest(SYMBOL, SIGNAL_FILE, indicator_filename=CURRENT_FILE))
        else:
            run_backtest_for_symbol(SYMBOL, generator=generator)
    assert calls == []
    assert storage.saved == []
    assert generator._contexts_by_key == {}
    assert storage.loads == [(GOLDEN_CROSS_SIGNALS, SIGNAL_FILE), (DAILY_PRICES_INDICATORS, CURRENT_FILE)]
    assert (DAILY_PRICES_INDICATORS, SYMBOL) in storage.lookups if not explicit else storage.lookups == []


@pytest.mark.parametrize("explicit", [False, True])
def test_generator_reads_actual_selected_file_and_records_it_not_unused_latest(explicit: bool) -> None:
    storage = _MemoryStorage({(GOLDEN_CROSS_SIGNALS, SIGNAL_FILE): _saved(),
                              (DAILY_PRICES_INDICATORS, CURRENT_FILE): _current(),
                              (DAILY_PRICES_INDICATORS, "005930_unselected_bad.csv"): _current().iloc[:1]})
    if explicit:
        storage.latest[DAILY_PRICES_INDICATORS] = "005930_unselected_bad.csv"
    generator = GoldenCrossBacktestGenerator(processed_storage=storage)
    loaded = generator.load_signal_frame(BacktestRequest(SYMBOL, SIGNAL_FILE, indicator_filename=CURRENT_FILE if explicit else None))
    assert input_sources_from_frame(loaded).indicator_source_filename == CURRENT_FILE
    assert storage.loads == [(GOLDEN_CROSS_SIGNALS, SIGNAL_FILE), (DAILY_PRICES_INDICATORS, CURRENT_FILE)]
    result = generator.run_backtest(SYMBOL, loaded)
    assert result.summary.iloc[0]["indicator_source_filename"] == CURRENT_FILE
    assert result.summary.iloc[0]["signal_source_filename"] == SIGNAL_FILE
    assert result.summary.iloc[0]["final_equity"] == pytest.approx(1.2)


@pytest.mark.parametrize("kind", ["duplicate", "malformed"])
def test_bad_declared_signal_blocks_before_any_indicator_load(monkeypatch: pytest.MonkeyPatch, kind: str) -> None:
    saved = _saved()
    if kind == "duplicate":
        saved.loc[1, "date"] = saved.loc[0, "date"]
    else:
        saved = saved.drop(columns="signal")
    storage = _MemoryStorage({(GOLDEN_CROSS_SIGNALS, SIGNAL_FILE): saved})
    generator = GoldenCrossBacktestGenerator(processed_storage=storage)
    calls = _forbid_downstream(monkeypatch, job)
    with pytest.raises(ValueError, match="duplicate trading dates" if kind == "duplicate" else "missing columns"):
        run_backtest_for_symbol(SYMBOL, generator=generator)
    assert storage.loads == [(GOLDEN_CROSS_SIGNALS, SIGNAL_FILE)]
    assert (DAILY_PRICES_INDICATORS, SYMBOL) not in storage.lookups
    assert calls == [] and storage.saved == [] and generator._contexts_by_key == {}


@pytest.mark.parametrize("kind", ["normal", "header-empty", "zero-byte"])
def test_saved_only_compatibility_has_no_indicator_provenance(kind: str) -> None:
    saved: pd.DataFrame | Exception = _saved() if kind == "normal" else _saved().iloc[:0]
    if kind == "zero-byte":
        saved = pd.errors.EmptyDataError("synthetic empty signal file")
    storage = _MemoryStorage({(GOLDEN_CROSS_SIGNALS, SIGNAL_FILE): saved}, latest={GOLDEN_CROSS_SIGNALS: SIGNAL_FILE})
    generator = GoldenCrossBacktestGenerator(processed_storage=storage)
    result = run_backtest_for_symbol(SYMBOL, generator=generator)
    assert result["signal_rows"] == (4 if kind == "normal" else 0)
    summary = next(frame for dataset, _name, frame in storage.saved if dataset == "backtest_summaries")
    assert summary.iloc[0]["indicator_source_dataset"] is None
    assert summary.iloc[0]["indicator_source_filename"] is None
    assert storage.loads == [(GOLDEN_CROSS_SIGNALS, SIGNAL_FILE)]


@pytest.mark.parametrize("mismatch", [False, True])
def test_real_temporary_csv_cli_respects_current_prices_and_blocks_output_on_mismatch(tmp_path: Path, mismatch: bool) -> None:
    storage = CsvStorage(tmp_path / "synthetic-csv")
    saved = _saved()
    if mismatch:
        saved.loc[1, "close"] = 100.00000001
    storage.save(GOLDEN_CROSS_SIGNALS, SIGNAL_FILE, saved)
    storage.save(DAILY_PRICES_INDICATORS, CURRENT_FILE, _current())
    generator = GoldenCrossBacktestGenerator(processed_storage=storage)
    if mismatch:
        with pytest.raises(ValueError, match="close mismatch"):
            run_backtest_for_symbol(SYMBOL, generator=generator)
        assert not (storage.root_dir / "backtest_summaries").exists()
        assert not (storage.root_dir / "backtest_trades").exists()
        assert generator._contexts_by_key == {}
    else:
        result = run_backtest_for_symbol(SYMBOL, generator=generator)
        summary = pd.read_csv(result["summary_saved_path"])
        assert summary.iloc[0]["indicator_source_filename"] == CURRENT_FILE
        assert summary.iloc[0]["final_equity"] == pytest.approx(1.2)
        assert pd.read_csv(result["trades_saved_path"]).iloc[0]["entry_price"] == 100.0


def _inputs(saved: pd.DataFrame | None, filename: str | None = SIGNAL_FILE) -> ui.LoadedBacktestInputs:
    return ui.LoadedBacktestInputs(
        SYMBOL, ui.LoadedDataset(DAILY_PRICES_INDICATORS, CURRENT_FILE, _current()),
        ui.LoadedDataset("investor_daily", None, None), ui.LoadedDataset("daily_prices", None, None),
        ui.LoadedDataset(GOLDEN_CROSS_SIGNALS, filename, saved),
    )


def _action(inputs: ui.LoadedBacktestInputs, parameters: dict | None = None) -> None:
    ui._run_backtest_action(selected_items=[ui.ResolvedSymbol(SYMBOL, SYMBOL, "QA memory")],
                            selected_strategy_ids=["golden-cross"], loaded_inputs={SYMBOL: inputs},
                            strategy_parameters={"golden-cross": parameters} if parameters else {}, combination_settings=None)


@pytest.mark.parametrize("kind", ["internal-missing", "ulp-close"])
def test_real_ui_action_blocks_before_runner_context_and_clears_stale_bundle(monkeypatch: pytest.MonkeyPatch, kind: str) -> None:
    fake = _FakeStreamlit()
    fake.session_state[ui.BACKTEST_RESULTS_KEY] = {"previous_run": "must disappear"}
    monkeypatch.setattr(ui, "st", fake)
    calls = _forbid_downstream(monkeypatch, ui)
    _action(_inputs(_bad_saved(kind)))
    assert calls == []
    assert ui.BACKTEST_RESULTS_KEY not in fake.session_state
    assert fake.session_state["action_message_type"] == "error"
    reason = fake.session_state[ui.BACKTEST_BLOCKED_REASONS_KEY][0]
    assert GOLDEN_CROSS_SIGNALS in reason and DAILY_PRICES_INDICATORS in reason
    assert "close mismatch" in reason if kind == "ulp-close" else "trading dates" in reason


@pytest.mark.parametrize("custom", [False, True])
def test_real_ui_execution_and_success_action_match_actual_signal_source(monkeypatch: pytest.MonkeyPatch, custom: bool) -> None:
    fake = _FakeStreamlit()
    fake.session_state[ui.BACKTEST_RESULTS_KEY] = {"previous_run": True}
    fake.session_state[ui.BACKTEST_BLOCKED_REASONS_KEY] = ("old failure",)
    monkeypatch.setattr(ui, "st", fake)
    parameters = {"short_window": 2, "long_window": 3} if custom else None
    inputs = _inputs(_bad_saved("old") if custom else _saved())
    _action(inputs, parameters)
    assert fake.session_state["action_message_type"] == "success"
    assert fake.session_state[ui.BACKTEST_BLOCKED_REASONS_KEY] == ()
    bundle = fake.session_state[ui.BACKTEST_RESULTS_KEY]
    assert "previous_run" not in bundle
    summary = bundle["summary_frame"].iloc[0]
    assert summary["signal_source_filename"] == (None if custom else SIGNAL_FILE)
    expected_rows = build_strategy_signal_rows("golden-cross", inputs.adapter_datasets(), parameters=parameters)
    expected = DEFAULT_BACKTEST_RUNNER.run(SYMBOL, expected_rows)
    assert summary["final_equity"] == expected.summary.iloc[0]["final_equity"]
    assert summary["max_drawdown_pct"] == expected.summary.iloc[0]["max_drawdown_pct"]
    assert bundle["daily_equity_frame"]["equity"].tolist() == build_daily_mark_to_market_equity_curve(expected_rows, expected.trades)["equity"].tolist()


@pytest.mark.parametrize("kind", ["filename-missing", "frame-missing", "columns-missing"])
def test_ui_source_metadata_requires_filename_frame_and_columns(kind: str) -> None:
    inputs = _inputs(None if kind == "frame-missing" else (_saved().drop(columns="signal") if kind == "columns-missing" else _saved()),
                     filename=None if kind == "filename-missing" else SIGNAL_FILE)
    bundle = ui._execute_backtests([ui.ResolvedSymbol(SYMBOL, SYMBOL, "QA")], ["golden-cross"], {SYMBOL: inputs})
    assert bundle["summary_frame"].iloc[0]["signal_source_filename"] is None
    assert bundle["summary_frame"].iloc[0]["signal_source_dataset"] is None


@pytest.mark.parametrize("mismatch", [False, True])
def test_real_render_uses_memory_inputs_and_shows_alignment_recovery_caption(monkeypatch: pytest.MonkeyPatch, mismatch: bool) -> None:
    fake = _FakeStreamlit(multiselect_queue=[[SYMBOL], ["golden-cross"]], button_values={"백테스트 실행": True})
    fake.session_state[ui.BACKTEST_RESULTS_KEY] = {"previous_result": True}
    inputs = _inputs(_bad_saved("ulp-close") if mismatch else _saved())
    monkeypatch.setattr(ui, "st", fake)
    monkeypatch.setattr(ui, "_load_backtest_inputs", lambda _service, _symbol: inputs)
    def forbidden_io(*_args: object, **_kwargs: object) -> None:
        pytest.fail("fake UI attempted file/DB IO")
    service = SimpleNamespace(list_backtest_history_previews=lambda _dataset: [],
                              load_preview_frame=forbidden_io, get_dataset_storage=forbidden_io)
    ui.render_backtest_tab(SimpleNamespace(raw_previews=[], processed_previews=[]), service,
                          symbol_lookup=SimpleNamespace(list_entries=lambda: [ui.SymbolEntry(SYMBOL, "QA memory")]))
    assert any("거래일·종가" in text and "준비 실행" in text for text in fake.caption_calls)
    if mismatch:
        assert ui.BACKTEST_RESULTS_KEY not in fake.session_state
        assert "close mismatch" in fake.session_state[ui.BACKTEST_BLOCKED_REASONS_KEY][0]
        assert fake.session_state["action_message_type"] == "error"
        assert "#### 거래 로그" not in fake.markdown_calls
    else:
        assert fake.session_state["action_message_type"] == "success"
        assert fake.session_state[ui.BACKTEST_RESULTS_KEY]["summary_frame"].iloc[0]["signal_source_filename"] == SIGNAL_FILE
        assert "#### 거래 로그" in fake.markdown_calls
