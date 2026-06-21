# invest_bot DB migration implementation-ready plan

## Objective

Align the DB/runtime implementation with the ownership rules below:

- `symbols` is the canonical stock reference table.
- only stock master sync updates `symbols`.
- user lookup/search/select must be read-only.
- `daily_prices` and `investor_daily` are collected fact tables.
- `dataset_frames` is an artifact/snapshot store, not a reference table.
- `stock_info_snapshots` is a deprecated candidate, not a canonical source.

## Current policy

| Area | Canonical table / source | User-triggered mutation allowed? |
| --- | --- | --- |
| Symbol code/name lookup | `symbols` + stock master file | No |
| Daily OHLCV facts | `daily_prices` | Yes, via collection jobs |
| Investor flow facts | `investor_daily` | Yes, via collection jobs |
| Raw/processed previews and outputs | `dataset_frames` | Yes, execution output only |
| Raw stock info history | `stock_info_snapshots` | No; removal candidate |

## Implementation phases

### 1. Canonical lookup enforcement

- dashboard symbol picker reads from `symbols` / stock master only
- `SymbolLookup` no longer resolves names from `stock_info`
- fallback `stock_info` values like `prdt_abrv_name == pdno` must not become lookup source

### 2. Write-boundary cleanup

- user lookup/search/select remains read-only
- `save_stock_info` fallback rows do not overwrite DB/file artifacts
- `stock_info` raw responses are not allowed to redefine canonical symbol names

### 3. Snapshot responsibility reduction

- `dataset_frames.stock_info` is treated as optional raw artifact only
- report/dashboard naming logic must not depend on `dataset_frames.stock_info`
- `symbols` remains the only canonical symbol-name source in product logic

### 4. Schema simplification follow-up

- review and remove remaining runtime dependency on `stock_info_snapshots`
- once unused, add migration to drop `stock_info_snapshots`
- keep `dataset_frames` focused on preview/report/analysis artifacts

## Deliverables

- ownership-aligned ERD
- repository responsibility document
- migration/operations notes reflecting canonical source boundaries
- regression tests that prove fallback stock info cannot pollute symbol lookup/display

## Risks

- legacy code paths may still assume `stock_info` is the fastest place to read a symbol name
- environments that skip stock master sync can still behave inconsistently until startup sync is guaranteed
- historical docs may describe old bootstrap behavior and need explicit archival labeling

## Verification checklist

- symbol picker / resolver uses `symbols` or stock master, not `stock_info`
- fallback stock info with `prdt_abrv_name == pdno` does not affect dashboard/report names
- collection still writes `daily_prices` and `investor_daily`
- docs consistently distinguish canonical tables from artifacts

## Handoff notes

- next schema-cleanup lane should decide when `stock_info_snapshots` can be dropped physically
- longer term, replace bootstrap-only migration flow with tracked Alembic revisions
