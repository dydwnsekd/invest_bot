from __future__ import annotations

from invest_bot.config.settings import AppSettings
from invest_bot.dashboard.report_favorites import ReportFavoritesStore
from invest_bot.db.engine import build_engine, build_session_factory
from invest_bot.db.repositories import SqlAlchemyReportFavoriteSymbolRepository
from sqlalchemy.exc import IntegrityError
from tests.helpers import init_test_db, make_test_dir


def _make_store(name: str) -> ReportFavoritesStore:
    test_dir = make_test_dir(name)
    database_url = f"sqlite+pysqlite:///{(test_dir / 'favorites.db').as_posix()}"
    init_test_db(database_url)
    repository = SqlAlchemyReportFavoriteSymbolRepository(build_session_factory(build_engine(database_url)))
    return ReportFavoritesStore(repository)


def test_report_favorites_store_returns_empty_when_table_is_empty() -> None:
    store = _make_store("report_favorites_empty")

    assert store.load() == []
    assert store.load_symbols() == set()


def test_report_favorites_store_roundtrip_add_remove_and_unique_symbols() -> None:
    store = _make_store("report_favorites_roundtrip")

    assert store.add("005930") is True
    assert store.add("005930") is False
    assert store.is_favorite("005930") is True
    assert store.load_symbols() == {"005930"}

    repository = store.repository
    reloaded = ReportFavoritesStore(repository)
    assert reloaded.load_symbols() == {"005930"}

    assert reloaded.remove("005930") is True
    assert reloaded.remove("005930") is False
    assert reloaded.load_symbols() == set()


def test_report_favorites_store_toggle_flips_state() -> None:
    store = _make_store("report_favorites_toggle")

    assert store.toggle("000660") is True
    assert store.load_symbols() == {"000660"}
    assert store.toggle("000660") is False
    assert store.load_symbols() == set()


def test_report_favorites_store_normalizes_numeric_symbols() -> None:
    store = _make_store("report_favorites_normalize")

    assert store.add("5930") is True
    assert store.load_symbols() == {"005930"}


def test_report_favorites_store_does_not_import_legacy_json_file() -> None:
    store = _make_store("report_favorites_no_json_backfill")
    legacy_file = make_test_dir("report_favorites_legacy_json") / "report_favorites_state.json"
    legacy_file.write_text(
        '{"version": 1, "favorite_symbols": [{"symbol":"005930","created_at":"2026-06-27T00:00:00+00:00"}]}',
        encoding="utf-8",
    )

    assert legacy_file.exists()
    assert store.load_symbols() == set()


def test_report_favorites_store_accepts_legacy_path_constructor_shape() -> None:
    test_dir = make_test_dir("report_favorites_legacy_path_ctor")
    legacy_file = test_dir / "report_favorites_state.json"
    database_url = f"sqlite+pysqlite:///{(test_dir / 'favorites.db').as_posix()}"
    init_test_db(database_url)
    legacy_file.write_text(
        '{"version": 1, "favorite_symbols": [{"symbol":"005930","created_at":"2026-06-27T00:00:00+00:00"}]}',
        encoding="utf-8",
    )

    store = ReportFavoritesStore(legacy_file, settings=AppSettings(database_url_value=database_url))

    assert store.load_symbols() == set()


def test_report_favorite_repository_returns_false_on_duplicate_insert_race() -> None:
    class _RaceSession:
        def __enter__(self) -> "_RaceSession":
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

        def get(self, model, symbol):  # noqa: ANN001
            return None

        def add(self, record) -> None:  # noqa: ANN001
            self.record = record

        def commit(self) -> None:
            raise IntegrityError("insert", {}, Exception("duplicate key"))

        def rollback(self) -> None:
            self.rolled_back = True

    session = _RaceSession()
    repository = SqlAlchemyReportFavoriteSymbolRepository(lambda: session)

    assert repository.add("005930") is False
    assert session.rolled_back is True
