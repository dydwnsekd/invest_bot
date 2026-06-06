# invest_bot DB Migration Plan Draft

## Goal

Create an implementation-ready migration path from the current CSV-first workflow to a Postgres-backed persistence layer without breaking existing collection, dashboard, and test flows.

## What is now finalized

1. **ERD draft**: `docs/operations/db_erd.md`
2. **Runtime DB config seam**: `src/invest_bot/config/settings.py`
3. **Repository contracts**: `src/invest_bot/db/contracts.py`
4. **Draft compose validation entrypoint**: `python -m invest_bot.db.bootstrap --json`

## Phase plan

### Phase 1 — preserve the current system while adding DB seams
- Keep CSV storage as the active production path.
- Read DB connection values from `.env` / runtime environment.
- Define repository contracts before selecting ORM details.
- Use the draft compose migration container only as a readiness check.

### Phase 2 — implement adapters
- Add SQLAlchemy, Alembic, and a Postgres driver.
- Implement repository adapters for `stocks`, `daily_prices`, `investor_daily_flows`, and `market_reports`.
- Keep dual-write or backfill tooling until dashboard and analysis reads are migrated.

### Phase 3 — switch consumers incrementally
- Migrate collector writes behind repositories.
- Migrate dashboard read paths behind repositories or a query service.
- Retire direct filesystem assumptions only after regression coverage passes.

## Known hazards

- Current `dashboard/service.py` and related tests assume filesystem datasets.
- Current collector writes directly to CSV via `CsvStorage`.
- No Alembic/SQLAlchemy toolchain exists yet, so real DB migrations must stay disabled until Phase 2 lands.

## Done definition for the next implementation lane

- add DB dependencies
- create initial ORM models matching the ERD
- add first Alembic revision
- implement one concrete repository adapter end to end
- keep CSV-based regression tests green or replace them with equivalent DB-backed coverage
