# Project Rules

## Scope

- Market: domestic stocks only
- Modes: mock trading and live trading
- Language: Python 3.13
- Package management: `pip`
- Testing: `pytest`

## Implementation priorities

1. Safety
2. Validation
3. Simplicity
4. Extensibility

## Required habits

- Read `agent.md` before major implementation work.
- Read `README.md` before changing project structure or setup.
- Inspect `reference/open-trading-api` before implementing API-facing features.
- Update `README.md` when structure, setup, or behavior changes.
- Keep dependency decisions aligned with the current project scope; use reference dependency files only as early guidance.

## Architecture rules

- Keep strategy, trading, and data collection modules separate.
- Keep mock trading and live trading execution paths separate.
- Prefer project-specific wrappers over direct reuse of reference scripts.
- Keep secrets outside the repository.
- Treat the database as the default persistence authority for collected and processed datasets.
- Keep schema creation and upgrades in migrations or explicit init scripts; runtime constructors must not call `create_all()`.
- Keep DB snapshot persistence (`dataset_frames`) and normalized table writes as separate responsibilities with explicit flags and failure boundaries.
- When a UI or service accepts injected storage or roots, helper functions must preserve that caller context instead of reopening default runtime state.

## Safety rules

- Never assume reference example code is safe for live trading as-is.
- Add a validation path before extending order placement logic.
- Favor incremental delivery: data collection, backtest, mock trading, then live trading hardening.
