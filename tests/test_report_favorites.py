from __future__ import annotations

from pathlib import Path

from invest_bot.dashboard.report_favorites import ReportFavoritesStore
from tests.helpers import make_test_dir


def test_report_favorites_store_returns_empty_when_file_is_missing() -> None:
    store = ReportFavoritesStore(make_test_dir("report_favorites_missing") / "favorites.json")

    assert store.load() == []
    assert store.load_symbols() == set()


def test_report_favorites_store_returns_empty_when_json_is_invalid() -> None:
    path = make_test_dir("report_favorites_invalid") / "favorites.json"
    path.write_text("{broken", encoding="utf-8")
    store = ReportFavoritesStore(path)

    assert store.load() == []


def test_report_favorites_store_returns_empty_when_version_is_unknown() -> None:
    path = make_test_dir("report_favorites_version") / "favorites.json"
    path.write_text('{"version": 999, "favorite_symbols": [{"symbol":"005930","created_at":"2026-06-27T00:00:00+00:00"}]}', encoding="utf-8")
    store = ReportFavoritesStore(path)

    assert store.load() == []


def test_report_favorites_store_roundtrip_add_remove_and_unique_symbols() -> None:
    path = make_test_dir("report_favorites_roundtrip") / "favorites.json"
    store = ReportFavoritesStore(path)

    assert store.add("005930") is True
    assert store.add("005930") is False
    assert store.is_favorite("005930") is True
    assert store.load_symbols() == {"005930"}
    assert path.exists()

    reloaded = ReportFavoritesStore(path)
    assert reloaded.load_symbols() == {"005930"}

    assert reloaded.remove("005930") is True
    assert reloaded.remove("005930") is False
    assert reloaded.load_symbols() == set()


def test_report_favorites_store_toggle_flips_state() -> None:
    path = make_test_dir("report_favorites_toggle") / "favorites.json"
    store = ReportFavoritesStore(path)

    assert store.toggle("000660") is True
    assert store.load_symbols() == {"000660"}
    assert store.toggle("000660") is False
    assert store.load_symbols() == set()
