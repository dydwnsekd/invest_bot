from __future__ import annotations

from datetime import date, datetime
from pathlib import Path

import pandas as pd
import pytest

from invest_bot.backtest import DEFAULT_BACKTEST_RUNNER, GOLDEN_CROSS_SIGNALS, build_strategy_signal_rows
from invest_bot.backtest.strategy_registry import DAILY_PRICES_INDICATORS
from invest_bot.jobs.generate_backtest import BacktestRequest, GoldenCrossBacktestGenerator
from invest_bot.jobs.run_backtest import run_backtest_for_symbol
from invest_bot.market.storage import SavedDataset


SYMBOL = "005930"
SIGNAL_FILE = "005930_saved.csv"
INDICATOR_FILE = "005930_current.csv"


def _signals() -> pd.DataFrame:
    return pd.DataFrame({"date": ["2026-04-01", "2026-04-02", "2026-04-03"],
                         "close": [100.0, 101.0, 102.0], "signal": ["buy", "hold", "sell"],
                         "signal_reason": ["saved entry", "saved hold", "saved exit"]})


def _indicators(signals: pd.DataFrame | None = None) -> pd.DataFrame:
    frame = (signals if signals is not None else _signals()).loc[:, ["date", "close"]].copy()
    return frame.assign(ma_5=100.0, ma_20=100.0)


def _build(saved: pd.DataFrame, current: pd.DataFrame, **kwargs: object) -> pd.DataFrame:
    return build_strategy_signal_rows("golden-cross", {GOLDEN_CROSS_SIGNALS: saved, DAILY_PRICES_INDICATORS: current}, **kwargs)


@pytest.mark.parametrize(("dates", "missing", "extra"), [
    (["2026-04-01", "2026-04-02"], "2026-04-03", None),
    (["2026-03-31", "2026-04-01", "2026-04-02"], "2026-04-03", "2026-03-31"),
    (["2026-04-02", "2026-04-03", "2026-04-04"], "2026-04-01", "2026-04-04"),
    (["2026-04-01", "2026-04-03"], "2026-04-02", None),
])
def test_saved_dates_must_equal_current_indicator_calendar_dates(
    dates: list[str], missing: str | None, extra: str | None
) -> None:
    saved = _signals().iloc[:len(dates)].copy()
    saved["date"] = dates
    before = saved.copy(deep=True)
    with pytest.raises(ValueError, match="golden_cross_signals.*trading dates") as error:
        _build(saved, _indicators())
    message = str(error.value)
    assert DAILY_PRICES_INDICATORS in message
    if missing:
        assert f"missing saved dates: {missing}" in message
    if extra:
        assert f"extra saved dates: {extra}" in message
    pd.testing.assert_frame_equal(saved, before)


def test_same_date_different_close_is_blocked_with_sources_and_sample() -> None:
    saved, current = _signals(), _indicators()
    saved.loc[1, "close"] = 999.0
    with pytest.raises(ValueError, match="close mismatch.*2026-04-02") as error:
        _build(saved, current)
    assert GOLDEN_CROSS_SIGNALS in str(error.value)
    assert DAILY_PRICES_INDICATORS in str(error.value)


@pytest.mark.parametrize("invalid", [None, float("nan"), "bad", "", float("inf"), 0.0, -1.0,
                                     True, complex(101, 0), pd.Timestamp("2026-04-02")])
@pytest.mark.parametrize("source", [GOLDEN_CROSS_SIGNALS, DAILY_PRICES_INDICATORS])
def test_invalid_close_never_counts_as_matching(invalid: object, source: str) -> None:
    saved, current = _signals(), _indicators()
    frame = saved if source == GOLDEN_CROSS_SIGNALS else current
    frame["close"] = frame["close"].astype(object)
    frame.loc[1, "close"] = invalid
    with pytest.raises(ValueError, match=f"{source}.*invalid close.*2026-04-02"):
        _build(saved, current)


def test_matching_invalid_closes_on_both_sides_are_not_accepted() -> None:
    saved, current = _signals(), _indicators()
    saved.loc[1, "close"] = float("nan")
    current.loc[1, "close"] = float("nan")
    with pytest.raises(ValueError, match="invalid close"):
        _build(saved, current)


