"""Real SQL observation is independent of SQLAlchemy's URL display escaping."""
from __future__ import annotations

import json
from urllib.parse import quote

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL, make_url
from streamlit.testing.v1 import AppTest

from invest_bot.config.settings import AppSettings
from invest_bot.dashboard.streamlit_state import DashboardFrameLoader
from tests.g06c_layout_fixture import G06cHarness
from tests.qa02_dashboard_fixture import QA02Harness


@pytest.fixture
def escaped_url_display(monkeypatch):
    original = URL.__str__

    def display(url):
        rendered = original(url)
        if url.database:
            # Display-only counterfactual for 2.0; already-escaped 2.1 output
            # remains unchanged. Do not alter URL components or engine/query.
            rendered = rendered.replace(url.database, quote(url.database, safe="/"), 1)
        return rendered

    monkeypatch.setattr(URL, "__str__", display)
    monkeypatch.setattr(AppSettings, "from_file", lambda *a, **k: pytest.fail("runtime settings access"))


@pytest.mark.parametrize("harness_type", [QA02Harness, G06cHarness], ids=["QA02", "G06c"])
def test_same_database_snapshot_and_other_database_isolation(tmp_path, escaped_url_display, harness_type):
    harness = harness_type(tmp_path / "target DB 한글")
    target = make_url(harness.database_url)
    assert target.database == str(harness.directory / "qa02.sqlite")
    assert str(target) != harness.database_url
    other = create_engine(f"sqlite:///{tmp_path / 'other DB 한글.sqlite'}")
    try:
        with harness.observe():
            with other.connect() as connection:
                assert connection.execute(text("SELECT 987654")).scalar_one() == 987654
            assert not harness.selects
            snapshot = harness.service.build_snapshot()
            assert len(harness.selects) == 2
            loader = DashboardFrameLoader(harness.service, snapshot.latest_records)
            samsung = loader.load_professional("005930")
            hyundai = loader.load_professional("005380")
            assert len(harness.selects) == 2  # Actual frame consumers add no SQL.
            assert samsung.foreign_net.dropna().tolist() == [-11., 0.]
            assert hyundai.foreign_net.dropna().tolist() == [0.]
            assert samsung.attrs["investor_flow_source"] == "summary"
            assert hyundai.attrs["investor_flow_source"] == "detail"
            assert all(phase == "snapshot" for phase, _ in harness.selects)
        assert harness.sql_attempts[-1]["snapshot_selects"] == 2
        assert harness.sql_attempts[-1]["frame_consumer_selects"] == 0
        if isinstance(harness, G06cHarness):
            events = harness.classified_attempts[-1]
            assert len(events) == 2
            assert all(item["phase"] == "snapshot" and item["context"] == "screen" for item in events)
            assert not harness.write_attempts
    finally:
        other.dispose()


@pytest.mark.parametrize("statement,verb", [
    ("INSERT INTO qa04_guard VALUES (2, 99)", "INSERT"),
    ("UPDATE qa04_guard SET value = 99 WHERE id = 1", "UPDATE"),
])
def test_derived_observer_blocks_actual_target_writes_but_ignores_other_database(tmp_path, escaped_url_display, statement, verb):
    harness = G06cHarness(tmp_path / "guard DB 한글")
    target = create_engine(harness.database_url)
    other = create_engine(f"sqlite:///{tmp_path / 'unrelated DB 한글.sqlite'}")
    try:
        with target.begin() as connection:
            connection.execute(text("CREATE TABLE qa04_guard (id INTEGER PRIMARY KEY, value INTEGER)"))
            connection.execute(text("INSERT INTO qa04_guard VALUES (1, 7)"))
        with target.begin() as connection:
            with harness.observe():
                with other.begin() as unrelated:
                    unrelated.execute(text("CREATE TABLE unrelated_guard (value INTEGER)"))
                    unrelated.execute(text("INSERT INTO unrelated_guard VALUES (3)"))
                assert not harness.write_attempts
                with pytest.raises(AssertionError, match="G06c render attempted SQLite write: " + verb):
                    connection.execute(text(statement))
                assert harness.write_attempts == [verb]
                assert connection.execute(text("SELECT value FROM qa04_guard WHERE id = 1")).scalar_one() == 7
        assert len(harness.classified_attempts[-1]) == 1
        assert harness.classified_attempts[-1][0]["context"] == "screen"
        assert harness.sql_attempts[-1]["total_selects"] == 1
        with target.connect() as connection:
            assert connection.execute(text("SELECT id, value FROM qa04_guard")).all() == [(1, 7)]
    finally:
        target.dispose()
        other.dispose()


def real_app(folder, derived):
    from pathlib import Path
    import streamlit as st
    from tests.qa02_dashboard_fixture import QA02Harness
    from tests.g06c_layout_fixture import G06cHarness
    if "qa02_harness" not in st.session_state:
        st.session_state["qa02_harness"] = (G06cHarness if derived else QA02Harness)(Path(folder))
    st.session_state["qa02_harness"].render()


@pytest.mark.parametrize("derived", [False, True], ids=["QA02-main", "G06c-main"])
def test_actual_main_keeps_strict_read_budget_with_escaped_url_display(tmp_path, escaped_url_display, derived):
    folder = tmp_path / "actual App DB 한글"
    app = AppTest.from_function(real_app, kwargs={"folder": str(folder), "derived": derived}, default_timeout=30).run()
    records = []
    for tab, favorites in (("홈", 0), ("투자 리포트", 1)):
        if tab != "홈":
            app.button(key="nav_" + tab).click().run()
        assert not app.exception
        measurement = dict(app.session_state["qa02_measurement"])
        assert measurement["tab"] == tab
        assert measurement["snapshot_selects"] == 2
        assert measurement["favorite_selects_after_snapshot"] == favorites
        assert measurement["total_selects"] == 2 + favorites
        assert measurement["frame_consumer_selects"] == 0
        assert measurement["job_calls"] == 0 and measurement["forbidden_calls"] == []
        if derived:
            extra = app.session_state["g06c_measurement"]
            assert extra["write_attempts"] == [] and extra["runner_calls"] == []
            assert len(extra["sql_events"]) == 2 + favorites
        records.append(measurement)
    harness = app.session_state["qa02_harness"]
    assert (folder / "qa02.sqlite").is_file()
    assert not harness.calls and not harness.forbidden_calls
    assert all(attempt["frame_consumer_selects"] == 0 for attempt in harness.sql_attempts)
    assert sum(attempt["total_selects"] for attempt in harness.sql_attempts) == records[-1]["selects_all_script_attempts"]
    (tmp_path / "qa04f-observations.json").write_text(json.dumps({"completed": records, "all_attempts": harness.sql_attempts}, ensure_ascii=False, indent=2))
