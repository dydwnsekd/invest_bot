# invest_bot DB migration implementation-ready plan

## Objective

Replace the current file-oriented persistence path with a PostgreSQL-backed data model that preserves existing collection, lookup, analysis, and dashboard behaviors.

## Scope

- PostgreSQL service lifecycle in `docker-compose.yml`
- Alembic-based schema migrations
- Repository interfaces for symbols, prices, stock info snapshots, and analysis runs
- Compatibility path from CSV-backed repositories to DB-backed repositories

## Phases

1. **Schema bootstrap**
   - add Alembic configuration and initial revision for `symbols`, `daily_prices`, `stock_info_snapshots`, and `analysis_runs`
   - add local DB settings parsing and connection bootstrap
2. **Repository adapters**
   - formalize repository protocols
   - implement PostgreSQL repositories alongside current CSV adapters
   - preserve constructor injection for existing consumers
3. **Consumer migration**
   - move collection jobs to DB writes
   - move lookup and dashboard reads to repository interfaces
   - keep CSV fallback only where explicitly needed during rollout
4. **Operational verification**
   - run migrations from a clean Postgres container
   - verify scheduler/web start only after migration success
   - verify lookup and collection regression coverage against repository contracts

## Deliverables

- ERD document for table shape and relationships
- repository interface contract document
- docker-compose draft wired for db -> migrate -> app startup ordering
- automated tests that lock the compose contract and required migration docs

## Risks

- `docker-compose.yml` currently references an Alembic command before Alembic config is checked in
- shared runtime files such as `docker-compose.yml`, `Dockerfile`, and `settings.py` are high-collision surfaces
- DB migration can break current CSV-relative path assumptions if adapter boundaries are not preserved

## Verification checklist

- parse `docker-compose.yml` successfully
- confirm `.env.example` includes DB runtime variables
- confirm migration docs exist and include ERD, repository, and phased plan sections
- run targeted repository/config tests plus full pytest suite after changes

## Handoff notes

- The next implementation lane should add Alembic config and DB settings before enabling the `migrate` service in end-to-end runtime tests.
- Existing `StockMasterRepository` and `CsvStorage` remain the compatibility baseline for parity tests.
