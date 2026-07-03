from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from invest_bot.config.settings import AppSettings
from invest_bot.db.engine import build_engine, build_session_factory
from invest_bot.db.repositories import SqlAlchemyReportFavoriteSymbolRepository, normalize_symbol


@dataclass(frozen=True, slots=True)
class FavoriteSymbolRecord:
    symbol: str
    created_at: str


class ReportFavoritesStore:
    def __init__(
        self,
        repository: SqlAlchemyReportFavoriteSymbolRepository | str | Path | None = None,
        *,
        settings: AppSettings | None = None,
    ) -> None:
        resolved_repository = repository
        if isinstance(repository, str | Path):
            resolved_repository = None
        self.repository = resolved_repository or self._build_repository(settings)

    @staticmethod
    def _build_repository(settings: AppSettings | None) -> SqlAlchemyReportFavoriteSymbolRepository:
        resolved = settings or AppSettings.from_file()
        database_url = resolved.database_url.strip()
        if not database_url:
            raise RuntimeError("ReportFavoritesStore requires a configured database_url for DB-backed persistence.")
        engine = build_engine(database_url)
        return SqlAlchemyReportFavoriteSymbolRepository(build_session_factory(engine))

    def load(self) -> list[FavoriteSymbolRecord]:
        return [
            FavoriteSymbolRecord(symbol=record.symbol, created_at=record.created_at.isoformat())
            for record in self.repository.load_all()
        ]

    def load_symbols(self) -> set[str]:
        return {record.symbol for record in self.load()}

    def is_favorite(self, symbol: str) -> bool:
        normalized = normalize_symbol(symbol)
        return bool(normalized) and normalized in self.load_symbols()

    def add(self, symbol: str) -> bool:
        return self.repository.add(symbol)

    def remove(self, symbol: str) -> bool:
        return self.repository.remove(symbol)

    def toggle(self, symbol: str) -> bool:
        if self.is_favorite(symbol):
            self.remove(symbol)
            return False
        self.add(symbol)
        return True
