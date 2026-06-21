from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Callable

from invest_bot.config.settings import AppSettings
from invest_bot.db.contracts import StockRecord, StockRepository
from invest_bot.db.engine import build_engine, build_session_factory
from invest_bot.db.repositories import SqlAlchemyStockRepository
from invest_bot.market.repositories import StockMasterRepositoryProtocol
from invest_bot.market.stock_master import StockMasterRepository


@dataclass(frozen=True, slots=True)
class StockMasterSyncResult:
    refreshed: bool
    used_fallback_file: bool
    db_synced: bool
    entry_count: int
    sync_started_at: datetime
    source_path: Path
    refresh_error: str = ""


class StockMasterSyncService:
    def __init__(
        self,
        *,
        settings: AppSettings | None = None,
        master_repository: StockMasterRepositoryProtocol | None = None,
        stock_repository: StockRepository | None = None,
        state_file: str | Path | None = None,
        now_fn: Callable[[], datetime] | None = None,
    ) -> None:
        self.settings = settings or AppSettings.from_file()
        self.master_repository = master_repository or StockMasterRepository()
        self.stock_repository = stock_repository if stock_repository is not None else self._build_stock_repository()
        self.now_fn = now_fn or (lambda: datetime.now(UTC))
        default_state_file = Path("data/reference/stock_master_sync_state.json")
        path = Path(state_file) if state_file is not None else default_state_file
        if path.is_absolute():
            self.state_file = path
        else:
            project_root = Path(__file__).resolve().parents[3]
            self.state_file = project_root / path

    def sync(self, *, force_refresh: bool = False) -> StockMasterSyncResult:
        sync_started_at = self.now_fn()
        should_refresh = force_refresh or self._should_refresh(sync_started_at)
        refreshed = False
        used_fallback_file = False
        refresh_error = ""
        source_path = self.master_repository.ensure_updated(force=False)

        if should_refresh:
            try:
                source_path = self.master_repository.ensure_updated(force=True)
                refreshed = True
            except Exception as error:  # noqa: BLE001
                refresh_error = str(error)
                source_path = self.master_repository.ensure_updated(force=False)
                used_fallback_file = source_path.exists()
                if not used_fallback_file:
                    raise

        entries = self.master_repository.load_entries()
        db_synced = False
        if self.stock_repository is not None:
            for entry in entries:
                self.stock_repository.upsert(
                    StockRecord(
                        symbol=str(entry.get("symbol", "")).strip(),
                        symbol_name=str(entry.get("symbol_name", "")).strip(),
                        market=str(entry.get("market", "")).strip() or "unknown",
                    )
                )
            db_synced = True

        result = StockMasterSyncResult(
            refreshed=refreshed,
            used_fallback_file=used_fallback_file,
            db_synced=db_synced,
            entry_count=len(entries),
            sync_started_at=sync_started_at,
            source_path=source_path,
            refresh_error=refresh_error,
        )
        self._write_state(result)
        return result

    def _build_stock_repository(self) -> StockRepository | None:
        if not self.settings.enable_db_write:
            return None
        engine = build_engine(self.settings.database_url)
        session_factory = build_session_factory(engine)
        return SqlAlchemyStockRepository(session_factory)

    def _should_refresh(self, now: datetime) -> bool:
        payload = self._read_state()
        last_synced_at = str(payload.get("last_synced_at", "")).strip()
        if not last_synced_at:
            return True
        try:
            previous = datetime.fromisoformat(last_synced_at)
        except ValueError:
            return True
        if previous.tzinfo is None:
            previous = previous.replace(tzinfo=UTC)
        interval = timedelta(minutes=self.settings.stock_master_refresh_interval_minutes)
        return previous + interval <= now

    def _read_state(self) -> dict[str, object]:
        if not self.state_file.exists():
            return {}
        try:
            return json.loads(self.state_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}

    def _write_state(self, result: StockMasterSyncResult) -> None:
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "last_synced_at": result.sync_started_at.isoformat(),
            "refreshed": result.refreshed,
            "used_fallback_file": result.used_fallback_file,
            "db_synced": result.db_synced,
            "entry_count": result.entry_count,
            "source_path": str(result.source_path),
            "refresh_error": result.refresh_error,
        }
        self.state_file.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def sync_stock_master(*, force_refresh: bool = False, settings: AppSettings | None = None) -> StockMasterSyncResult:
    service = StockMasterSyncService(settings=settings)
    return service.sync(force_refresh=force_refresh)
