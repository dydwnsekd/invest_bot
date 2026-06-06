from invest_bot.db import Base, build_database_url


def test_build_database_url_prefers_explicit_database_url(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://demo:secret@db:5432/demo")
    assert build_database_url() == "postgresql+psycopg://demo:secret@db:5432/demo"


def test_build_database_url_builds_from_invest_bot_env(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("INVEST_BOT_DB_HOST", "db")
    monkeypatch.setenv("INVEST_BOT_DB_PORT", "5433")
    monkeypatch.setenv("INVEST_BOT_DB_NAME", "sample")
    monkeypatch.setenv("INVEST_BOT_DB_USER", "user+name")
    monkeypatch.setenv("INVEST_BOT_DB_PASSWORD", "pass word")

    assert build_database_url() == "postgresql+psycopg://user%2Bname:pass+word@db:5433/sample"


def test_initial_db_metadata_exposes_expected_tables():
    assert {"symbols", "daily_prices", "stock_info_snapshots", "investor_daily"}.issubset(Base.metadata.tables)
