"""Independent cross-feature QA02 checks; no product/owned test replacement."""
from __future__ import annotations

from datetime import date
import base64
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

from invest_bot.config.settings import AppSettings
from invest_bot.dashboard.data_status import build_report_data_status, build_snapshot_data_statuses
from invest_bot.dashboard.streamlit_state import DashboardFrameLoader
from tests.qa02_dashboard_fixture import QA02Harness, ROOT


APP_FILE = ROOT / "tests/qa02_dashboard_fixture.py"


@pytest.fixture(autouse=True)
def deny_implicit_operational_settings(monkeypatch):
    def denied(*_args, **_kwargs):
        pytest.fail("independent QA02 must not read runtime config")
    monkeypatch.setattr(AppSettings, "from_file", denied)


def start():
    app = AppTest.from_file(str(APP_FILE), default_timeout=30).run()
    assert not app.exception
    return app


def text(app):
    return "\n".join(str(item.value) for group in (app.markdown, app.caption, app.warning, app.info, app.error, app.success) for item in group)


def nav(app, name):
    next(button for button in app.button if button.key == f"nav_{name}").click().run()
    assert not app.exception
    assert app.session_state["selected_tab"] == name
    return app


def click(app, label):
    next(button for button in app.button if button.label == label).click().run()
    assert not app.exception


def measurement(app):
    value = app.session_state["qa02_measurement"]
    assert value["frame_consumer_selects"] == 0
    assert value["forbidden_calls"] == []
    assert value["snapshot_selects"] == 2  # real stock-name SELECT + batched frame SELECT
    assert value["total_selects"] == value["snapshot_selects"] + value["favorite_selects_after_snapshot"]
    return value


def test_actual_main_home_report_watchlist_navigation_and_sql_boundaries():
    app = start()
    assert "분석 갱신" in text(app)
    assert measurement(app)["total_selects"] == 2
    harness = app.session_state["qa02_harness"]
    for view in ("투자 리포트", "관심종목", "홈", "데이터 갱신", "투자 리포트"):
        previous_attempts = len(harness.sql_attempts)
        nav(app, view)
        current = measurement(app)
        assert current["favorite_selects_after_snapshot"] == (1 if view in {"투자 리포트", "관심종목"} else 0)
        assert current["job_calls"] == 0
        attempts = harness.sql_attempts[previous_attempts:]
        assert attempts[-1]["completed_render"]
        assert sum(attempt["total_selects"] for attempt in attempts) >= current["total_selects"]
        assert all(attempt["frame_consumer_selects"] == 0 for attempt in attempts)
    assert app.session_state["qa02_calls"] == []


@pytest.mark.parametrize("view,query_key,selection_key", [
    ("투자 리포트", "report_query", "report_selected_entry_key"),
    ("관심종목", "watchlist_query", "watchlist_selected_entry_key"),
])
def test_search_selection_and_real_sidebar_roundtrip_preserve_stored_report(view, query_key, selection_key):
    app = start()
    nav(app, view)
    next(widget for widget in app.text_input if widget.key == query_key).input("삼성").run()
    assert not app.exception
    assert "005930" in str(app.session_state[selection_key])
    assert "원본 가격 2026-10-22" in text(app)
    assert "판단 리포트 2026-10-21" in text(app)
    assert "분석 갱신" in text(app)
    next(widget for widget in app.text_input if widget.key == query_key).input("").run()
    next(widget for widget in app.selectbox if widget.key == selection_key).select_index(1).run()
    chosen = app.session_state[selection_key]
    nav(app, "홈")
    nav(app, view)
    assert app.session_state[selection_key] == chosen
    assert measurement(app)["job_calls"] == 0


