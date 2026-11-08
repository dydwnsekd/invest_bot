from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime
import json
from pathlib import Path

import pandas as pd
import pytest

from invest_bot.backtest import DEFAULT_BACKTEST_ADAPTER_REGISTRY, DEFAULT_BACKTEST_RUNNER
from invest_bot.backtest.combination import combine_strategy_signal_rows, resolve_backtest_combination_settings
from invest_bot.backtest.parameters import resolve_backtest_parameters
from invest_bot.backtest import persistence
from invest_bot.dashboard.service import DashboardDataService
from invest_bot.db.frame_storage import DbFrameStorage
from invest_bot.market.storage import CsvStorage, SavedDataset
from tests.helpers import init_test_db


def _batch(*, symbols=("005930",), rsi=None, saved=False, golden=None):
    summaries, trades, metadata = [], [], []
    for number, symbol in enumerate(symbols):
        flat = number > 0
        frame = pd.DataFrame({
            "date": pd.date_range("2026-04-01", periods=5),
            "close": [100.] * 5 if flat else [95., 100., 50., 100., 110.],
            "rsi_14": [50.] * 5 if flat else [35., 50., 50., 65., 50.],
            "ma_5": [100.] * 5 if flat else [98., 101., 102., 98., 102.],
            "ma_20": [100.] * 5,
        })
        datasets = {"daily_prices_indicators": frame}
        if saved:
            datasets["golden_cross_signals"] = frame[["date", "close"]].assign(
                signal=["buy", "hold", "hold", "sell", "hold"], signal_reason="saved",
            )
        contexts, signals = {}, {}
        for strategy_id, supplied in [("rsi", rsi), ("golden-cross", golden)]:
            parameters = resolve_backtest_parameters(strategy_id, supplied)
            adapted = DEFAULT_BACKTEST_ADAPTER_REGISTRY.build_signal_rows(strategy_id, datasets, parameters=parameters)
            uses_saved = saved and strategy_id == "golden-cross" and parameters == {"short_window": 5., "long_window": 20.}
            sources = persistence.BacktestInputSources(
                indicator_source_filename=f"{symbol}_indicators.csv",
                signal_source_dataset="golden_cross_signals" if uses_saved else None,
                signal_source_filename=f"{symbol}_signals.csv" if uses_saved else None,
                investor_source_dataset=None, price_source_dataset=None,
            )
            context = persistence.build_context(
                symbol=symbol, strategy_id=adapted.strategy_id, strategy_name=adapted.strategy_name,
                input_sources=sources, strategy_parameters=parameters, now=datetime(2026, 11, 8, tzinfo=UTC),
            )
            contexts[strategy_id], signals[strategy_id] = context, adapted.signal_rows
            result = DEFAULT_BACKTEST_RUNNER.run(symbol, adapted.signal_rows)
            summaries.append(persistence.enrich_summary(result.summary, context))
            trades.append(persistence.enrich_trades(result.trades, context))
        settings = resolve_backtest_combination_settings(list(contexts), "or", {"rsi": 1.5, "golden-cross": .5})
        combined_metadata = persistence.build_combination_metadata(settings, contexts)
        metadata.append(combined_metadata)
        context = persistence.build_context(
            symbol=symbol, strategy_id=settings.strategy_id, strategy_name=settings.strategy_name,
            input_sources=contexts["rsi"].input_sources, combination_settings=combined_metadata,
            now=datetime(2026, 11, 8, tzinfo=UTC),
        )
        result = DEFAULT_BACKTEST_RUNNER.run(symbol, combine_strategy_signal_rows(signals, settings))
        summaries.append(persistence.enrich_summary(result.summary, context))
        trades.append(persistence.enrich_trades(result.trades, context))
    return pd.concat(summaries, ignore_index=True), pd.concat(trades, ignore_index=True), metadata


class MemoryStorage:
    def __init__(self, *, fail_at=None):
        self.frames, self.writes, self.fail_at = {}, [], fail_at

    def load(self, dataset, filename):
        if (dataset, filename) not in self.frames:
            raise FileNotFoundError(filename)
        return self.frames[(dataset, filename)].copy(deep=True)

    def save(self, dataset, filename, frame):
        if len(self.writes) == self.fail_at:
            raise OSError("synthetic write failure")
        self.writes.append((dataset, filename))
        self.frames[(dataset, filename)] = frame.copy(deep=True)
        return SavedDataset(dataset, Path("/memory") / filename, len(frame))


