from __future__ import annotations

import sys
from pathlib import Path

import streamlit.web.cli as stcli


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"
APP_PATH = PROJECT_ROOT / "streamlit_app.py"


def main() -> None:
    if str(SRC_PATH) not in sys.path:
        sys.path.insert(0, str(SRC_PATH))

    sys.argv = [
        "streamlit",
        "run",
        str(APP_PATH),
    ]
    raise SystemExit(stcli.main())


if __name__ == "__main__":
    main()
