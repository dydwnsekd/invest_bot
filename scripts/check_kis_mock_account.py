"""Run a read-only connection check with an explicitly supplied KIS mock token."""
import argparse
from datetime import datetime, timezone
import os
from pathlib import Path
import sys
from time import sleep

from requests import Session

SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from invest_bot.clients.kis_order_client import (
    KISMockBoundaryError,
    KISMockCredentials,
    KISMockOrderClient,
    MOCK_BASE_URL,
)


MOCK_INPUTS = (
    "INVEST_BOT_KIS_MOCK_ACCOUNT_NUMBER",
    "INVEST_BOT_KIS_MOCK_APP_KEY",
    "INVEST_BOT_KIS_MOCK_APP_SECRET",
    "INVEST_BOT_KIS_MOCK_ACCESS_TOKEN",
    "INVEST_BOT_KIS_MOCK_TOKEN_EXPIRES_AT",
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args(argv)
    values = [os.environ.get(name, "") for name in MOCK_INPUTS]
    missing = [name for name, value in zip(MOCK_INPUTS, values) if not value.strip()]
    if missing:
        print("Missing mock inputs: " + ", ".join(missing))
        return 2

    account, key, secret, token, expiry = values
    try:
        credentials = KISMockCredentials(account, key, secret, token, datetime.fromisoformat(expiry))
    except ValueError:
        print("Invalid mock token expiry. Use ISO 8601 with a timezone.")
        return 2

    with Session() as session:
        session.trust_env = False
        try:
            client = KISMockOrderClient(
                credentials=credentials, alias="mock-check", binding_version="v1",
                mode="mock", base_url=MOCK_BASE_URL, session=session,
                clock=lambda: datetime.now(timezone.utc), page_pause=lambda: sleep(0.5),
            )
        except KISMockBoundaryError:
            print("Invalid mock inputs or expired token.")
            return 2
        result = client.check_account()

    balance_status = "ok" if result.balance_ok else "failed"
    order_status = {None: "skipped", False: "failed", True: "ok"}[result.orders_ok]
    print(f"balance={balance_status} orders={order_status}")
    return 0 if result.ok else 1


if __name__ == "__main__":
    sys.exit(main())
