from __future__ import annotations

import argparse
import json
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Callable

import yaml

from invest_bot.config.settings import CONFIG_DIR
from invest_bot.jobs.collect_market_data import collect_market_data_for_symbols


@dataclass(slots=True)
class CollectionScheduleConfig:
    symbols: list[str]
    days: int = 30
    interval_minutes: int = 1440
    run_on_startup: bool = True
    log_path: Path = Path("logs/collection_scheduler.log")

    @classmethod
    def from_file(cls, path: str | Path | None = None) -> "CollectionScheduleConfig":
        config_path = Path(path) if path is not None else CONFIG_DIR / "collection_schedule.yaml"
        if not config_path.exists():
            raise FileNotFoundError(
                f"Collection schedule file was not found: '{config_path}'. "
                "Copy config/collection_schedule.yaml.example to config/collection_schedule.yaml first."
            )

        payload = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
        raw_symbols = payload.get("symbols", [])
        symbols_file = payload.get("symbols_file")

        symbols = _normalize_symbols(raw_symbols)
        if symbols_file:
            symbols.extend(_load_symbols_from_file(config_path.parent / str(symbols_file)))
            symbols = _normalize_symbols(symbols)

        if not symbols:
            raise ValueError("Collection schedule must define at least one symbol.")

        log_path = Path(str(payload.get("log_path", "logs/collection_scheduler.log")))
        if not log_path.is_absolute():
            log_path = Path(__file__).resolve().parents[3] / log_path

        return cls(
            symbols=symbols,
            days=max(int(payload.get("days", 30)), 1),
            interval_minutes=max(int(payload.get("interval_minutes", 1440)), 1),
            run_on_startup=bool(payload.get("run_on_startup", True)),
            log_path=log_path,
        )


@dataclass(slots=True)
class ScheduledCollectionRunner:
    schedule: CollectionScheduleConfig
    collector_fn: Callable[[list[str], int], dict[str, object]] = collect_market_data_for_symbols
    sleep_fn: Callable[[float], None] = time.sleep
    now_fn: Callable[[], datetime] = datetime.now

    def run_once(self) -> dict[str, object]:
        started_at = self.now_fn()
        self._append_log(
            {
                "event": "collection_started",
                "started_at": started_at.isoformat(timespec="seconds"),
                "symbol_count": len(self.schedule.symbols),
                "days": self.schedule.days,
            }
        )
        result = self.collector_fn(symbols=self.schedule.symbols, days=self.schedule.days)
        finished_at = self.now_fn()
        self._append_log(
            {
                "event": "collection_finished",
                "finished_at": finished_at.isoformat(timespec="seconds"),
                "success_count": result.get("success_count", 0),
                "failed_count": result.get("failed_count", 0),
                "symbols": result.get("symbols", []),
            }
        )
        return result

    def run_forever(self, max_runs: int | None = None) -> int:
        completed_runs = 0
        if self.schedule.run_on_startup and _should_continue(completed_runs, max_runs):
            self.run_once()
            completed_runs += 1

        while _should_continue(completed_runs, max_runs):
            wait_seconds = self.schedule.interval_minutes * 60
            next_run_at = self.now_fn() + timedelta(seconds=wait_seconds)
            self._append_log(
                {
                    "event": "collection_waiting",
                    "next_run_at": next_run_at.isoformat(timespec="seconds"),
                    "wait_seconds": wait_seconds,
                }
            )
            self.sleep_fn(wait_seconds)
            self.run_once()
            completed_runs += 1
        return completed_runs

    def _append_log(self, payload: dict[str, object]) -> None:
        self.schedule.log_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.schedule.log_path, "a", encoding="utf-8") as file:
            file.write(json.dumps(payload, ensure_ascii=False) + "\n")


def _normalize_symbols(raw_symbols: object) -> list[str]:
    if isinstance(raw_symbols, str):
        values = [token.strip() for token in raw_symbols.replace(",", "\n").splitlines()]
    else:
        values = [str(token).strip() for token in (raw_symbols or [])]

    unique: list[str] = []
    seen: set[str] = set()
    for symbol in values:
        if symbol and symbol not in seen:
            unique.append(symbol)
            seen.add(symbol)
    return unique


def _load_symbols_from_file(path: Path) -> list[str]:
    if not path.exists():
        raise FileNotFoundError(f"Symbol list file was not found: '{path}'.")
    return _normalize_symbols(path.read_text(encoding="utf-8").splitlines())


def _should_continue(completed_runs: int, max_runs: int | None) -> bool:
    return max_runs is None or completed_runs < max_runs


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run scheduled domestic stock collection.")
    parser.add_argument("--config", dest="config_path", help="Optional path to a collection schedule YAML file.")
    parser.add_argument("--once", action="store_true", help="Run a single collection cycle and exit.")
    parser.add_argument("--max-runs", type=int, default=None, help="Optional max collection cycles before exit.")
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    schedule = CollectionScheduleConfig.from_file(args.config_path)
    runner = ScheduledCollectionRunner(schedule=schedule)

    if args.once:
        print(runner.run_once())
        return

    max_runs = None if args.max_runs is None else max(args.max_runs, 0)
    print(
        {
            "message": "scheduled collection started",
            "symbols": schedule.symbols,
            "days": schedule.days,
            "interval_minutes": schedule.interval_minutes,
            "run_on_startup": schedule.run_on_startup,
            "log_path": str(schedule.log_path),
            "max_runs": max_runs,
        }
    )
    runner.run_forever(max_runs=max_runs)
