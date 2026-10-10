from __future__ import annotations

import json
import sys
from datetime import datetime

import pytest
import yaml

from invest_bot.jobs import scheduled_collection
from invest_bot.jobs.collect_market_data import DEFAULT_COLLECTION_LOOKBACK_DAYS
from invest_bot.jobs.scheduled_collection import CollectionScheduleConfig, ScheduledCollectionRunner, load_schedule_status
from tests.helpers import make_test_dir


@pytest.mark.parametrize("field", ["days", "interval_minutes"])
@pytest.mark.parametrize("value", [0, -1, 1.5, 1.0, True, False, "1.5", "invalid", "", None])
def test_schedule_rejects_invalid_positive_integers(tmp_path, field, value):
    config_file = tmp_path / "schedule.yaml"
    config_file.write_text(
        yaml.safe_dump({"symbols": ["005930"], field: value}), encoding="utf-8"
    )

    with pytest.raises(ValueError, match=field):
        CollectionScheduleConfig.from_file(config_file)


@pytest.mark.parametrize("value", [1, "15", " 60 "])
def test_schedule_accepts_positive_integer_values_and_numeric_strings(tmp_path, value):
    config_file = tmp_path / "schedule.yaml"
    config_file.write_text(
        yaml.safe_dump({"symbols": ["005930"], "days": value, "interval_minutes": value}),
        encoding="utf-8",
    )

    schedule = CollectionScheduleConfig.from_file(config_file)

    assert schedule.days == int(value)
    assert schedule.interval_minutes == int(value)


@pytest.mark.parametrize("value,expected", [(True, True), (False, False), ("true", True), ("false", False), (" FALSE ", False)])
def test_schedule_parses_boolean_without_python_truthiness(tmp_path, value, expected):
    config_file = tmp_path / "schedule.yaml"
    config_file.write_text(
        yaml.safe_dump({"symbols": ["005930"], "run_on_startup": value}), encoding="utf-8"
    )

    assert CollectionScheduleConfig.from_file(config_file).run_on_startup is expected


@pytest.mark.parametrize("value", [0, 1, "", "yes", "no", [], {}, None])
def test_schedule_rejects_ambiguous_boolean_values(tmp_path, value):
    config_file = tmp_path / "schedule.yaml"
    config_file.write_text(
        yaml.safe_dump({"symbols": ["005930"], "run_on_startup": value}), encoding="utf-8"
    )

    with pytest.raises(ValueError, match="run_on_startup"):
        CollectionScheduleConfig.from_file(config_file)


@pytest.mark.parametrize("text", [
    "- not-a-mapping\n", "false\n", "0\n", "symbols: 5930\n",
    "symbols: {code: '005930'}\n", "symbols: [true]\n",
    "symbols: [[005930]]\n", "symbols: ['005930']\nsymbols_file: true\n",
    "symbols: ['005930']\nlog_path: []\n", "symbols: ['005930']\nlog_path: null\n",
])
def test_schedule_rejects_wrong_yaml_types(tmp_path, text):
    config_file = tmp_path / "schedule.yaml"
    config_file.write_text(text, encoding="utf-8")

    with pytest.raises(ValueError):
        CollectionScheduleConfig.from_file(config_file)


def test_schedule_preserves_csv_symbols_file_deduplication_and_relative_log(tmp_path):
    (tmp_path / "symbols.csv").write_text("000660\n035420\n005930\n", encoding="utf-8")
    config_file = tmp_path / "schedule.yaml"
    config_file.write_text(
        "symbols: '005930,000660'\nsymbols_file: symbols.csv\nlog_path: ../runtime/collection.log\n",
        encoding="utf-8",
    )

    schedule = CollectionScheduleConfig.from_file(config_file)

    assert schedule.symbols == ["005930", "000660", "035420"]
    assert schedule.log_path == tmp_path / ".." / "runtime" / "collection.log"
    assert schedule.days == 365
    assert schedule.interval_minutes == 1440
    assert schedule.run_on_startup is True


