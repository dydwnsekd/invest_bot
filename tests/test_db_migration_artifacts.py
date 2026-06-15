from __future__ import annotations

from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]


def test_env_example_includes_compose_runtime_variables():
    env_text = (ROOT / ".env.example").read_text(encoding="utf-8")

    for key in [
        "INVEST_BOT_DB_DATA_DIR",
        "INVEST_BOT_APP_ROLE",
    ]:
        assert f"{key}=" in env_text


def test_app_yaml_example_exposes_db_and_kis_settings():
    app_yaml = (ROOT / "config" / "app.yaml.example").read_text(encoding="utf-8")

    for key in [
        "database_url:",
        "kis_live_app_key:",
        "kis_live_app_secret:",
        "kis_mock_app_key:",
        "kis_mock_app_secret:",
        "db_host:",
        "db_host_docker:",
        "db_port:",
        "db_name:",
        "db_user:",
        "db_password:",
        "enable_db_write:",
    ]:
        assert key in app_yaml


def test_docker_compose_defines_db_migration_startup_flow():
    compose = yaml.safe_load((ROOT / "docker-compose.yml").read_text(encoding="utf-8"))
    services = compose["services"]

    assert services["db"]["image"] == "postgres:17"
    assert services["db"]["volumes"] == ["${INVEST_BOT_DB_DATA_DIR:-./.docker/postgres}:/var/lib/postgresql/data"]
    assert services["migrate"]["command"] == ["python", "scripts/init_db.py"]
    assert services["migrate"]["depends_on"]["db"]["condition"] == "service_healthy"
    assert services["migrate"]["environment"]["INVEST_BOT_APP_ROLE"] == "migrate"
    assert services["migrate"]["volumes"] == ["./config:/app/config:ro"]

    for service_name in ["scheduler", "web", "collector"]:
        depends_on = services[service_name]["depends_on"]
        assert depends_on["db"]["condition"] == "service_healthy"
        assert depends_on["migrate"]["condition"] == "service_completed_successfully"
        assert services[service_name]["env_file"] == [".env"]
        assert services[service_name]["volumes"] == ["./config:/app/config:ro"]


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
        ROOT / "docs/architecture/db_schema.md": [
            "# invest_bot DB-first schema",
            "## Tables",
            "## Endpoint configuration",
            "## Relationship image",
        ],
    }

    for path, required_sections in docs.items():
            assert path.exists(), f"missing required migration artifact: {path}"
            content = path.read_text(encoding="utf-8")
            for section in required_sections:
                assert section in content, f"missing section {section!r} in {path.name}"

    assert (ROOT / "docs/architecture/db_schema.svg").exists()
    assert (ROOT / "scripts/init_db.py").exists()


def test_dockerignore_excludes_runtime_secret_files():
    dockerignore = (ROOT / ".dockerignore").read_text(encoding="utf-8")

    for path in [".env", "config/app.yaml"]:
        assert path in dockerignore
