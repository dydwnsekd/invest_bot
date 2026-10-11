from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace

import pandas as pd
import pytest

from invest_bot.backtest import (
    BacktestDataReadinessError,
    DEFAULT_BACKTEST_RUNNER,
    GOLDEN_CROSS_SIGNALS,
    build_daily_mark_to_market_equity_curve,
    build_strategy_signal_rows,
    check_backtest_readiness,
    combine_strategy_signal_rows,
    resolve_backtest_combination_settings,
)
from invest_bot.backtest.dates import duplicate_trading_date_reason
from invest_bot.backtest.runner import NormalizedSignalBacktestRunner
from invest_bot.backtest.strategy_registry import DAILY_PRICES_INDICATORS, INVESTOR_DAILY
from invest_bot.dashboard import streamlit_backtest as dashboard
from invest_bot.jobs.generate_backtest import GoldenCrossBacktestGenerator
from invest_bot.jobs.run_backtest import run_backtest_for_symbol


def _rows(dates: list[object]) -> pd.DataFrame:
    return pd.DataFrame({
        "date": pd.Series(dates, dtype=object),
        "close": [100.0] * len(dates),
        "signal": ["hold"] * len(dates),
        "rsi_14": [50.0] * len(dates),
        "ma_20": [100.0] * len(dates),
    })


def _exercise(boundary: str, frame: pd.DataFrame) -> None:
    if boundary == "readiness":
        result = check_backtest_readiness(["rsi"], {DAILY_PRICES_INDICATORS: frame})
        assert not result.ready_to_run
        assert "duplicate trading dates: 2026-04-03" in "; ".join(result.blocking_reasons)
    else:
        with pytest.raises(ValueError, match="duplicate trading dates: 2026-04-03"):
            if boundary == "saved-adapter":
                build_strategy_signal_rows("golden-cross", {GOLDEN_CROSS_SIGNALS: frame})
            elif boundary == "runner":
                DEFAULT_BACKTEST_RUNNER.run("QA_ONLY", frame)
            elif boundary == "curve":
                build_daily_mark_to_market_equity_curve(frame, pd.DataFrame())
            else:
                settings = resolve_backtest_combination_settings(["rsi", "momentum"])
                combine_strategy_signal_rows({"rsi": frame, "momentum": frame.copy()}, settings)


@pytest.mark.parametrize("representation", ["strings", "timestamps", "aware-naive-timestamps", "timestamp-string"])
@pytest.mark.parametrize("boundary", ["readiness", "saved-adapter", "runner", "curve", "combination"])
def test_timezone_same_local_date_rejected_for_each_representation_and_boundary(
    representation: str, boundary: str
) -> None:
    values: list[object] = ["2026-04-03 00:30:00+09:00", "2026-04-03 23:30:00-04:00"]
    if representation == "timestamps":
        values = [pd.Timestamp(value) for value in values]
    elif representation == "aware-naive-timestamps":
        values = [pd.Timestamp(values[0]), pd.Timestamp("2026-04-03")]
    elif representation == "timestamp-string":
        values[0] = pd.Timestamp(values[0])
    frame = _rows(values)
    before = frame.copy(deep=True)
    _exercise(boundary, frame)
    pd.testing.assert_frame_equal(frame, before)


@pytest.mark.parametrize("representation", ["strings", "timestamps"])
def test_same_instant_on_different_local_dates_is_not_a_duplicate(representation: str) -> None:
    values: list[object] = ["2026-04-03 00:30:00+09:00", "2026-04-02 11:30:00-04:00"]
    if representation == "timestamps":
        values = [pd.Timestamp(value) for value in values]
    assert duplicate_trading_date_reason(_rows(values), source="QA memory rows") is None


@pytest.mark.parametrize("duplicate_primary", [False, True])
def test_investor_date_takes_precedence_over_trade_date(duplicate_primary: bool) -> None:
    price = _rows(["2026-04-03", "2026-04-06"])
    investor = pd.DataFrame({
        "date": ["2026-04-03", "2026-04-03" if duplicate_primary else "2026-04-06"],
        "trade_date": ["2026-04-03", "2026-04-06" if duplicate_primary else "2026-04-03"],
        "foreign_net_qty": [1.0, 1.0],
        "institutional_net_qty": [1.0, 1.0],
    })
    before = investor.copy(deep=True)
    datasets = {DAILY_PRICES_INDICATORS: price, INVESTOR_DAILY: investor}
    readiness = check_backtest_readiness(["investor-flow-custom"], datasets)
    if duplicate_primary:
        assert not readiness.ready_to_run
        with pytest.raises(BacktestDataReadinessError, match="investor_daily has duplicate trading dates"):
            build_strategy_signal_rows("investor-flow-custom", datasets)
    else:
        assert readiness.ready_to_run
        assert len(build_strategy_signal_rows("investor-flow-custom", datasets)) == 2
    pd.testing.assert_frame_equal(investor, before)