@pytest.mark.parametrize("args,count,waits", [
    (["--once"], 1, []),
    (["--max-runs", "2"], 2, [60, 60]),
])
def test_schedule_main_preserves_once_and_normal_loop(tmp_path, monkeypatch, args, count, waits):
    config_file = tmp_path / "schedule.yaml"
    config_file.write_text(
        "symbols: ['005930']\nrun_on_startup: false\ninterval_minutes: 1\nlog_path: collection.log\n",
        encoding="utf-8",
    )
    collected = []
    synced = []
    sleeps = []

    def collector(symbols, days):
        collected.append((symbols, days))
        return {"success_count": 1, "failed_count": 0}

    def runner(schedule, before_run_fn):
        return ScheduledCollectionRunner(
            schedule=schedule, before_run_fn=before_run_fn,
            collector_fn=collector, sleep_fn=sleeps.append,
        )

    monkeypatch.setattr(sys, "argv", ["scheduler", "--config", str(config_file), *args])
    monkeypatch.setattr(scheduled_collection, "sync_stock_master", lambda: synced.append("sync"))
    monkeypatch.setattr(scheduled_collection, "ScheduledCollectionRunner", runner)

    scheduled_collection.main()

    assert collected == [(["005930"], 365)] * count
    assert synced == ["sync"] * count
    assert sleeps == waits
    assert load_schedule_status(config_file).total_logged_runs == count


def test_collection_schedule_config_loads_symbols_and_symbols_file():
    test_dir = make_test_dir("scheduled_collection_config")
    symbols_file = test_dir / "symbols.txt"
    symbols_file.write_text("005930\n000660\n005930\n", encoding="utf-8")

    config_file = test_dir / "collection_schedule.yaml"
    config_file.write_text(
        "\n".join(
            [
                "symbols:",
                "  - '035420'",
                f"symbols_file: {symbols_file.name}",
                "days: 15",
                "interval_minutes: 60",
                "run_on_startup: false",
                "log_path: logs/custom_collection.log",
            ]
        ),
        encoding="utf-8",
    )

    config = CollectionScheduleConfig.from_file(config_file)

    assert config.symbols == ["035420", "005930", "000660"]
    assert config.days == 15
    assert config.interval_minutes == 60
    assert config.run_on_startup is False
    assert config.log_path.name == "custom_collection.log"



def test_collection_schedule_config_defaults_to_365_days_when_omitted():
    test_dir = make_test_dir("scheduled_collection_default_days")
    config_file = test_dir / "collection_schedule.yaml"
    config_file.write_text("symbols:\n  - '005930'\n", encoding="utf-8")

    config = CollectionScheduleConfig.from_file(config_file)

    assert DEFAULT_COLLECTION_LOOKBACK_DAYS == 365
    assert config.days == 365
    expected_log_path = config_file.parent.parent / ".runtime" / "logs" / "collection_scheduler.log"
    assert config.log_path.resolve() == expected_log_path.resolve()

def test_scheduled_collection_runner_runs_once_and_writes_logs():
    test_dir = make_test_dir("scheduled_collection_once")
    config = CollectionScheduleConfig(
        symbols=["005930", "000660"],
        days=20,
        interval_minutes=30,
        log_path=test_dir / "collection.log",
    )

    calls: list[tuple[list[str], int]] = []

    def collector_fn(symbols: list[str], days: int) -> dict[str, object]:
        calls.append((symbols, days))
        return {
            "symbols": symbols,
            "success_count": 2,
            "failed_count": 0,
        }

    runner = ScheduledCollectionRunner(
        schedule=config,
        collector_fn=collector_fn,
        now_fn=lambda: datetime(2026, 5, 31, 15, 30, 0),
    )
    result = runner.run_once()

    assert calls == [(["005930", "000660"], 20)]
    assert result["success_count"] == 2

    lines = config.log_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 2
    assert json.loads(lines[0])["event"] == "collection_started"
    assert json.loads(lines[1])["event"] == "collection_finished"


def test_scheduled_collection_runner_calls_before_run_hook():
    test_dir = make_test_dir("scheduled_collection_before_run")
    config = CollectionScheduleConfig(
        symbols=["005930"],
        days=20,
        interval_minutes=30,
        log_path=test_dir / "collection.log",
    )
    before_run_calls: list[str] = []

    runner = ScheduledCollectionRunner(
        schedule=config,
        collector_fn=lambda symbols, days: {"symbols": symbols, "success_count": 1, "failed_count": 0},
        before_run_fn=lambda: before_run_calls.append("sync"),
        now_fn=lambda: datetime(2026, 5, 31, 15, 30, 0),
    )

    runner.run_once()

    assert before_run_calls == ["sync"]


