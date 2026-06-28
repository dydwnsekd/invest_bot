from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path


@dataclass(frozen=True, slots=True)
class FavoriteSymbolRecord:
    symbol: str
    created_at: str


class ReportFavoritesStore:
    VERSION = 1

    def __init__(self, state_file: str | Path | None = None) -> None:
        default_state_file = Path("data/reference/report_favorites_state.json")
        path = Path(state_file) if state_file is not None else default_state_file
        if path.is_absolute():
            self.state_file = path
        else:
            project_root = Path(__file__).resolve().parents[3]
            self.state_file = project_root / path

    def load(self) -> list[FavoriteSymbolRecord]:
        payload = self._read_payload()
        if payload.get("version") != self.VERSION:
            return []

        records: list[FavoriteSymbolRecord] = []
        seen: set[str] = set()
        raw_records = payload.get("favorite_symbols", [])
        if not isinstance(raw_records, list):
            return []
        for item in raw_records:
            if not isinstance(item, dict):
                continue
            symbol = str(item.get("symbol", "")).strip()
            created_at = str(item.get("created_at", "")).strip()
            if not symbol or symbol in seen:
                continue
            seen.add(symbol)
            records.append(FavoriteSymbolRecord(symbol=symbol, created_at=created_at))
        return records

    def load_symbols(self) -> set[str]:
        return {record.symbol for record in self.load()}

    def is_favorite(self, symbol: str) -> bool:
        normalized = str(symbol).strip()
        return bool(normalized) and normalized in self.load_symbols()

    def add(self, symbol: str) -> bool:
        normalized = str(symbol).strip()
        if not normalized:
            return False
        records = self.load()
        if any(record.symbol == normalized for record in records):
            return False
        records.append(
            FavoriteSymbolRecord(
                symbol=normalized,
                created_at=datetime.now(UTC).isoformat(),
            )
        )
        self._write(records)
        return True

    def remove(self, symbol: str) -> bool:
        normalized = str(symbol).strip()
        if not normalized:
            return False
        records = self.load()
        filtered = [record for record in records if record.symbol != normalized]
        if len(filtered) == len(records):
            return False
        self._write(filtered)
        return True

    def toggle(self, symbol: str) -> bool:
        if self.is_favorite(symbol):
            self.remove(symbol)
            return False
        self.add(symbol)
        return True

    def _read_payload(self) -> dict[str, object]:
        if not self.state_file.exists():
            return {}
        try:
            raw = json.loads(self.state_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}
        return raw if isinstance(raw, dict) else {}

    def _write(self, records: list[FavoriteSymbolRecord]) -> None:
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "version": self.VERSION,
            "favorite_symbols": [
                {
                    "symbol": record.symbol,
                    "created_at": record.created_at,
                }
                for record in records
            ],
        }
        temp_path = self.state_file.with_suffix(f"{self.state_file.suffix}.tmp")
        temp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(temp_path, self.state_file)