@pytest.mark.parametrize("source", [GOLDEN_CROSS_SIGNALS, DAILY_PRICES_INDICATORS])
def test_unparseable_date_cannot_be_removed_to_fake_alignment(source: str) -> None:
    saved, current = _signals(), _indicators()
    frame = saved if source == GOLDEN_CROSS_SIGNALS else current
    frame.loc[1, "date"] = "invalid"
    with pytest.raises(ValueError, match=f"{source}.*invalid trading dates"):
        _build(saved, current)


@pytest.mark.parametrize("source", [GOLDEN_CROSS_SIGNALS, DAILY_PRICES_INDICATORS])
def test_duplicate_check_precedes_invalid_close_comparison(source: str) -> None:
    saved, current = _signals(), _indicators()
    frame = saved if source == GOLDEN_CROSS_SIGNALS else current
    frame.loc[1, "date"] = frame.loc[0, "date"]
    frame.loc[1, "close"] = float("nan")
    with pytest.raises(ValueError, match="duplicate trading dates"):
        _build(saved, current)


def test_sorting_and_numeric_strings_preserve_saved_signals_reasons_and_input() -> None:
    saved, current = _signals().iloc[::-1].copy(), _indicators()
    current["close"] = ["100.00", "101", "102.0"]
    saved_before, current_before = saved.copy(deep=True), current.copy(deep=True)
    expected = build_strategy_signal_rows("golden-cross", {GOLDEN_CROSS_SIGNALS: saved})
    pd.testing.assert_frame_equal(_build(saved, current), expected)
    pd.testing.assert_frame_equal(saved, saved_before)
    pd.testing.assert_frame_equal(current, current_before)


@pytest.mark.parametrize("representation", ["strings", "timestamps", "python-dates", "mixed"])
@pytest.mark.parametrize("source", ["current", "saved"])
def test_matching_local_calendar_dates_preserve_row_price_association(representation: str, source: str) -> None:
    saved, current = _signals(), _indicators()
    values: list[object] = ["2026-04-01 00:30:00+09:00", "2026-04-02 23:30:00-04:00", "2026-04-03 12:00:00+01:00"]
    if representation == "timestamps":
        values = [pd.Timestamp(value) for value in values]
    elif representation == "python-dates":
        values = [date(2026, 4, 1), datetime(2026, 4, 2, 17), date(2026, 4, 3)]
    elif representation == "mixed":
        values = [pd.Timestamp(values[0]), values[1], pd.Timestamp("2026-04-03")]
    frame = current if source == "current" else saved
    frame["date"] = pd.Series(values, dtype=object)
    frame = frame.iloc[[2, 0, 1]].copy()
    frame.index = [7, 7, 7]
    if source == "current":
        current = frame
    else:
        saved = frame
    before = frame.copy(deep=True)
    rows = _build(saved, current)
    assert rows["signal_reason"].tolist() == ["saved entry", "saved hold", "saved exit"]
    assert [value.date() for value in rows["date"]] == [date(2026, 4, day) for day in (1, 2, 3)]
    result = DEFAULT_BACKTEST_RUNNER.run(SYMBOL, rows)
    assert result.summary.iloc[0]["final_equity"] == pytest.approx(102.0 / 101.0)
    pd.testing.assert_frame_equal(frame, before)


def test_same_instant_on_different_local_days_is_a_date_mismatch() -> None:
    saved, current = _signals().iloc[:1].copy(), _indicators().iloc[:1].copy()
    saved["date"] = [pd.Timestamp("2026-04-03 00:30:00+09:00")]
    current["date"] = [pd.Timestamp("2026-04-02 11:30:00-04:00")]
    with pytest.raises(ValueError, match="trading dates") as error:
        _build(saved, current)
    assert "2026-04-02" in str(error.value)
    assert "2026-04-03" in str(error.value)


@pytest.mark.parametrize("bad_saved", ["dates", "close", "duplicates", "columns"])
def test_custom_windows_ignore_unused_saved_signals(bad_saved: str) -> None:
    saved, current = _signals(), _indicators()
    if bad_saved == "dates":
        saved["date"] = "1999-01-01"
    elif bad_saved == "close":
        saved["close"] = float("nan")
    elif bad_saved == "duplicates":
        saved.loc[1, "date"] = saved.loc[0, "date"]
    else:
        saved = pd.DataFrame({"unrelated": [1]})
    parameters = {"short_window": 2, "long_window": 3}
    expected = build_strategy_signal_rows("golden-cross", {DAILY_PRICES_INDICATORS: current}, parameters=parameters)
    pd.testing.assert_frame_equal(_build(saved, current, parameters=parameters), expected)


