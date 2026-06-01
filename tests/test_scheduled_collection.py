from __future__ import annotations

import json
from datetime import datetime

from invest_bot.jobs.scheduled_collection import CollectionScheduleConfig, ScheduledCollectionRunner, load_schedule_status
from tests.helpers import make_test_dir


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
