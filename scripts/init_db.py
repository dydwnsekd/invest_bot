from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"

if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from invest_bot.db.migrate_runtime import migrate
from invest_bot.market.master_sync import sync_stock_master


def main() -> None:
    migrate()
    sync_stock_master(force_refresh=True)
    print("database initialization complete")


if __name__ == "__main__":
    main()
