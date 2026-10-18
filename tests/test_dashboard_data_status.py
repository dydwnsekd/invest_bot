from datetime import UTC, date, datetime
from types import SimpleNamespace

import pandas as pd
import pytest

from invest_bot.dashboard import streamlit_overview as overview
from invest_bot.dashboard.service import DashboardDataService
from invest_bot.dashboard.streamlit_watchlist import build_watchlist_data_statuses
from invest_bot.db.contracts import DatasetFrameRecord
from invest_bot.db.repositories import frame_to_json

TODAY = date(2026, 10, 2)
OLD = date(2026, 10, 1)
DATASETS = ("daily_prices", "investor_daily_summary", "daily_prices_indicators", "golden_cross_signals", "market_reports")


def records_for(symbol="005930", **dates):
    return tuple(
        DatasetFrameRecord(
            dataset=name, filename=f"{symbol}_{name}.csv", symbol=symbol,
            row_count=1, frame_json=frame_to_json(pd.DataFrame({"date": [str(dates.get(name, TODAY))]})),
            created_at=datetime(2026, 10, 3, tzinfo=UTC),
        )
        for name in DATASETS if dates.get(name, TODAY) is not None
    )


def forbidden(*args, **kwargs):
    pytest.fail("snapshot status must not read backing storage or execute jobs")


def statuses(records, monkeypatch, symbols={"005930"}):
    service = DashboardDataService(raw_root="/not/read/raw", processed_root="/not/read/processed")
    monkeypatch.setattr(service, "get_dataset_storage", forbidden)
    return build_watchlist_data_statuses(service, symbols, today=TODAY, latest_records=records)


def home_status(symbol_statuses):
    rows = [(SimpleNamespace(symbol="005930"), pd.Series({"date": str(OLD)}))]
    return overview.build_overview_trust_status(
        rows, rows, None, today=TODAY, symbol_statuses=symbol_statuses,
    )


def test_current_sources_old_analysis_recommends_only_analysis(monkeypatch):
    symbol_statuses = statuses(records_for(daily_prices_indicators=OLD, golden_cross_signals=OLD, market_reports=OLD), monkeypatch)
    state = home_status(symbol_statuses)
    assert state.label == "분석 갱신 필요"
    assert "수집" not in state.detail
    assert state.report_date == OLD
    assert state.data_status.symbol_statuses[0].daily_date == TODAY
    actions = overview.build_overview_next_actions(SimpleNamespace(log_exists=True), None, state)
    assert actions[0][0] == "분석 갱신"
    assert actions[0][2] == "데이터 갱신"


def test_missing_source_and_stale_source_have_distinct_reasons(monkeypatch):
    missing = statuses(records_for(investor_daily_summary=None), monkeypatch)[0]
    stale = statuses(records_for(investor_daily_summary=OLD), monkeypatch)[0]
    assert missing.label == stale.label == "데이터 갱신 필요"
    assert "수급 원본" in missing.detail and "없" in missing.detail
    assert "2026-10-02" in stale.detail
    assert missing.detail != stale.detail


@pytest.mark.parametrize("dataset", ["daily_prices_indicators", "golden_cross_signals", "market_reports"])
def test_output_ahead_of_inputs_is_not_reported_current(dataset, monkeypatch):
    state = statuses(records_for(**{dataset: date(2026, 10, 5)}), monkeypatch)[0]
    assert state.label == "기준일 불일치"


def test_home_cannot_hide_one_symbols_old_output_with_another_symbols_new_date(monkeypatch):
    records = records_for(market_reports=OLD) + records_for("000660", golden_cross_signals=OLD)
    state = home_status(statuses(records, monkeypatch, {"005930", "000660"}))
    assert state.label == "분석 갱신 필요"
    assert all(symbol in state.detail for symbol in ("005930", "000660"))


def test_empty_db_snapshot_never_falls_back_to_storage(monkeypatch):
    states = statuses((), monkeypatch)
    assert states[0].daily_date is None and states[0].report_date is None
    assert states[0].label == "데이터 갱신 필요"


def test_selected_report_date_is_preserved_even_when_latest_snapshot_is_newer(monkeypatch):
    from invest_bot.dashboard.data_status import build_report_data_status
    service = DashboardDataService(raw_root="/not/read/raw", processed_root="/not/read/processed")
    monkeypatch.setattr(service, "get_dataset_storage", forbidden)
    snapshot = SimpleNamespace(raw_previews=[], processed_previews=[], latest_records=records_for())
    state = build_report_data_status(service, snapshot, "005930", pd.Series({"date": str(OLD)}), today=TODAY)
    assert state.report_date == OLD and state.daily_date == TODAY
    assert state.label == "분석 갱신 필요"


def test_lightweight_report_snapshot_does_not_add_backing_reads(monkeypatch):
    from pathlib import Path
    from invest_bot.dashboard.data_status import build_report_data_status
    service = DashboardDataService(raw_root="/not/read/raw", processed_root="/not/read/processed")
    monkeypatch.setattr(service, "get_dataset_storage", forbidden)
    preview = SimpleNamespace(name="market_reports", symbol="005930", path=Path("report.csv"), created_at=None)
    row = pd.Series({"date": str(OLD)})
    state = build_report_data_status(
        service, SimpleNamespace(processed_previews=[preview]), "005930", row,
        today=TODAY, read_preview_frame=lambda preview: pd.DataFrame([row]),
    )
    assert state.report_date == OLD
    assert state.daily_date is None