def test_effective_rsi_and_actual_saved_signal_choice_survive_both_json_columns():
    summary, trades, metadata = _batch(rsi={"buy_threshold": 40, "sell_threshold": 60}, saved=True)
    _, _, default = _batch(saved=True)
    assert metadata != default
    component = metadata[0]["components"]["rsi"]
    assert component["strategy_parameters"] == {"buy_threshold": 40., "sell_threshold": 60.}
    assert metadata[0]["components"]["golden-cross"]["uses_saved_signal"] is True
    assert metadata[0]["components"]["golden-cross"]["input_sources"]["signal"]["filename"] == "005930_signals.csv"
    combo = summary.loc[summary.strategy_id == "combination-or"].iloc[0]
    assert combo.max_drawdown_pct == pytest.approx(50.)
    assert combo.total_return_pct == pytest.approx(10.)
    assert json.loads(combo.combination_settings_json) == metadata[0]
    assert json.loads(combo.strategy_parameters_json) == {}  # flat single-strategy column is unchanged
    assert json.loads(summary.iloc[0].strategy_parameters_json) == component["strategy_parameters"]
    assert json.loads(trades.loc[trades.strategy_id == "combination-or"].iloc[0].combination_settings_json) == metadata[0]
    _, _, custom = _batch(saved=True, golden={"short_window": 2, "long_window": 3})
    gc = custom[0]["components"]["golden-cross"]
    assert gc["uses_saved_signal"] is False
    assert gc["input_sources"]["signal"] == {"dataset": None, "filename": None}


@pytest.mark.parametrize(("value", "status"), [
    (None, "legacy"), ("{}", "legacy"),
    ('{"mode":"and","weights":{"rsi":1},"component_strategy_ids":["rsi"]}', "legacy"),
    ("{", "malformed"), ('{"metadata_version":99}', "unsupported"),
    ('{"metadata_version":1}', "malformed"),
])
def test_reader_separates_legacy_malformed_and_unsupported_without_inference(value, status):
    result = persistence.read_combination_metadata(value)
    assert result.status == status
    assert result.metadata is None
    assert result.message


def test_recorded_reader_does_not_resolve_todays_defaults(monkeypatch):
    _, _, metadata = _batch(rsi={"buy_threshold": 40, "sell_threshold": 60})
    monkeypatch.setattr(persistence, "resolve_backtest_parameters", lambda *a, **kw: pytest.fail("inferred defaults"))
    result = persistence.read_combination_metadata(json.dumps(metadata[0]))
    assert result.status == "recorded"
    assert result.metadata == metadata[0]
    bad = deepcopy(metadata[0])
    bad["components"]["rsi"]["strategy_parameters"]["buy_threshold"] = float("nan")
    assert persistence.read_combination_metadata(bad).status == "malformed"


def test_explicit_save_only_collision_and_late_validation_have_zero_writes():
    from invest_bot.backtest.artifacts import save_backtest_batch
    summary, trades, _ = _batch(symbols=("005930", "000660"), rsi={"buy_threshold": 40, "sell_threshold": 60})
    storage = MemoryStorage()
    original = summary.copy(deep=True)
    assert storage.writes == []
    broken = summary.copy(deep=True)
    broken.loc[len(broken) - 1, "combination_settings_json"] = '{"metadata_version":99}'
    with pytest.raises(ValueError):
        save_backtest_batch(storage, broken, trades)
    assert storage.writes == []
    saved = save_backtest_batch(storage, summary, trades)
    assert len(saved) == 12  # every single/combination, every symbol, zero-trade run included
    pd.testing.assert_frame_equal(summary, original)
    with pytest.raises(FileExistsError):
        save_backtest_batch(storage, summary, trades)
    assert len(storage.writes) == 12
    for dataset, filename in storage.writes:
        assert filename.startswith(("005930_", "000660_"))
        assert dataset in {"backtest_summaries", "backtest_trades"}
    assert sum(len(frame) for (dataset, _), frame in storage.frames.items() if dataset == "backtest_trades") == len(trades)


