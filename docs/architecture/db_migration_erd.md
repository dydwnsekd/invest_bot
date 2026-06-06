# invest_bot DB migration ERD

## Goal

Migrate the current file-based market data flow to a PostgreSQL-backed schema without breaking the existing symbol lookup, collection, analysis, and dashboard workflows.

## Tables

### `symbols`

| Column | Type | Notes |
| --- | --- | --- |
| `id` | UUID | Primary key |
| `symbol_code` | VARCHAR(6) | Unique domestic stock code such as `005930` |
| `symbol_name` | TEXT | Canonical display name |
| `market` | TEXT | Market code such as `KOSPI` or `KOSDAQ` |
| `created_at` | TIMESTAMPTZ | Insert timestamp |
| `updated_at` | TIMESTAMPTZ | Last update timestamp |

### `daily_prices`

| Column | Type | Notes |
| --- | --- | --- |
| `id` | UUID | Primary key |
| `symbol_id` | UUID | Foreign key to `symbols.id` |
| `trade_date` | DATE | Trading session date |
| `open_price` | NUMERIC(18,4) | Opening price |
| `high_price` | NUMERIC(18,4) | High price |
| `low_price` | NUMERIC(18,4) | Low price |
| `close_price` | NUMERIC(18,4) | Closing price |
| `volume` | BIGINT | Traded volume |
| `created_at` | TIMESTAMPTZ | Insert timestamp |

### `stock_info_snapshots`

| Column | Type | Notes |
| --- | --- | --- |
| `id` | UUID | Primary key |
| `symbol_id` | UUID | Foreign key to `symbols.id` |
| `collected_at` | TIMESTAMPTZ | Snapshot collection timestamp |
| `raw_payload` | JSONB | Raw API payload for traceability |
| `source` | TEXT | Upstream source identifier |

### `analysis_runs`

| Column | Type | Notes |
| --- | --- | --- |
| `id` | UUID | Primary key |
| `symbol_id` | UUID | Foreign key to `symbols.id` |
| `analysis_type` | TEXT | Daily price analysis, report generation, or signal generation |
| `started_at` | TIMESTAMPTZ | Job start time |
| `completed_at` | TIMESTAMPTZ | Job completion time |
| `status` | TEXT | `started`, `completed`, or `failed` |
| `artifacts` | JSONB | Output file paths or generated summary metadata |

## Relationships

- `symbols` 1:N `daily_prices`
- `symbols` 1:N `stock_info_snapshots`
- `symbols` 1:N `analysis_runs`

## Constraints

- `symbols.symbol_code` must be unique and remain zero-padded to six digits.
- `daily_prices` must be unique on `(symbol_id, trade_date)` to preserve idempotent re-collection.
- Foreign keys must use `ON DELETE RESTRICT` for audit safety.
- UTC timestamps are required for all job and snapshot records.

## Mapping from current file-based artifacts

- `data/reference/stock_master.csv` -> `symbols`
- `data/raw/domestic_stock/daily_prices/*.csv` -> `daily_prices`
- `data/raw/domestic_stock/stock_info/*.csv` -> `stock_info_snapshots`
- generated reports / signal metadata -> `analysis_runs.artifacts`