def test_raw_investor_missing_columns_remains_original_blocker() -> None:
    raw = pd.DataFrame({"trade_date": ["2026-04-03", "2026-04-03"], "investor_type": ["foreign", "institution"]})
    datasets = {DAILY_PRICES_INDICATORS: _rows(["2026-04-03"]), INVESTOR_DAILY: raw}
    reason = "; ".join(check_backtest_readiness(["investor-flow-custom"], datasets).blocking_reasons)
    assert "missing columns in investor_daily" in reason
    assert "foreign_net_qty" in reason
    assert "institutional_net_qty" in reason
    assert "duplicate trading dates" not in reason


def test_error_contains_source_sorted_bounded_sample_and_policy() -> None:
    dates = ["2026-04-06", "2026-04-03", "2026-04-02", "2026-04-01"] * 2
    reason = duplicate_trading_date_reason(_rows(dates), source="QA memory rows")
    assert reason == (
        "QA memory rows has duplicate trading dates: 2026-04-01, 2026-04-02, 2026-04-03 (+1 more); "
        "daily backtests require one row per trading date"
    )


def test_repeated_invalid_values_are_excluded_from_duplicate_count() -> None:
    frame = _rows([pd.NaT, pd.NaT, None, None, "invalid", "invalid", "2026-04-03"])
    before = frame.copy(deep=True)
    assert duplicate_trading_date_reason(frame, source="QA memory rows") is None
    pd.testing.assert_frame_equal(frame, before)


def test_duplicate_validation_precedes_trade_calculation(monkeypatch: pytest.MonkeyPatch) -> None:
    frame = _rows(["2026-04-03", "2026-04-03"])
    frame["signal"] = ["buy", "sell"]
    frame["close"] = ["not-a-price", "not-a-price"]
    def unexpected(*_args: object, **_kwargs: object) -> None:
        pytest.fail("duplicate inputs reached summary computation")
    monkeypatch.setattr(NormalizedSignalBacktestRunner, "_build_summary", unexpected)
    with pytest.raises(ValueError, match="duplicate trading dates"):
        DEFAULT_BACKTEST_RUNNER.run("QA_ONLY", frame)


@pytest.mark.parametrize("bad_strategy", ["rsi", "momentum"])
@pytest.mark.parametrize("mode", ["and", "or", "weighted"])
def test_combination_validates_each_strategy_before_synthesis(bad_strategy: str, mode: str) -> None:
    frames = {name: _rows(["2026-04-03", "2026-04-06"]) for name in ["rsi", "momentum"]}
    frames[bad_strategy] = _rows(["2026-04-03", "2026-04-03"])
    frames[bad_strategy].loc[1, "close"] = None
    settings = resolve_backtest_combination_settings(list(frames), mode=mode)
    with pytest.raises(ValueError, match=f"{bad_strategy} strategy signal rows has duplicate trading dates"):
        combine_strategy_signal_rows(frames, settings)


class _MemoryStorage:
    def __init__(self, frame: pd.DataFrame) -> None:
        self.frame = frame
        self.saved: list[object] = []

    def latest_filename(self, *_args: object) -> str:
        return "QA_ONLY_signals.csv"

    def load(self, *_args: object) -> pd.DataFrame:
        return self.frame.copy(deep=True)

    def save(self, *args: object) -> None:
        self.saved.append(args)
        pytest.fail("duplicate generator input reached artifact persistence")


def test_generator_cli_workflow_never_persists_duplicate_input() -> None:
    storage = _MemoryStorage(_rows(["2026-04-03", "2026-04-03"]))
    generator = GoldenCrossBacktestGenerator(processed_storage=storage)
    with pytest.raises(ValueError, match="golden_cross_signals has duplicate trading dates"):
        run_backtest_for_symbol("QA_ONLY", generator=generator)
    assert storage.saved == []
    assert generator._contexts_by_key == {}


def test_generator_direct_runner_does_not_allocate_context_on_duplicates() -> None:
    frame = _rows(["2026-04-03", "2026-04-03"])
    storage = _MemoryStorage(frame)
    generator = GoldenCrossBacktestGenerator(processed_storage=storage)
    with pytest.raises(ValueError, match="QA_ONLY signal rows has duplicate trading dates"):
        generator.run_backtest("QA_ONLY", frame)
    assert storage.saved == []
    assert generator._contexts_by_key == {}


