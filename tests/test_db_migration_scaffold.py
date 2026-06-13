from invest_bot.config.settings import AppSettings
from tests.helpers import make_test_dir

from invest_bot.db import Base, build_database_url
from invest_bot.db.migration import should_stamp_existing_schema


def test_build_database_url_prefers_direct_database_url_from_app_yaml():
    test_dir = make_test_dir("migration_direct_url")
    config_path = test_dir / "app.yaml"
    config_path.write_text("database_url: postgresql+psycopg://demo:secret@db:5432/demo\n", encoding="utf-8")

    assert build_database_url(AppSettings.from_file(config_path)) == "postgresql+psycopg://demo:secret@db:5432/demo"


def test_build_database_url_builds_from_app_yaml_fields():
    test_dir = make_test_dir("migration_db_fields")
    config_path = test_dir / "app.yaml"
    config_path.write_text(
        "\n".join(
            [
                "db_host: db",
                "db_port: 5433",
                "db_name: sample",
                "db_user: user+name",
                "db_password: pass word",
            ]
        ),
        encoding="utf-8",
    )

    assert build_database_url(AppSettings.from_file(config_path)) == "postgresql+psycopg://user%2Bname:pass+word@db:5433/sample"


def test_initial_db_metadata_exposes_expected_tables():
    assert {"symbols", "daily_prices", "stock_info_snapshots", "investor_daily"}.issubset(Base.metadata.tables)


def test_should_stamp_existing_schema_when_bootstrap_tables_exist_without_version_table():
    existing_tables = {"symbols", "daily_prices", "stock_info_snapshots", "investor_daily", "dataset_frames"}
    assert should_stamp_existing_schema(existing_tables, has_version_table=False) is True


def test_should_not_stamp_when_alembic_version_exists_or_schema_is_incomplete():
    assert should_stamp_existing_schema({"symbols", "daily_prices"}, has_version_table=False) is False
    assert should_stamp_existing_schema(
        {"symbols", "daily_prices", "stock_info_snapshots", "investor_daily", "alembic_version"},
        has_version_table=True,
    ) is False
