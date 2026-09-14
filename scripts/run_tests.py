from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
REPORT_DIR = ROOT / "data" / "processed" / "test_reports"
REPORT_FILE = REPORT_DIR / "pytest_results.xml"
COMMAND_FILE = REPORT_DIR / "pytest_command.txt"
SUITE_MARKERS = {
    "default": "not external_network and not postgresql",
    "external-network": "external_network",
    "postgresql": "postgresql",
}

if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


def main() -> None:
    parser = argparse.ArgumentParser(description="Run an isolated invest_bot pytest suite.")
    parser.add_argument("--suite", choices=SUITE_MARKERS, default="default")
    options, pytest_args = parser.parse_known_args()
    REPORT_DIR.mkdir(parents=True, exist_ok=True)

    pytest_args = pytest_args or ["tests"]
    if "-m" not in pytest_args and "--markers" not in pytest_args:
        pytest_args.extend(["-m", SUITE_MARKERS[options.suite]])
    command = [sys.executable, "-m", "pytest", *pytest_args, f"--junitxml={REPORT_FILE}"]
    COMMAND_FILE.write_text(" ".join(command), encoding="utf-8")

    completed = subprocess.run(command, cwd=ROOT)
    print({"report_path": str(REPORT_FILE), "command": " ".join(command), "exit_code": completed.returncode})
    raise SystemExit(completed.returncode)


if __name__ == "__main__":
    main()