def test_snapshot_states_and_selected_report_preserve_dates_without_consumer_queries(tmp_path):
    harness = QA02Harness(tmp_path)
    with harness.observe():
        snapshot = harness.service.build_snapshot()
        assert len(harness.selects) == 2
        harness.selects.clear()
        states = build_snapshot_data_statuses(harness.service, snapshot, today=date(2026, 10, 22))
        by_symbol = {state.symbol: state for state in states}
        assert by_symbol["005930"].label == "분석 갱신 필요"
        assert by_symbol["000660"].label == "데이터 갱신 필요"
        assert by_symbol["035420"].label == "기준일 불일치"
        assert by_symbol["005380"].label == "최신"
        selected = build_report_data_status(harness.service, snapshot, "005380", pd.Series({"date": "2026-10-20"}), today=date(2026, 10, 22))
        assert selected.report_date == date(2026, 10, 20)
        assert selected.daily_date == date(2026, 10, 22)
        assert selected.label == "분석 갱신 필요"
        assert harness.selects == []


def test_actual_sqlite_summary_observations_missing_misaligned_and_detail_precedence(tmp_path):
    harness = QA02Harness(tmp_path)
    with harness.observe():
        snapshot = harness.service.build_snapshot()
        harness.selects.clear()
        loader = DashboardFrameLoader(harness.service, snapshot.latest_records)
        summary = loader.load_professional("005930")
        assert summary.attrs["investor_flow_source"] == "summary"
        assert summary["foreign_net"].iloc[[1, 3]].tolist() == [-11., 0.]
        assert summary["foreign_net"].iloc[[0, 2]].isna().all()
        assert pd.isna(summary["institutional_net"].iloc[3])
        missing = loader.load_professional("000660")
        assert missing.attrs["investor_flow_source"] is None
        assert "수급 데이터 없음" in missing.attrs["investor_flow_message"]
        mismatch = loader.load_professional("035420")
        assert mismatch["foreign_net"].isna().all()
        assert "일치하지" in mismatch.attrs["investor_flow_message"]
        detail = loader.load_professional("005380")
        assert detail.attrs["investor_flow_source"] == "detail"
        assert detail["foreign_net"].iloc[-1] == 0.
        assert detail["foreign_net"].iloc[:-1].isna().all()
        assert "institutional_net" not in detail  # no summary gap filling
        summary.loc[1, "foreign_net"] = 999.
        assert loader.load_professional("005930")["foreign_net"].iloc[1] == -11.
        assert harness.selects == []


@pytest.mark.parametrize("timeframe,expected", [("daily", [-11., 0.]), ("weekly", [-11.]), ("monthly", [-11.])])
def test_summary_chart_and_actual_controls_render_from_snapshot(timeframe, expected):
    app = start()
    nav(app, "투자 리포트")
    app.text_input(key="report_query").input("삼성").run()
    assert not app.exception
    assert "요약의 실제 관측일" in text(app)
    assert app.get("plotly_chart")
    next(widget for widget in app.radio if widget.label == "봉 기준").set_value(timeframe).run()
    assert not app.exception
    spec = json.loads(app.get("plotly_chart")[0].proto.spec)
    foreign = [trace for trace in spec["data"] if trace.get("name") == "외국인 순매수"]
    assert len(foreign) == 1
    values = foreign[0]["y"]
    if isinstance(values, dict):
        values = np.frombuffer(base64.b64decode(values["bdata"]), dtype=values["dtype"])
    observed = [value for value in values if not pd.isna(value)]
    assert observed == expected
    assert any(trace["type"] == "candlestick" for trace in spec["data"])
    assert measurement(app)["frame_consumer_selects"] == 0
    assert app.session_state["qa02_calls"] == []


def test_action_selection_period_and_webhook_notice_changes_do_not_execute():
    app = start()
    nav(app, "데이터 갱신")
    app.multiselect(key="multi_symbol_picker").set_value(["005930", "000660"]).run()
    app.date_input(key="action_collection_period").set_value((date(2026, 9, 1), date(2026, 10, 20))).run()
    app.toggle(key="qa02_configured").set_value(True).run()
    assert not app.exception
    visible = text(app)
    assert "삼성전자 (005930)" in visible and "SK하이닉스 (000660)" in visible
    assert "2026-09-01 ~ 2026-10-20" in visible and "전송 설정: 설정됨" in visible
    assert "qa02-never-delivered" not in visible and "example.invalid" not in visible
    assert measurement(app)["job_calls"] == 0


