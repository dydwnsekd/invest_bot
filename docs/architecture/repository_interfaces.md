# invest_bot repository interfaces for DB migration

## Goal

Introduce DB-backed repositories behind stable contracts so the existing jobs and dashboard consumers can migrate incrementally from CSV files to PostgreSQL.

## Repository contracts

### `SymbolRepository`

- `get_by_code(symbol_code: str) -> dict[str, str] | None`
- `find_by_name(name: str) -> list[dict[str, str]]`
- `upsert_many(entries: list[dict[str, str]]) -> int`

### `DailyPriceRepository`

- `save_prices(symbol_code: str, rows: list[dict[str, object]]) -> int`
- `load_prices(symbol_code: str, start_date: str | None = None, end_date: str | None = None) -> list[dict[str, object]]`
- `latest_trade_date(symbol_code: str) -> str | None`

### `StockInfoRepository`

- `save_snapshot(symbol_code: str, payload: dict[str, object], collected_at: str) -> None`
- `latest_snapshot(symbol_code: str) -> dict[str, object] | None`

### `AnalysisRunRepository`

- `start_run(symbol_code: str, analysis_type: str) -> str`
- `complete_run(run_id: str, artifacts: dict[str, object]) -> None`
- `fail_run(run_id: str, reason: str) -> None`

## Compatibility rules

- Constructor injection must stay available for `SymbolLookup` and future service classes.
- Current CSV-backed classes remain valid adapters until DB repositories fully replace them.
- Symbol code normalization must stay centralized and preserve six-digit zero padding.
- Missing data paths must keep returning empty results or explicit domain errors instead of low-level DB exceptions.

## Initial adapter strategy

1. Keep `StockMasterRepository` as the first adapter for `SymbolRepository`.
2. Introduce PostgreSQL repositories alongside existing CSV storage.
3. Migrate read paths behind feature flags or constructor wiring.
4. Remove direct file writes only after parity tests pass.
