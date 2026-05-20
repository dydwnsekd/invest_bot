from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd


@dataclass(frozen=True, slots=True)
class ResolvedSymbol:
    raw_input: str
    symbol: str
    symbol_name: str


class SymbolLookup:
    """Resolve a dashboard input value to a domestic stock symbol code."""

    def __init__(self, stock_info_dir: str | Path = "data/raw/domestic_stock/stock_info") -> None:
        stock_dir = Path(stock_info_dir)
        if stock_dir.is_absolute():
            self.stock_info_dir = stock_dir
        else:
            project_root = Path(__file__).resolve().parents[3]
            self.stock_info_dir = project_root / stock_dir

    def resolve(self, value: str) -> ResolvedSymbol:
        raw = value.strip()
        if not raw:
            raise ValueError("종목코드 또는 종목명을 입력해 주세요.")

        if raw.isdigit():
            return ResolvedSymbol(raw_input=raw, symbol=raw, symbol_name=self._symbol_name_for_code(raw))

        entries = self._load_entries()
        normalized = self._normalize(raw)

        exact_matches = [entry for entry in entries if self._normalize(entry["symbol_name"]) == normalized]
        if len(exact_matches) == 1:
            entry = exact_matches[0]
            return ResolvedSymbol(raw_input=raw, symbol=entry["symbol"], symbol_name=entry["symbol_name"])

        partial_matches = [entry for entry in entries if normalized in self._normalize(entry["symbol_name"])]
        unique_partial = {entry["symbol"]: entry for entry in partial_matches}
        if len(unique_partial) == 1:
            entry = next(iter(unique_partial.values()))
            return ResolvedSymbol(raw_input=raw, symbol=entry["symbol"], symbol_name=entry["symbol_name"])

        if len(unique_partial) > 1:
            candidates = ", ".join(
                f"{entry['symbol_name']}({entry['symbol']})" for entry in list(unique_partial.values())[:5]
            )
            raise ValueError(
                f"'{raw}'에 해당하는 종목명이 여러 개 있습니다. 종목코드로 입력하거나 더 정확한 이름을 써 주세요: {candidates}"
            )

        raise ValueError(
            f"'{raw}'에 해당하는 종목명을 찾지 못했습니다. 아직 수집한 적 없는 종목이면 종목코드로 먼저 입력해 주세요."
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

    def _load_entries(self) -> list[dict[str, str]]:
        if not self.stock_info_dir.exists():
            return []

        entries: list[dict[str, str]] = []
        for csv_file in sorted(self.stock_info_dir.glob("*.csv")):
            try:
                frame = pd.read_csv(csv_file)
            except pd.errors.EmptyDataError:
                continue
            if frame.empty:
                continue

            symbol_value = frame.iloc[0].get("pdno", "")
            symbol = self._normalize_symbol_code(symbol_value) or self._normalize_symbol_code(csv_file.stem)
            symbol_name = str(frame.iloc[0].get("prdt_abrv_name", "")).strip()
            if symbol and symbol_name:
                entries.append({"symbol": symbol, "symbol_name": symbol_name})
        return entries

    def _symbol_name_for_code(self, symbol: str) -> str:
        for entry in self._load_entries():
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
