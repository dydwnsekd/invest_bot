# invest_bot repository interfaces for DB migration

## Goal

Introduce DB-backed repositories behind stable contracts so the existing jobs and dashboard consumers can migrate incrementally from CSV files to PostgreSQL.

## Repository contracts

현재 코드 기준 DB contract는 `src/invest_bot/db/contracts.py`를 canonical source로 본다.

### `StockRepository`

- `upsert(record: StockRecord) -> None`
- `get_by_symbol(symbol: str) -> StockRecord | None`
- `list_all() -> Sequence[StockRecord]`

### `DailyPriceRepository`

- `replace_for_symbol(symbol: str, records: Sequence[DailyPriceRecord]) -> None`
- `list_for_symbol(symbol: str, limit: int | None = None) -> Sequence[DailyPriceRecord]`
- `latest_trade_date(symbol: str) -> date | None`

### `StockInfoRepository`

- 이 문서 시점에는 별도 protocol로 분리되지 않았고, ORM table은 `stock_info_snapshots`로 준비돼 있다.
- 다음 단계에서 snapshot save/load contract를 별도 protocol로 분리할 수 있다.

### `InvestorDailyRepository`

- `replace_for_symbol(symbol: str, records: Sequence[InvestorDailyRecord]) -> None`
- `list_for_symbol(symbol: str, limit: int | None = None) -> Sequence[InvestorDailyRecord]`
- `latest_trade_date(symbol: str) -> date | None`

### `MarketReportRepository`

- `save(record: MarketReportRecord) -> None`
- `latest_for_symbol(symbol: str) -> MarketReportRecord | None`

## Compatibility rules

- Constructor injection must stay available for `SymbolLookup` and future service classes.
- Current CSV-backed classes remain valid adapters until DB repositories fully replace them.
- Symbol code normalization must stay centralized and preserve six-digit zero padding.
- Missing data paths must keep returning empty results or explicit domain errors instead of low-level DB exceptions.

## Initial adapter strategy

1. Keep `StockMasterRepository` as the first adapter for symbol catalog lookups.
2. Introduce PostgreSQL repositories alongside existing CSV storage.
3. Introduce duplicate-collection guards with `latest_trade_date()` plus DB unique constraints.
4. Migrate read paths behind feature flags or constructor wiring.
5. Replace direct file writes only after parity tests pass.
