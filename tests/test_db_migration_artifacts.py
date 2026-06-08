from __future__ import annotations

from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]


def test_env_example_includes_db_runtime_variables():
    env_text = (ROOT / ".env.example").read_text(encoding="utf-8")

    for key in [
        "INVEST_BOT_DB_HOST",
        "INVEST_BOT_DB_PORT",
        "INVEST_BOT_DB_NAME",
        "INVEST_BOT_DB_USER",
        "INVEST_BOT_DB_PASSWORD",
        "INVEST_BOT_APP_ROLE",
    ]:
        assert f"{key}=" in env_text


def test_docker_compose_defines_db_migration_startup_flow():
    compose = yaml.safe_load((ROOT / "docker-compose.yml").read_text(encoding="utf-8"))
    services = compose["services"]

    assert compose["volumes"] == {"postgres_data": None}
    assert services["db"]["image"] == "postgres:17"
    assert services["migrate"]["command"] == ["python", "-m", "invest_bot.db.migrate_runtime"]
    assert services["migrate"]["depends_on"]["db"]["condition"] == "service_healthy"

    for service_name in ["scheduler", "web", "collector"]:
        depends_on = services[service_name]["depends_on"]
        assert depends_on["db"]["condition"] == "service_healthy"
        assert depends_on["migrate"]["condition"] == "service_completed_successfully"
        assert services[service_name]["env_file"] == [".env"]


def test_db_migration_docs_exist_with_required_sections():
    docs = {
        ROOT / "docs/architecture/db_migration_erd.md": [
            "# invest_bot DB migration ERD",
            "## Tables",
            "## Relationships",
            "## Constraints",
        ],
        ROOT / "docs/architecture/repository_interfaces.md": [
            "# invest_bot repository interfaces for DB migration",
            "## Repository contracts",
            "## Compatibility rules",
            "## Initial adapter strategy",
        ],
        ROOT / "docs/architecture/db_migration_plan.md": [
            "# invest_bot DB migration implementation-ready plan",
            "## Phases",
            "## Deliverables",
            "## Verification checklist",
        ],
    }

    for path, required_sections in docs.items():
        assert path.exists(), f"missing required migration artifact: {path}"
        content = path.read_text(encoding="utf-8")
        for section in required_sections:
            assert section in content, f"missing section {section!r} in {path.name}"
