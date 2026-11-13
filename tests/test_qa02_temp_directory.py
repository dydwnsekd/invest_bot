"""QA04: real synthetic SQLite follows stdlib temp selection and explicit paths."""
from __future__ import annotations

from pathlib import Path
import shutil
import tempfile

import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

from invest_bot.config.settings import AppSettings
from invest_bot.dashboard.streamlit_state import DashboardFrameLoader
from tests.qa02_dashboard_fixture import DAYS, NAMES, QA02Harness, ROOT


@pytest.fixture(autouse=True)
def deny_runtime_settings(monkeypatch):
    monkeypatch.setattr(AppSettings, "from_file", lambda *a, **k: pytest.fail("runtime settings access"))


def configure_temp(monkeypatch, tmp_path, *, cached=False):
    selected = tmp_path / "configured temp 임시"
    selected.mkdir()
    environment = tmp_path / "other-temp" if cached else selected
    environment.mkdir(exist_ok=True)
    monkeypatch.setenv("TMPDIR", str(environment))
    monkeypatch.delenv("TEMP", raising=False)
    monkeypatch.delenv("TMP", raising=False)
    monkeypatch.setattr(tempfile, "tempdir", str(selected) if cached else None)
    return selected


def assert_real_seed_and_read_budget(harness):
    assert (harness.directory / "qa02.sqlite").is_file()
    assert harness.database_url == f"sqlite:///{harness.directory / 'qa02.sqlite'}"
    assert harness.favorites.load_symbols() == set(NAMES)
    prices = harness.storage.load("daily_prices", "005930_raw.csv")
    assert pd.to_datetime(prices["date"]).dt.strftime("%Y-%m-%d").tolist() == DAYS
    assert prices["close"].tolist() == [100., 101., 102., 103., 104.]
    with harness.observe():
        snapshot = harness.service.build_snapshot()
        loader = DashboardFrameLoader(harness.service, snapshot.latest_records)
        samsung = loader.load_professional("005930")
        hyundai = loader.load_professional("005380")
        assert len(harness.selects) == 2
        assert all(phase == "snapshot" for phase, _ in harness.selects)
    assert samsung.attrs["investor_flow_source"] == "summary"
    assert samsung.foreign_net.dropna().tolist() == [-11., 0.]
    assert pd.isna(samsung.foreign_net.iloc[0])
    assert hyundai.attrs["investor_flow_source"] == "detail"
    assert hyundai.foreign_net.dropna().tolist() == [0.]
    assert not harness.calls and not harness.forbidden_calls


@pytest.mark.parametrize("cached", [False, True], ids=["TMPDIR-reset-cache", "configured-cache"])
def test_default_sqlite_uses_standard_temp_root(monkeypatch, tmp_path, cached):
    selected = configure_temp(monkeypatch, tmp_path, cached=cached)
    harness = QA02Harness()
    try:
        assert harness.directory.parent.resolve() == selected.resolve()
        assert harness.directory.name.startswith("qa02-synthetic-")
        assert_real_seed_and_read_budget(harness)
    finally:
        # Only this constructor's unique synthetic directory is owned here.
        # Also remove the old implementation's misplaced directory after RED.
        for repository in (harness.storage.repository, harness.favorites.repository):
            repository.session_factory.kw["bind"].dispose()
        shutil.rmtree(harness.directory)


def test_explicit_directory_wins_without_allocating_default_temp(monkeypatch, tmp_path):
    selected = configure_temp(monkeypatch, tmp_path)
    supplied = tmp_path / "explicit" / "nested directory"
    harness = QA02Harness(directory=supplied)
    assert harness.directory == supplied
    assert list(selected.iterdir()) == []
    assert_real_seed_and_read_budget(harness)


def test_actual_app_keeps_one_temp_sqlite_and_read_only_rerun_budget(monkeypatch, tmp_path):
    selected = configure_temp(monkeypatch, tmp_path)
    app = AppTest.from_file(str(ROOT / "tests/qa02_dashboard_fixture.py"), default_timeout=30).run()
    assert not app.exception
    harness = app.session_state["qa02_harness"]
    try:
        assert harness.directory.parent.resolve() == selected.resolve()
        original_path = harness.directory / "qa02.sqlite"
        for view, favorite in (("홈", 0), ("투자 리포트", 1), ("관심종목", 1)):
            if view != "홈":
                app.button(key="nav_" + view).click().run()
            assert not app.exception
            assert app.session_state["qa02_harness"] is harness
            assert original_path.is_file()
            measured = app.session_state["qa02_measurement"]
            assert measured["tab"] == view
            assert measured["snapshot_selects"] == 2
            assert measured["favorite_selects_after_snapshot"] == favorite
            assert measured["total_selects"] == 2 + favorite
            assert measured["frame_consumer_selects"] == 0
            assert measured["job_calls"] == 0 and measured["forbidden_calls"] == []
        assert all(attempt["frame_consumer_selects"] == 0 for attempt in harness.sql_attempts)
        assert sum(attempt["total_selects"] for attempt in harness.sql_attempts) == measured["selects_all_script_attempts"]
        assert not harness.calls and not harness.forbidden_calls
    finally:
        for repository in (harness.storage.repository, harness.favorites.repository):
            repository.session_factory.kw["bind"].dispose()
        shutil.rmtree(harness.directory)
