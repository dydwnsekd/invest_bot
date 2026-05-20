from __future__ import annotations

import csv
import urllib.request
import zipfile
from io import BytesIO
from pathlib import Path

import pandas as pd


class StockMasterRepository:
    """Manage a local domestic stock master file used for symbol-name lookup."""

    MASTER_URLS = {
        "KOSPI": "https://new.real.download.dws.co.kr/common/master/kospi_code.mst.zip",
        "KOSDAQ": "https://new.real.download.dws.co.kr/common/master/kosdaq_code.mst.zip",
    }

    def __init__(self, master_file: str | Path = "data/reference/stock_master.csv") -> None:
        path = Path(master_file)
        if path.is_absolute():
            self.master_file = path
        else:
            project_root = Path(__file__).resolve().parents[3]
            self.master_file = project_root / path

    def load_entries(self) -> list[dict[str, str]]:
        if not self.master_file.exists():
            return []

        frame = pd.read_csv(self.master_file, dtype={"symbol": str})
        if frame.empty:
            return []

        entries: list[dict[str, str]] = []
        for row in frame.to_dict(orient="records"):
            symbol = self._normalize_symbol_code(row.get("symbol", ""))
            symbol_name = str(row.get("symbol_name", "")).strip()
            market = str(row.get("market", "")).strip()
            if symbol and symbol_name:
                entries.append({"symbol": symbol, "symbol_name": symbol_name, "market": market})
        return entries

    def ensure_updated(self, force: bool = False) -> Path:
        if self.master_file.exists() and not force:
            return self.master_file
        entries = self._download_entries()
        return self.write_entries(entries)

    def write_entries(self, entries: list[dict[str, str]]) -> Path:
        self.master_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.master_file, "w", newline="", encoding="utf-8-sig") as file:
            writer = csv.DictWriter(file, fieldnames=["symbol", "symbol_name", "market"])
            writer.writeheader()
            for entry in entries:
                writer.writerow(
                    {
                        "symbol": self._normalize_symbol_code(entry.get("symbol", "")),
                        "symbol_name": str(entry.get("symbol_name", "")).strip(),
                        "market": str(entry.get("market", "")).strip(),
                    }
                )
        return self.master_file

    def _download_entries(self) -> list[dict[str, str]]:
        merged: dict[str, dict[str, str]] = {}
        for market, url in self.MASTER_URLS.items():
            content = self._download_and_extract(url)
            for entry in self._parse_master_file(content, market):
                merged[entry["symbol"]] = entry
        return sorted(merged.values(), key=lambda item: item["symbol"])

    @staticmethod
    def _download_and_extract(url: str) -> bytes:
        with urllib.request.urlopen(url, timeout=60) as response:
            content = response.read()

        try:
            with zipfile.ZipFile(BytesIO(content)) as archive:
                names = archive.namelist()
                if not names:
                    return content
                return archive.read(names[0])
        except zipfile.BadZipFile:
            return content

    @classmethod
    def _parse_master_file(cls, content: bytes, market: str) -> list[dict[str, str]]:
        entries: list[dict[str, str]] = []
        for line_bytes in content.split(b"\n"):
            if len(line_bytes) < 61:
                continue

            raw_code = line_bytes[0:9].decode("euc-kr", errors="ignore").strip()
            raw_name = line_bytes[21:61].decode("euc-kr", errors="ignore").strip()
            symbol = cls._normalize_symbol_code(raw_code[-6:] if len(raw_code) > 6 else raw_code)
            if symbol and raw_name and symbol.isdigit():
                entries.append({"symbol": symbol, "symbol_name": raw_name, "market": market})
        return entries

    @staticmethod
    def _normalize_symbol_code(value: object) -> str:
        text = str(value).strip()
        if not text:
            return ""
        if text.isdigit():
            return text.zfill(6)
        return text
