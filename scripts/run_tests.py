from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
REPORT_DIR = ROOT / "data" / "processed" / "test_reports"
REPORT_FILE = REPORT_DIR / "pytest_results.xml"
COMMAND_FILE = REPORT_DIR / "pytest_command.txt"

if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


def main() -> None:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)

    pytest_args = sys.argv[1:] or ["tests"]
    command = [sys.executable, "-m", "pytest", *pytest_args, f"--junitxml={REPORT_FILE}"]
    COMMAND_FILE.write_text(" ".join(command), encoding="utf-8")

    completed = subprocess.run(command, cwd=ROOT)
    print({"report_path": str(REPORT_FILE), "command": " ".join(command), "exit_code": completed.returncode})
    raise SystemExit(completed.returncode)


if __name__ == "__main__":
    main()