@pytest.mark.parametrize("backend", ["csv", "sqlite"])
def test_actual_adapter_batch_round_trips_through_new_service(tmp_path, monkeypatch, backend):
    from invest_bot.backtest.artifacts import save_backtest_batch
    summary, trades, _ = _batch(symbols=("005930", "000660"), rsi={"buy_threshold": 40, "sell_threshold": 60})
    if backend == "csv":
        storage = CsvStorage(tmp_path / "processed")
    else:
        url = f"sqlite+pysqlite:///{tmp_path / 'frames.sqlite'}"
        init_test_db(url)
        storage = DbFrameStorage(url)
    before_summary, before_trades = summary.copy(deep=True), trades.copy(deep=True)
    saved = save_backtest_batch(storage, summary, trades)
    monkeypatch.setattr(DashboardDataService, "_load_symbol_name_map", lambda self: {})
    monkeypatch.setattr(DEFAULT_BACKTEST_RUNNER, "run", lambda *a, **kw: pytest.fail("history reran engine"))
    service = DashboardDataService(
        raw_root=tmp_path / "raw", processed_root=tmp_path / "processed",
        dataset_storage=DbFrameStorage(url) if backend == "sqlite" else None,
    )
    previews = service.list_backtest_history_previews()
    assert len(previews) == 6
    for preview in previews:
        loaded = service.load_preview_frame(preview).iloc[0]
        expected = summary.loc[summary.run_id == loaded.run_id].iloc[0]
        assert loaded.final_equity == pytest.approx(expected.final_equity)
        assert loaded.max_drawdown_pct == pytest.approx(expected.max_drawdown_pct)
        assert json.loads(loaded.strategy_parameters_json) == json.loads(expected.strategy_parameters_json)
        if loaded.strategy_id.startswith("combination-"):
            parsed = persistence.read_combination_metadata(loaded.combination_settings_json)
            assert parsed.status == "recorded"
            assert parsed.metadata == json.loads(expected.combination_settings_json)
    trade_previews = service.list_backtest_history_previews("backtest_trades")
    assert len(trade_previews) == 6
    reloaded = [service.load_preview_frame(preview) for preview in trade_previews]
    assert sum(len(frame) for frame in reloaded) == len(trades)
    assert sum(frame.empty for frame in reloaded) == 3
    for frame in reloaded:
        for _, row in frame.iterrows():
            expected = trades.loc[(trades.run_id == row.run_id) & (pd.to_datetime(trades.entry_date) == pd.Timestamp(row.entry_date))].iloc[0]
            assert row.return_pct == pytest.approx(expected.return_pct)
    pd.testing.assert_frame_equal(summary, before_summary)
    pd.testing.assert_frame_equal(trades, before_trades)
    assert len(saved) == 12


def test_partial_failure_is_not_success_and_reports_confirmed_artifacts():
    from invest_bot.backtest.artifacts import BacktestArtifactSaveError, save_backtest_batch
    summary, trades, _ = _batch(rsi={"buy_threshold": 40, "sell_threshold": 60})
    storage = MemoryStorage(fail_at=1)
    with pytest.raises(BacktestArtifactSaveError) as error:
        save_backtest_batch(storage, summary, trades)
    assert len(error.value.saved) == 1
    assert "synthetic write failure" in str(error.value)
    assert len(storage.writes) == 1


@pytest.mark.parametrize("problem", ["orphan", "count", "trade-metadata", "path", "duplicate-summary"])
def test_invalid_batch_is_rejected_before_any_write(problem):
    from invest_bot.backtest.artifacts import save_backtest_batch
    summary, trades, _ = _batch(rsi={"buy_threshold": 40, "sell_threshold": 60})
    if problem == "orphan":
        trades.loc[0, "run_id"] = "unknown"
    elif problem == "count":
        summary.loc[0, "trade_count"] += 1
    elif problem == "trade-metadata":
        trades.loc[0, "strategy_parameters_json"] = "{}"
    elif problem == "path":
        summary.loc[len(summary) - 1, "strategy_id"] = "../unsafe"
    else:
        summary = pd.concat([summary, summary.iloc[:1]], ignore_index=True)
    storage = MemoryStorage()
    with pytest.raises(ValueError):
        save_backtest_batch(storage, summary, trades)
    assert storage.writes == []


def test_existing_zero_byte_trade_artifact_blocks_whole_batch(tmp_path):
    from invest_bot.backtest.artifacts import save_backtest_batch
    summary, trades, _ = _batch()
    filename = persistence.build_output_filename(summary.iloc[-1:], persistence.BACKTEST_TRADES_OUTPUT)
    storage = CsvStorage(tmp_path)
    existing = tmp_path / "backtest_trades" / filename
    existing.parent.mkdir()
    existing.touch()
    with pytest.raises(FileExistsError):
        save_backtest_batch(storage, summary, trades)
    assert list(tmp_path.rglob("*.csv")) == [existing]
    assert existing.stat().st_size == 0


def test_metadata_snapshot_and_inconsistent_source_rejection():
    _, _, metadata = _batch(saved=True)
    context = persistence.build_context(
        symbol="005930", strategy_id="combination-or", strategy_name="OR",
        input_sources=persistence.BacktestInputSources(), combination_settings=metadata[0],
    )
    original = deepcopy(metadata[0])
    metadata[0]["components"]["rsi"]["strategy_parameters"]["buy_threshold"] = 44
    assert json.loads(context.combination_settings_json()) == original
    original["components"]["golden-cross"]["uses_saved_signal"] = False
    assert persistence.read_combination_metadata(original).status == "malformed"
    with pytest.raises(ValueError):
        persistence.build_context(symbol="005930", strategy_id="combination-or", strategy_name="OR",
                                  input_sources=persistence.BacktestInputSources(), combination_settings=original)