def test_matching_saved_path_preserves_next_close_final_close_and_mdd() -> None:
    saved = pd.DataFrame({"date": ["2026-04-01", "2026-04-02", "2026-04-03", "2026-04-04"],
                          "close": [95.0, 100.0, 50.0, 100.0], "signal": ["buy", "hold", "hold", "hold"]})
    expected = DEFAULT_BACKTEST_RUNNER.run(SYMBOL, build_strategy_signal_rows("golden-cross", {GOLDEN_CROSS_SIGNALS: saved}))
    result = DEFAULT_BACKTEST_RUNNER.run(SYMBOL, _build(saved, _indicators(saved)))
    pd.testing.assert_frame_equal(result.trades, expected.trades)
    pd.testing.assert_frame_equal(result.summary, expected.summary)
    assert result.summary.iloc[0]["max_drawdown_pct"] == pytest.approx(50.0)
    assert result.trades.iloc[0]["exit_reason"] == "final_close"


class _MemoryStorage:
    def __init__(self, frames: dict[tuple[str, str], pd.DataFrame | Exception]) -> None:
        self.frames = frames
        self.loads: list[tuple[str, str]] = []
        self.saved: list[tuple[str, str, pd.DataFrame]] = []

    def latest_filename(self, dataset: str, symbol: str) -> str | None:
        filenames = [filename for source, filename in self.frames if source == dataset and filename.startswith(f"{symbol}_")]
        return filenames[-1] if filenames else None

    def load(self, dataset: str, filename: str) -> pd.DataFrame:
        self.loads.append((dataset, filename))
        value = self.frames.get((dataset, filename))
        if value is None:
            raise FileNotFoundError(f"{dataset}: {filename}")
        if isinstance(value, Exception):
            raise value
        return value.copy(deep=True)

    def save(self, dataset: str, filename: str, frame: pd.DataFrame) -> SavedDataset:
        self.saved.append((dataset, filename, frame.copy(deep=True)))
        return SavedDataset(dataset, Path("/memory") / filename, len(frame))


@pytest.mark.parametrize("explicit", [False, True], ids=["latest", "explicit"])
@pytest.mark.parametrize("mismatch", ["dates", "close"])
def test_generator_and_cli_block_mismatch_without_persisting(explicit: bool, mismatch: str) -> None:
    current = _indicators()
    if mismatch == "dates":
        current = current.iloc[:2]
    else:
        current.loc[1, "close"] = 777.0
    storage = _MemoryStorage({(GOLDEN_CROSS_SIGNALS, SIGNAL_FILE): _signals(), (DAILY_PRICES_INDICATORS, INDICATOR_FILE): current})
    generator = GoldenCrossBacktestGenerator(processed_storage=storage)
    with pytest.raises(ValueError, match="trading dates|close mismatch"):
        if explicit:
            generator.load_signal_frame(BacktestRequest(SYMBOL, SIGNAL_FILE, indicator_filename=INDICATOR_FILE))
        else:
            run_backtest_for_symbol(SYMBOL, generator=generator)
    assert storage.saved == []
    assert generator._contexts_by_key == {}
    assert (DAILY_PRICES_INDICATORS, INDICATOR_FILE) in storage.loads


@pytest.mark.parametrize("current", [None, pd.DataFrame({"wrong": [1]}), pd.errors.EmptyDataError("empty indicator"), _indicators().iloc[:0]])
def test_explicit_missing_or_bad_indicator_does_not_fallback(current: pd.DataFrame | Exception | None) -> None:
    frames = {(GOLDEN_CROSS_SIGNALS, SIGNAL_FILE): _signals()}
    if current is not None:
        frames[(DAILY_PRICES_INDICATORS, INDICATOR_FILE)] = current
    storage = _MemoryStorage(frames)
    generator = GoldenCrossBacktestGenerator(processed_storage=storage)
    with pytest.raises((FileNotFoundError, ValueError)):
        generator.load_signal_frame(BacktestRequest(SYMBOL, SIGNAL_FILE, indicator_filename=INDICATOR_FILE))
    assert storage.saved == []
    assert generator._contexts_by_key == {}


