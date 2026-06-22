from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from invest_bot.market.repositories import StockMasterRepositoryProtocol
from invest_bot.market.stock_master import StockMasterRepository


@dataclass(frozen=True, slots=True)
class ResolvedSymbol:
    raw_input: str
    symbol: str
    symbol_name: str


@dataclass(frozen=True, slots=True)
class SymbolEntry:
    symbol: str
    symbol_name: str


class SymbolLookup:
    """Resolve a dashboard input value to a domestic stock symbol code."""

    def __init__(
        self,
        stock_info_dir: str | Path | None = None,
        master_repository: StockMasterRepositoryProtocol | None = None,
    ) -> None:
        _ = stock_info_dir
        self.master_repository = master_repository or StockMasterRepository()

    def resolve(self, value: str) -> ResolvedSymbol:
        raw = value.strip()
        if not raw:
            raise ValueError("종목코드 또는 종목명을 입력해 주세요.")

        if raw.isdigit():
            symbol = self._normalize_symbol_code(raw)
            return ResolvedSymbol(raw_input=raw, symbol=symbol, symbol_name=self._symbol_name_for_code(symbol))

        entry = self._find_by_name(raw, refresh_master=False)
        if entry is not None:
            return ResolvedSymbol(raw_input=raw, symbol=entry["symbol"], symbol_name=entry["symbol_name"])

        refresh_error: Exception | None = None
        try:
            self.master_repository.ensure_updated(force=True)
        except Exception as error:  # noqa: BLE001
            refresh_error = error

        entry = self._find_by_name(raw, refresh_master=False)
        if entry is not None:
            return ResolvedSymbol(raw_input=raw, symbol=entry["symbol"], symbol_name=entry["symbol_name"])

        if refresh_error is not None:
            raise ValueError(
                f"'{raw}'에 해당하는 종목명을 찾지 못했습니다. 종목 마스터 파일 갱신도 실패했습니다: {refresh_error}"
            ) from refresh_error

        raise ValueError(
            f"'{raw}'에 해당하는 종목명을 찾지 못했습니다. 종목코드로 입력하거나 종목명을 다시 확인해 주세요."
        )

    def resolve_many(self, values: list[str]) -> list[ResolvedSymbol]:
        resolved: list[ResolvedSymbol] = []
        seen: set[str] = set()
        for value in values:
            item = self.resolve(value)
            if item.symbol not in seen:
                resolved.append(item)
                seen.add(item.symbol)
        return resolved

    def list_entries(self, refresh_master: bool = False) -> list[SymbolEntry]:
        entries = self._load_entries(refresh_master=refresh_master, auto_update_if_missing=not refresh_master)
        unique_entries: dict[str, SymbolEntry] = {}
        for entry in entries:
            symbol = self._normalize_symbol_code(entry.get("symbol", ""))
            symbol_name = str(entry.get("symbol_name", "")).strip()
            if symbol and symbol_name and symbol not in unique_entries:
                unique_entries[symbol] = SymbolEntry(symbol=symbol, symbol_name=symbol_name)
        return sorted(unique_entries.values(), key=lambda item: (self._normalize(item.symbol_name), item.symbol))

    def _find_by_name(self, raw: str, refresh_master: bool) -> dict[str, str] | None:
        entries = self._load_entries(refresh_master=refresh_master, auto_update_if_missing=not refresh_master)
        normalized = self._normalize(raw)

        exact_matches = [entry for entry in entries if self._normalize(entry["symbol_name"]) == normalized]
        if len(exact_matches) == 1:
            return exact_matches[0]

        partial_matches = [entry for entry in entries if normalized in self._normalize(entry["symbol_name"])]
        unique_partial = {entry["symbol"]: entry for entry in partial_matches}
        if len(unique_partial) == 1:
            return next(iter(unique_partial.values()))

        if len(unique_partial) > 1:
            candidates = ", ".join(
                f"{entry['symbol_name']}({entry['symbol']})" for entry in list(unique_partial.values())[:5]
            )
            raise ValueError(
                f"'{raw}'에 해당하는 종목명이 여러 개 있습니다. 종목코드로 입력하거나 더 정확한 이름을 써 주세요: {candidates}"
            )
        return None

    def _load_entries(self, refresh_master: bool, auto_update_if_missing: bool) -> list[dict[str, str]]:
        if refresh_master:
            self.master_repository.ensure_updated(force=True)
        elif auto_update_if_missing:
            try:
                self.master_repository.ensure_updated(force=False)
            except Exception:
                pass

        entries: list[dict[str, str]] = []
        for entry in self.master_repository.load_entries():
            symbol = self._normalize_symbol_code(entry.get("symbol", ""))
            symbol_name = str(entry.get("symbol_name", "")).strip()
            if symbol and symbol_name:
                entries.append({"symbol": symbol, "symbol_name": symbol_name})
        return entries

    def _symbol_name_for_code(self, symbol: str) -> str:
        for entry in self._load_entries(refresh_master=False, auto_update_if_missing=False):
            if entry["symbol"] == symbol:
                return entry["symbol_name"]
        return ""

    @staticmethod
    def _normalize(value: str) -> str:
        return "".join(value.strip().lower().split())

    @staticmethod
    def _normalize_symbol_code(value: object) -> str:
        text = str(value).strip()
        if not text:
            return ""
        if text.isdigit():
            return text.zfill(6)
        return text