@pytest.mark.parametrize("label", ["데이터 수집", "전체 파이프라인", "지표 계산", "신호 생성", "리포트 생성"])
def test_explicit_five_buttons_preserve_step_order_targets_and_delivery_request(label):
    app = start()
    nav(app, "데이터 갱신")
    symbols = ["000660", "005380"]
    app.multiselect(key="multi_symbol_picker").set_value(symbols).run()
    app.toggle(key="qa02_configured").set_value(True).run()
    assert app.session_state["qa02_calls"] == []
    click(app, label)
    calls = app.session_state["qa02_calls"]
    if label in {"데이터 수집", "전체 파이프라인"}:
        assert calls[0][0:2] == ("collect", tuple(symbols))
        assert isinstance(calls[0][2], int)
    expected_steps = [(kind, symbol, "discord", True) if kind == "report" else (kind, symbol)
                      for symbol in symbols for kind in ("indicators", "signals", "report")]
    if label == "전체 파이프라인":
        assert calls[1:] == expected_steps
    elif label == "데이터 수집":
        assert len(calls) == 1
    else:
        kind = {"지표 계산": "indicators", "신호 생성": "signals", "리포트 생성": "report"}[label]
        assert calls == [(kind, symbol, "discord", True) if kind == "report" else (kind, symbol) for symbol in symbols]
    assert app.session_state["action_message_type"] == "success"
    assert measurement(app)["forbidden_calls"] == []


@pytest.mark.parametrize("collection,status", [("partial", "warning"), ("none", "error")])
def test_pipeline_partial_or_total_collection_failure_limits_downstream_targets(collection, status):
    app = start()
    nav(app, "데이터 갱신")
    app.multiselect(key="multi_symbol_picker").set_value(["005380", "000660"]).run()
    app.selectbox(key="qa02_collection").select(collection).run()
    app.toggle(key="qa02_configured").set_value(True).run()
    click(app, "전체 파이프라인")
    calls = app.session_state["qa02_calls"]
    assert calls[0][:2] == ("collect", ("005380", "000660"))
    assert calls[1:] == ([("indicators", "005380"), ("signals", "005380"), ("report", "005380", "discord", True)] if collection == "partial" else [])
    assert app.session_state["action_message_type"] == status


@pytest.mark.parametrize("label", ["리포트 생성", "전체 파이프라인"])
@pytest.mark.parametrize("configured,result,detail", [(False, "sent", "웹훅 미설정"), (True, "failed", "synthetic HTTP 500")])
def test_report_delivery_skipped_or_failed_is_not_announced_as_success(label, configured, result, detail):
    app = start()
    nav(app, "데이터 갱신")
    app.multiselect(key="multi_symbol_picker").set_value(["005380", "035420"]).run()
    app.toggle(key="qa02_configured").set_value(configured).run()
    app.selectbox(key="qa02_delivery").select(result).run()
    click(app, label)
    assert app.session_state["action_message_type"] == "warning"
    assert detail in app.session_state["action_message"]
    assert [call for call in app.session_state["qa02_calls"] if call[0] == "report"] == [
        ("report", symbol, "discord", configured) for symbol in ("005380", "035420")]
    assert "Discord 전송 경고" in text(app)


@pytest.mark.parametrize("label", ["데이터 수집", "전체 파이프라인", "지표 계산", "신호 생성", "리포트 생성"])
def test_empty_selection_does_not_execute_any_of_five_actions(label):
    app = start()
    nav(app, "데이터 갱신")
    app.multiselect(key="multi_symbol_picker").set_value([]).run()
    click(app, label)
    assert app.session_state["qa02_calls"] == []
    assert app.session_state["action_message_type"] == "error"
    assert "종목을 하나 이상 선택" in app.session_state["action_message"]


