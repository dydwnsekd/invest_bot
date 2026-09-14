import argparse
import os
import sys
from collections.abc import Sequence
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"

if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from invest_bot.db.migrate_runtime import migrate
from invest_bot.market.master_sync import sync_stock_master


INIT_MODE_ENV = "INVEST_BOT_INIT_MODE"
FULL_MODE = "full"
MIGRATE_ONLY_MODE = "migrate-only"
INIT_MODES = (FULL_MODE, MIGRATE_ONLY_MODE)


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Apply database migrations and optionally refresh the external stock master."
    )
    parser.add_argument(
        "--mode",
        choices=INIT_MODES,
        default=None,
        help=(
            "Initialization mode. Defaults to INVEST_BOT_INIT_MODE when set, otherwise 'full' "
            "for backward compatibility."
        ),
    )
    args = parser.parse_args(argv)
    env_mode = os.getenv(INIT_MODE_ENV, "").strip().lower()
    args.mode = args.mode or env_mode or FULL_MODE
    if args.mode not in INIT_MODES:
        parser.error(f"{INIT_MODE_ENV} must be one of: {', '.join(INIT_MODES)}")
    return args


def main(argv: Sequence[str] | None = None) -> None:
    args = _parse_args(argv)
    migrate()
    print("database migration complete")

    if args.mode == MIGRATE_ONLY_MODE:
        print("stock master sync skipped (migration-only mode)")
        return

    sync_stock_master(force_refresh=True)
    print("database initialization complete")


if __name__ == "__main__":
    main()
