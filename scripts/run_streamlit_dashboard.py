from __future__ import annotations

import os
import sys
from pathlib import Path

import streamlit.web.cli as stcli


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"
APP_PATH = PROJECT_ROOT / "streamlit_app.py"
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8000


def resolve_dashboard_bind(host: str = DEFAULT_HOST, port: int = DEFAULT_PORT) -> tuple[str, int]:
    resolved_host = os.getenv("INVEST_BOT_DASHBOARD_HOST", host).strip() or host
    port_value = os.getenv("INVEST_BOT_DASHBOARD_PORT", str(port)).strip()
    try:
        resolved_port = int(port_value)
    except ValueError:
        resolved_port = port
    return resolved_host, resolved_port


def build_streamlit_argv(host: str, port: int) -> list[str]:
    return [
        "streamlit",
        "run",
        str(APP_PATH),
        "--server.address",
        host,
        "--server.port",
        str(port),
        "--server.headless",
        "true",
    ]


def main() -> None:
    if str(SRC_PATH) not in sys.path:
        sys.path.insert(0, str(SRC_PATH))

    host, port = resolve_dashboard_bind()
    sys.argv = build_streamlit_argv(host, port)
    raise SystemExit(stcli.main())


if __name__ == "__main__":
    main()