@pytest.mark.parametrize("explicit", [False, True])
def test_generator_loads_actual_selected_indicator_and_records_that_source(explicit: bool) -> None:
    storage = _MemoryStorage({(GOLDEN_CROSS_SIGNALS, SIGNAL_FILE): _signals(),
                              (DAILY_PRICES_INDICATORS, INDICATOR_FILE): _indicators()})
    if explicit:
        storage.frames[(DAILY_PRICES_INDICATORS, "005930_later_bad.csv")] = _indicators().iloc[:1]
    generator = GoldenCrossBacktestGenerator(processed_storage=storage)
    request = BacktestRequest(SYMBOL, SIGNAL_FILE, indicator_filename=INDICATOR_FILE if explicit else None)
    loaded = generator.load_signal_frame(request)
    assert storage.loads == [(GOLDEN_CROSS_SIGNALS, SIGNAL_FILE), (DAILY_PRICES_INDICATORS, INDICATOR_FILE)]
    sources = loaded.attrs["backtest_input_sources"]
    assert sources.indicator_source_filename == INDICATOR_FILE
    assert sources.indicator_source_dataset == DAILY_PRICES_INDICATORS
    summary = generator.run_backtest(SYMBOL, loaded).summary.iloc[0]
    assert summary["indicator_source_filename"] == INDICATOR_FILE


def test_cli_persists_actual_latest_indicator_source() -> None:
    storage = _MemoryStorage({(GOLDEN_CROSS_SIGNALS, SIGNAL_FILE): _signals(), (DAILY_PRICES_INDICATORS, INDICATOR_FILE): _indicators()})
    run_backtest_for_symbol(SYMBOL, generator=GoldenCrossBacktestGenerator(processed_storage=storage))
    assert len(storage.saved) == 2
    summary = next(frame for dataset, _filename, frame in storage.saved if dataset == "backtest_summaries")
    assert summary.iloc[0]["indicator_source_filename"] == INDICATOR_FILE


@pytest.mark.parametrize("empty", [False, True])
def test_no_current_indicator_preserves_saved_only_and_empty_compatibility(empty: bool) -> None:
    saved = _signals().iloc[:0] if empty else _signals()
    storage = _MemoryStorage({(GOLDEN_CROSS_SIGNALS, SIGNAL_FILE): saved})
    generator = GoldenCrossBacktestGenerator(processed_storage=storage)
    loaded = generator.load_signal_frame(BacktestRequest(SYMBOL, SIGNAL_FILE))
    assert loaded.empty == empty
    assert loaded.attrs["backtest_input_sources"].indicator_source_dataset is None
    assert loaded.attrs["backtest_input_sources"].indicator_source_filename is None
    assert generator.run_backtest(SYMBOL, loaded).summary.iloc[0]["source_rows"] == len(saved)


def test_empty_saved_signals_cannot_claim_alignment_to_nonempty_current() -> None:
    with pytest.raises(ValueError, match="trading dates"):
        _build(_signals().iloc[:0], _indicators())


def test_explicit_default_windows_still_validate_saved_alignment() -> None:
    with pytest.raises(ValueError, match="trading dates"):
        _build(_signals().iloc[:2], _indicators(), parameters={"short_window": 5, "long_window": 20})


@pytest.mark.parametrize("saved", [None, pd.DataFrame({"unrelated": [1]})])
def test_unused_saved_frame_keeps_default_current_indicator_calculation(saved: pd.DataFrame | None) -> None:
    current = _indicators()
    expected = build_strategy_signal_rows("golden-cross", {DAILY_PRICES_INDICATORS: current})
    actual = build_strategy_signal_rows("golden-cross", {DAILY_PRICES_INDICATORS: current, GOLDEN_CROSS_SIGNALS: saved})
    pd.testing.assert_frame_equal(actual, expected)


@pytest.mark.parametrize("has_current", [False, True])
def test_generator_does_not_recalculate_a_malformed_declared_signal_file(has_current: bool) -> None:
    frames = {(GOLDEN_CROSS_SIGNALS, SIGNAL_FILE): pd.DataFrame({"unrelated": [1]})}
    if has_current:
        frames[(DAILY_PRICES_INDICATORS, INDICATOR_FILE)] = _indicators()
    storage = _MemoryStorage(frames)
    generator = GoldenCrossBacktestGenerator(processed_storage=storage)
    with pytest.raises(ValueError, match="golden_cross_signals.*missing columns"):
        run_backtest_for_symbol(SYMBOL, generator=generator)
    assert storage.saved == []
    assert generator._contexts_by_key == {}