def test_scheduled_collection_runner_logs_failure_and_preserves_it_for_status():
    test_dir = make_test_dir("scheduled_collection_failure")
    config_file = test_dir / "collection_schedule.yaml"
    config_file.write_text(
        "symbols:\n  - '005930'\nlog_path: runtime/collection.log\n",
        encoding="utf-8",
    )
    config = CollectionScheduleConfig.from_file(config_file)

    def failing_collector(symbols: list[str], days: int) -> dict[str, object]:
        raise RuntimeError("collector unavailable")

    runner = ScheduledCollectionRunner(
        schedule=config,
        collector_fn=failing_collector,
        now_fn=lambda: datetime(2026, 5, 31, 15, 30, 0),
    )

    with pytest.raises(RuntimeError, match="collector unavailable"):
        runner.run_once()

    status = load_schedule_status(config_file)
    assert status.last_event == "collection_failed"
    assert status.last_failed_at == "2026-05-31T15:30:00"
    assert status.last_error == "collector unavailable"
    assert [entry["event"] for entry in status.recent_entries or []] == [
        "collection_started",
        "collection_failed",
    ]


def test_scheduled_collection_runner_appends_across_runner_restarts():
    test_dir = make_test_dir("scheduled_collection_restart")
    config_file = test_dir / "collection_schedule.yaml"
    config_file.write_text("symbols:\n  - '005930'\nlog_path: runtime/collection.log\n", encoding="utf-8")
    schedule = CollectionScheduleConfig.from_file(config_file)
    collector = lambda symbols, days: {"symbols": symbols, "success_count": 1, "failed_count": 0}

    ScheduledCollectionRunner(schedule=schedule, collector_fn=collector).run_once()
    ScheduledCollectionRunner(schedule=schedule, collector_fn=collector).run_once()

    status = load_schedule_status(config_file)
    assert schedule.log_path.parent.resolve() == (test_dir / "runtime").resolve()
    assert status.total_logged_runs == 2
    assert len(status.recent_entries or []) == 4


def test_scheduled_collection_runner_repeats_with_interval_and_max_runs():
    test_dir = make_test_dir("scheduled_collection_loop")
    config = CollectionScheduleConfig(
        symbols=["005930"],
        days=10,
        interval_minutes=5,
        run_on_startup=False,
        log_path=test_dir / "collection.log",
    )

    collector_calls: list[int] = []
    sleep_calls: list[float] = []

    def collector_fn(symbols: list[str], days: int) -> dict[str, object]:
        collector_calls.append(days)
        return {
            "symbols": symbols,
            "success_count": 1,
            "failed_count": 0,
        }

    runner = ScheduledCollectionRunner(
        schedule=config,
        collector_fn=collector_fn,
        sleep_fn=lambda seconds: sleep_calls.append(seconds),
        now_fn=lambda: datetime(2026, 5, 31, 16, 0, 0),
    )

    completed_runs = runner.run_forever(max_runs=2)

    assert completed_runs == 2
    assert collector_calls == [10, 10]
    assert sleep_calls == [300, 300]


def test_load_schedule_status_summarizes_recent_log_entries():
    test_dir = make_test_dir("scheduled_collection_status")
    config_file = test_dir / "collection_schedule.yaml"
    config_file.write_text(
        "\n".join(
            [
                "symbols:",
                "  - '005930'",
                "days: 25",
                "interval_minutes: 120",
                "run_on_startup: true",
                "log_path: collection.log",
            ]
        ),
        encoding="utf-8",
    )
    log_file = test_dir / "collection.log"
    log_file.write_text(
        "\n".join(
            [
                json.dumps({"event": "collection_started", "started_at": "2026-05-31T09:00:00"}, ensure_ascii=False),
                json.dumps(
                    {
                        "event": "collection_finished",
                        "finished_at": "2026-05-31T09:00:10",
                        "success_count": 2,
                        "failed_count": 1,
                    },
                    ensure_ascii=False,
                ),
                json.dumps(
                    {
                        "event": "collection_waiting",
                        "next_run_at": "2026-05-31T11:00:10",
                        "wait_seconds": 7200,
                    },
                    ensure_ascii=False,
                ),
            ]
        ),
        encoding="utf-8",
    )

    status = load_schedule_status(config_file)

    assert status.log_exists is True
    assert status.schedule.symbols == ["005930"]
    assert status.last_event == "collection_waiting"
    assert status.last_started_at == "2026-05-31T09:00:00"
    assert status.last_finished_at == "2026-05-31T09:00:10"
    assert status.next_run_at == "2026-05-31T11:00:10"
    assert status.last_success_count == 2
    assert status.last_failed_count == 1
    assert status.total_logged_runs == 1
    assert status.recent_entries is not None
    assert len(status.recent_entries) == 3