def test_dashboard_preparation_table_and_render_show_duplicate_block(monkeypatch: pytest.MonkeyPatch) -> None:
    frame = _rows(["2026-04-03", "2026-04-03"])
    inputs = dashboard.LoadedBacktestInputs(
        symbol="QA_ONLY",
        indicator=dashboard.LoadedDataset(DAILY_PRICES_INDICATORS, "memory.csv", frame),
        investor=dashboard.LoadedDataset(INVESTOR_DAILY, None, None),
        price=dashboard.LoadedDataset("daily_prices", None, None),
        golden_cross_signal=dashboard.LoadedDataset(GOLDEN_CROSS_SIGNALS, None, None),
    )
    payload = dashboard._build_readiness_payload(
        selected_items=[SimpleNamespace(symbol="QA_ONLY", symbol_name="QA memory")],
        selected_strategy_ids=["rsi"],
        loaded_inputs={"QA_ONLY": inputs},
        strategy_labels={"rsi": "RSI"},
    )
    assert payload["can_run"] is False
    assert payload["ready_count"] == 0
    row = payload["rows"].iloc[0]
    assert row["ready"] == "차단"
    assert "daily_prices_indicators has duplicate trading dates: 2026-04-03" in row["blocking_reasons"]
    rendered: list[pd.DataFrame] = []
    warnings: list[str] = []
    column = SimpleNamespace(metric=lambda *_args: None)
    fake = SimpleNamespace(
        markdown=lambda *_args, **_kwargs: None,
        columns=lambda *_args, **_kwargs: [column] * 3,
        dataframe=lambda frame, **_kwargs: rendered.append(frame.copy()),
        warning=warnings.append,
    )
    monkeypatch.setattr(dashboard, "st", fake)
    dashboard._render_readiness_panel(payload)
    assert rendered[0].iloc[0]["ready"] == "차단"
    assert "duplicate trading dates: 2026-04-03" in warnings[0]


@pytest.mark.parametrize("values", [
    pytest.param([date(2026, 4, 3), date(2026, 4, 3)], id="date-date"),
    pytest.param([date(2026, 4, 3), "2026-04-03"], id="date-string"),
    pytest.param([date(2026, 4, 3), pd.Timestamp("2026-04-03 15:30")], id="date-timestamp"),
    pytest.param([datetime(2026, 4, 3, 9), datetime(2026, 4, 3, 15, 30)], id="datetime-intraday"),
    pytest.param([datetime(2026, 4, 3, 0, 30, tzinfo=timezone(timedelta(hours=9))),
                  "2026-04-03 23:30:00-04:00"], id="aware-datetime-offset-string"),
    pytest.param([datetime(2026, 4, 3, 0, 30, tzinfo=timezone(timedelta(hours=9))),
                  datetime(2026, 4, 3, 23, 30, tzinfo=timezone(timedelta(hours=-4)))], id="mixed-offset-datetimes"),
    pytest.param([datetime(2026, 4, 3, 0, 30, tzinfo=timezone(timedelta(hours=9))),
                  datetime(2026, 4, 3)], id="aware-naive-datetimes"),
    pytest.param([pd.Timestamp("2026-04-03 00:30:00+09:00"),
                  datetime(2026, 4, 3, 23, 30, tzinfo=timezone(timedelta(hours=-4)))], id="timestamp-datetime"),
])
def test_followup_python_date_and_datetime_preserve_local_calendar_policy(values: list[object]) -> None:
    frame = _rows(values)
    before = frame.copy(deep=True)
    assert duplicate_trading_date_reason(frame, source="QA Python dates") == (
        "QA Python dates has duplicate trading dates: 2026-04-03; "
        "daily backtests require one row per trading date"
    )
    pd.testing.assert_frame_equal(frame, before)


@pytest.mark.parametrize("second", [
    datetime(2026, 4, 2, 11, 30, tzinfo=timezone(timedelta(hours=-4))),
    "2026-04-02 11:30:00-04:00",
])
def test_followup_python_datetime_same_instant_different_local_day_allowed(second: object) -> None:
    frame = _rows([datetime(2026, 4, 3, 0, 30, tzinfo=timezone(timedelta(hours=9))), second])
    before = frame.copy(deep=True)
    assert duplicate_trading_date_reason(frame, source="QA Python dates") is None
    pd.testing.assert_frame_equal(frame, before)


def test_followup_nat_excluded_around_python_date_and_string_partitions() -> None:
    frame = _rows([pd.NaT, date(2026, 4, 3), pd.NaT, None, "invalid", "invalid", "2026-04-06"])
    frame.index = [7] * len(frame)
    before = frame.copy(deep=True)
    assert duplicate_trading_date_reason(frame, source="QA partitions") is None
    pd.testing.assert_frame_equal(frame, before)


@pytest.mark.parametrize("index", [[7, 7, 7], [7, 2, 7], ["repeated", "other", "repeated"]])
@pytest.mark.parametrize("boundary", ["readiness", "saved-adapter", "runner", "curve", "combination"])
def test_followup_repeated_indexes_do_not_hide_duplicates_across_parse_partitions(
    index: list[object], boundary: str
) -> None:
    frame = _rows([date(2026, 4, 3), "invalid", "2026-04-03 15:30:00"])
    frame.index = index
    frame.index.name = "fixture_index"
    before = frame.copy(deep=True)
    _exercise(boundary, frame)
    pd.testing.assert_frame_equal(frame, before)
