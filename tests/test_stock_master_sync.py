from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from invest_bot.config.settings import AppSettings
from invest_bot.db.contracts import StockRecord
from invest_bot.market.master_sync import StockMasterSyncService
from tests.helpers import make_test_dir


class StubStockMasterRepository:
    def __init__(self, master_file: Path, entries: list[dict[str, str]], *, fail_force_refresh: bool = False) -> None:
        self.master_file = master_file
        self._entries = entries
        self.fail_force_refresh = fail_force_refresh
        self.ensure_updated_calls: list[bool] = []
        self.master_file.parent.mkdir(parents=True, exist_ok=True)
        self.master_file.write_text("seed", encoding="utf-8")

    def load_entries(self) -> list[dict[str, str]]:
        return self._entries

    def ensure_updated(self, force: bool = False) -> Path:
        self.ensure_updated_calls.append(force)
        if force and self.fail_force_refresh:
            raise RuntimeError("download failed")
        return self.master_file


class StubStockRepository:
    def __init__(self) -> None:
        self.records: dict[str, StockRecord] = {}

    def upsert(self, record: StockRecord) -> None:
        self.records[record.symbol] = record

    def get_by_symbol(self, symbol: str) -> StockRecord | None:
        return self.records.get(symbol)

    def list_all(self):
        return list(self.records.values())


def test_stock_master_sync_force_refresh_updates_db_and_state():
    test_dir = make_test_dir("stock_master_sync_force")
    state_file = test_dir / "stock_master_sync_state.json"
    repo = StubStockMasterRepository(
        test_dir / "stock_master.csv",
        [
            {"symbol": "005930", "symbol_name": "삼성전자", "market": "KOSPI"},
            {"symbol": "000660", "symbol_name": "SK하이닉스", "market": "KOSPI"},
        ],
    )
    stock_repo = StubStockRepository()
    settings = AppSettings(enable_db_write=False)
    service = StockMasterSyncService(
        settings=settings,
        master_repository=repo,
        stock_repository=stock_repo,
        state_file=state_file,
        now_fn=lambda: datetime(2026, 6, 19, 13, 0, 0, tzinfo=UTC),
    )

    result = service.sync(force_refresh=True)

    assert result.refreshed is True
    assert result.db_synced is True
    assert result.entry_count == 2
    assert repo.ensure_updated_calls == [False, True]
    assert stock_repo.get_by_symbol("005930") == StockRecord(symbol="005930", symbol_name="삼성전자", market="KOSPI")
    payload = json.loads(state_file.read_text(encoding="utf-8"))
    assert payload["entry_count"] == 2
    assert payload["refreshed"] is True


def test_stock_master_sync_skips_refresh_when_recent_but_still_syncs_db():
    test_dir = make_test_dir("stock_master_sync_recent")
    state_file = test_dir / "stock_master_sync_state.json"
    state_file.write_text(
        json.dumps({"last_synced_at": "2026-06-19T12:30:00+00:00"}, ensure_ascii=False),
        encoding="utf-8",
    )
    repo = StubStockMasterRepository(
        test_dir / "stock_master.csv",
        [{"symbol": "005930", "symbol_name": "삼성전자", "market": "KOSPI"}],
    )
    stock_repo = StubStockRepository()
    settings = AppSettings(enable_db_write=False, stock_master_refresh_interval_minutes=1440)
    service = StockMasterSyncService(
        settings=settings,
        master_repository=repo,
        stock_repository=stock_repo,
        state_file=state_file,
        now_fn=lambda: datetime(2026, 6, 19, 13, 0, 0, tzinfo=UTC),
    )

    result = service.sync()

    assert result.refreshed is False
    assert repo.ensure_updated_calls == [False]
    assert stock_repo.get_by_symbol("005930") == StockRecord(symbol="005930", symbol_name="삼성전자", market="KOSPI")


def test_stock_master_sync_uses_local_file_when_refresh_fails():
    test_dir = make_test_dir("stock_master_sync_fallback")
    state_file = test_dir / "stock_master_sync_state.json"
    repo = StubStockMasterRepository(
        test_dir / "stock_master.csv",
        [{"symbol": "005930", "symbol_name": "삼성전자", "market": "KOSPI"}],
        fail_force_refresh=True,
    )
    stock_repo = StubStockRepository()
    service = StockMasterSyncService(
        settings=AppSettings(enable_db_write=False),
        master_repository=repo,
        stock_repository=stock_repo,
        state_file=state_file,
        now_fn=lambda: datetime(2026, 6, 19, 13, 0, 0, tzinfo=UTC),
    )

    result = service.sync(force_refresh=True)

    assert result.refreshed is False
    assert result.used_fallback_file is True
    assert "download failed" in result.refresh_error
    assert stock_repo.get_by_symbol("005930") == StockRecord(symbol="005930", symbol_name="삼성전자", market="KOSPI")