@pytest.mark.parametrize("view", ["홈", "투자 리포트", "관심종목"])
@pytest.mark.parametrize("scenario,label", [("분석 지연", "분석 갱신 필요"), ("원본 누락", "데이터 갱신 필요"), ("날짜 불일치", "기준일 불일치"), ("정상", "기준일 확인됨")])
def test_actual_renderers_show_consistent_source_and_decision_dates(view, scenario, label):
    from streamlit.testing.v1 import AppTest
    from tests.g05b_dashboard_fixture import render_fixture
    app = AppTest.from_function(render_fixture, default_timeout=20).run()
    app.selectbox[0].select(scenario)
    app.radio[0].set_value(view).run()
    assert not app.exception
    visible = "\n".join(str(item.value) for group in (app.markdown, app.caption, app.warning, app.info) for item in group)
    expected = "최신" if scenario == "정상" and view == "관심종목" else label
    if scenario == "정상" and view == "홈":
        expected = "기준일이 확인되었습니다"
    if scenario == "정상" and view == "투자 리포트":
        expected = "기준으로 준비"
    assert expected in visible
    if view in ("홈", "투자 리포트"):
        assert "원본 가격 2026-10-02" in visible
        expected_report = "2026-10-01" if scenario == "분석 지연" else "2026-10-05" if scenario == "날짜 불일치" else "2026-10-02"
        if view == "홈" or scenario != "날짜 불일치":
            assert f"판단 리포트 {expected_report}" in visible
    assert sum(app.session_state["g05b_counts"].values()) == 0


def test_all_status_consumers_reuse_sqlite_snapshot_without_selects(tmp_path):
    from sqlalchemy import Engine, event
    from invest_bot.dashboard.data_status import build_snapshot_data_statuses, build_report_data_status
    from invest_bot.db.frame_storage import DbFrameStorage
    from tests.helpers import init_test_db

    database_url = f"sqlite:///{tmp_path / 'g05b.db'}"
    init_test_db(database_url)
    storage = DbFrameStorage(database_url)
    service = DashboardDataService(dataset_storage=storage)
    service._load_symbol_name_map = lambda: {}
    for dataset in DATASETS:
        day = TODAY if dataset in DATASETS[:2] else OLD
        storage.save(dataset, f"005930_{dataset}.csv", pd.DataFrame({"symbol": ["005930"], "date": [str(day)]}))
    snapshot = service.build_snapshot()
    selects = []
    def observe(conn, cursor, statement, parameters, context, executemany):
        if statement.lstrip().upper().startswith("SELECT"):
            selects.append(statement)
    event.listen(Engine, "before_cursor_execute", observe)
    try:
        states = build_snapshot_data_statuses(service, snapshot, today=TODAY)
        home = home_status(states)
        report = build_report_data_status(service, snapshot, "005930", pd.Series({"date": str(OLD)}), today=TODAY)
        watch = build_watchlist_data_statuses(service, {"005930"}, today=TODAY, latest_records=snapshot.latest_records)
    finally:
        event.remove(Engine, "before_cursor_execute", observe)
    assert home.label == report.label == watch[0].label == "분석 갱신 필요"
    assert report.report_date == watch[0].report_date == OLD
    assert selects == []


@pytest.mark.parametrize("view,query_key,selection_key", [
    ("투자 리포트", "report_query", "report_selected_entry_key"),
    ("관심종목", "watchlist_query", "watchlist_selected_entry_key"),
])
def test_search_selection_and_tab_roundtrip_preserve_state_without_execution(view, query_key, selection_key):
    from streamlit.testing.v1 import AppTest
    from tests.g05b_dashboard_fixture import render_fixture
    app = AppTest.from_function(render_fixture, default_timeout=20).run()
    app.radio[0].set_value(view).run()
    assert not app.exception
    next(item for item in app.text_input if item.key == query_key).input("삼성").run()
    assert not app.exception
    assert "005930" in str(app.session_state[selection_key])
    next(item for item in app.text_input if item.key == query_key).input("").run()
    selection = next(item for item in app.selectbox if item.key == selection_key)
    selection.select_index(1).run()
    chosen = app.session_state[selection_key]
    app.radio[0].set_value("홈").run()
    app.radio[0].set_value(view).run()
    assert not app.exception
    assert app.session_state[selection_key] == chosen
    assert sum(app.session_state["g05b_counts"].values()) == 0


def test_analysis_action_navigates_without_starting_any_job():
    from streamlit.testing.v1 import AppTest
    from tests.g05b_dashboard_fixture import render_fixture
    app = AppTest.from_function(render_fixture, default_timeout=20).run()
    action = next(item for item in app.button if item.key == "overview_next_action_0")
    assert action.label == "분석 갱신 열기"
    action.click().run()
    assert not app.exception
    assert app.radio[0].value == "데이터 갱신"
    assert sum(app.session_state["g05b_counts"].values()) == 0