def test_snapshot_is_authoritative_and_refreshes_only_next_rerun(tmp_path):
    harness = QA02Harness(tmp_path)
    with harness.observe():
        old_snapshot = harness.service.build_snapshot()
        loader = DashboardFrameLoader(harness.service, old_snapshot.latest_records)
        old = loader.load_professional("005930")["foreign_net"].iloc[1]
        harness.storage.save("investor_daily_summary", "005930_summary.csv", pd.DataFrame({"trade_date": ["2026-10-19", "2026-10-22"], "foreign_net": [32., 10.]}))
        harness.selects.clear()
        assert loader.load_professional("005930")["foreign_net"].iloc[1] == old == -11.
        assert DashboardFrameLoader(harness.service, ()).load_professional("005930") is None
        assert harness.selects == []
        new_snapshot = harness.service.build_snapshot()
        assert len(harness.selects) == 2
        harness.selects.clear()
        assert DashboardFrameLoader(harness.service, new_snapshot.latest_records).load_professional("005930")["foreign_net"].iloc[1] == 32.
        assert harness.selects == []


def test_without_snapshot_sqlite_loader_cache_is_request_local(tmp_path):
    harness = QA02Harness(tmp_path)
    with harness.observe():
        loader = DashboardFrameLoader(harness.service)
        assert loader.load_professional("005930")["foreign_net"].iloc[1] == -11.
        initial_queries = len(harness.selects)
        assert initial_queries == 4
        harness.selects.clear()
        assert loader.load_professional("005930")["foreign_net"].iloc[1] == -11.
        assert harness.selects == []


def actual_daily_flow_traces():
    """Use the actual app/selector/builder/render path, not a hand-built chart."""
    app = start()
    nav(app, "투자 리포트")
    app.text_input(key="report_query").input("삼성").run()
    assert not app.exception
    spec = json.loads(app.get("plotly_chart")[0].proto.spec)
    return app, {trace.get("name"): trace for trace in spec["data"]}


def trace_values(trace):
    values = trace["y"]
    if isinstance(values, dict):
        values = np.frombuffer(base64.b64decode(values["bdata"]), dtype=values["dtype"])
    return list(values)


@pytest.mark.parametrize("series,value", [
    pytest.param("기관 순매수", 5., id="isolated-positive"),
    pytest.param("외국인 순매수", -11., id="isolated-negative"),
    pytest.param("외국인 순매수", 0., id="isolated-real-zero"),
])
def test_isolated_observed_flow_values_have_visible_markers(series, value):
    app, traces = actual_daily_flow_traces()
    trace = traces[series]
    assert value in trace_values(trace)  # the value actually reaches the rendered trace
    assert "markers" in trace.get("mode", ""), (
        f"{series}={value} is isolated by missing days; lines-only renders no point for it"
    )
    assert trace.get("visible", True) is True
    assert trace.get("opacity", 1) > 0
    assert trace.get("marker", {}).get("size", 6) > 0
    assert trace.get("marker", {}).get("opacity", 1) > 0
    assert trace.get("connectgaps", False) is False
    assert measurement(app)["frame_consumer_selects"] == 0
    assert app.session_state["qa02_calls"] == []


def test_flow_gaps_remain_missing_without_zero_replacement_or_interpolation():
    app, traces = actual_daily_flow_traces()
    foreign = trace_values(traces["외국인 순매수"])
    institution = trace_values(traces["기관 순매수"])
    assert [pd.isna(value) for value in foreign] == [True, False, True, False]
    assert [foreign[1], foreign[3]] == [-11., 0.]
    assert [pd.isna(value) for value in institution] == [True, False, True, True]
    assert institution[1] == 5.
    assert all(traces[name].get("connectgaps", False) is False for name in ("외국인 순매수", "기관 순매수"))
    assert measurement(app)["frame_consumer_selects"] == 0
