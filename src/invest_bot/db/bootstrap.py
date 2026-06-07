from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import cast

from invest_bot.config.settings import AppSettings, PROJECT_ROOT


def build_readiness_report(settings: AppSettings | None = None) -> dict[str, object]:
    resolved_settings = settings or AppSettings.from_file()
    plan_path = PROJECT_ROOT / "docs" / "operations" / "db_migration_plan.md"
    erd_path = PROJECT_ROOT / "docs" / "architecture" / "db_migration_erd.md"
    contracts_path = PROJECT_ROOT / "src" / "invest_bot" / "db" / "contracts.py"
    compose_path = PROJECT_ROOT / "docker-compose.yml"
    return {
        "draft_only": True,
        "database_url": resolved_settings.database_url,
        "artifacts": {
            "docker_compose": _artifact_status(compose_path),
            "erd": _artifact_status(erd_path),
            "migration_plan": _artifact_status(plan_path),
            "repository_contracts": _artifact_status(contracts_path),
        },
        "next_step": "Implement SQLAlchemy/Alembic adapters behind the repository contracts before enabling real DB migrations.",
    }


def _artifact_status(path: Path) -> dict[str, object]:
    return {"path": str(path.relative_to(PROJECT_ROOT)), "exists": path.exists()}


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate the draft DB migration surface.")
    parser.add_argument("--json", action="store_true", help="Print the readiness report as JSON.")
    args = parser.parse_args()

    report = build_readiness_report()
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return

    print("invest_bot DB migration draft readiness")
    print(f"database_url={report['database_url']}")
    artifacts = cast(dict[str, dict[str, object]], report["artifacts"])
    for name, artifact in artifacts.items():
        state = "ok" if artifact["exists"] else "missing"
        print(f"- {name}: {state} ({artifact['path']})")
    print(report["next_step"])


if __name__ == "__main__":
    main()
