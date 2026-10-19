from datetime import date

import pytest
from streamlit.testing.v1 import AppTest

from tests.g06a_action_fixture import render_action_fixture


BUTTONS = ("데이터 수집", "전체 파이프라인", "지표 계산", "신호 생성", "리포트 생성")
SYMBOLS = ["005930", "000660"]


def start_app(**kwargs):
    app = AppTest.from_function(render_action_fixture, kwargs=kwargs, default_timeout=15).run()
    assert not app.exception
    return app


def visible_text(app):
    return "\n".join(item.value for group in (app.caption, app.markdown, app.info, app.warning, app.error, app.success) for item in group)


def click(app, label):
    next(button for button in app.button if button.label == label).click().run()
    assert not app.exception


@pytest.mark.parametrize("webhook,expected", [("configured", "설정됨"), ("empty", "미설정"), ("whitespace", "미설정")])
def test_initial_notice_discloses_scope_without_executing_or_exposing_webhook(webhook, expected):
    app = start_app(webhook=webhook)
    text = visible_text(app)
    assert f"Discord 전송 설정: {expected}" in text
    assert "실행 대상: 삼성전자 (005930) · 총 1개" in text
    assert "수집 성공 종목만" in text
    assert "저장된 지표·신호·수급" in text
    assert "Discord 전송 없음" in text
    if webhook == "configured":
        assert "성공 여부는 실행 결과" in text
    else:
        assert "전송은 건너뜁니다" in text
    assert "synthetic-token" not in text and "example.invalid" not in text
    assert app.session_state["g06a_calls"] == []


def test_selection_period_and_configuration_changes_only_update_notice():
    app = start_app()
    app.multiselect[0].set_value(SYMBOLS + ["035420", "005380"]).run()
    app.date_input[0].set_value((date(2026, 9, 1), date(2026, 10, 1))).run()
    app.toggle[0].set_value(False).run()
    assert not app.exception
    text = visible_text(app)
    assert "외 1개 · 총 4개" in text
    assert "2026-09-01 ~ 2026-10-01" in text
    assert "Discord 전송 설정: 미설정" in text
    assert app.session_state["g06a_calls"] == []
    app.multiselect[0].set_value([]).run()
    assert "실행 대상: 선택 없음" in visible_text(app)
    assert app.session_state["g06a_calls"] == []


@pytest.mark.parametrize("label", BUTTONS)
def test_explicit_button_keeps_existing_selected_symbol_and_step_calls(label):
    app = start_app()
    app.multiselect[0].set_value(SYMBOLS).run()
    assert app.session_state["g06a_calls"] == []
    click(app, label)
    calls = app.session_state["g06a_calls"]
    if label in ("데이터 수집", "전체 파이프라인"):
        assert calls[0][:2] == ("collect", tuple(SYMBOLS))
        assert isinstance(calls[0][2], int)
    if label == "전체 파이프라인":
        assert calls[1:] == [
            (kind, symbol, "discord", True) if kind == "report" else (kind, symbol)
            for symbol in SYMBOLS for kind in ("indicators", "signals", "report")
        ]
    elif label == "데이터 수집":
        assert len(calls) == 1
    else:
        kind = {"지표 계산": "indicators", "신호 생성": "signals", "리포트 생성": "report"}[label]
        assert calls == [(kind, symbol, "discord", True) if kind == "report" else (kind, symbol) for symbol in SYMBOLS]
    assert app.session_state["action_message_type"] == "success"


@pytest.mark.parametrize("label", BUTTONS)
def test_empty_selection_click_never_starts_a_job(label):
    app = start_app()
    app.multiselect[0].set_value([]).run()
    click(app, label)
    assert app.session_state["g06a_calls"] == []
    assert app.session_state["action_message_type"] == "error"
    assert "종목을 하나 이상 선택" in app.session_state["action_message"]


@pytest.mark.parametrize("label", ["리포트 생성", "전체 파이프라인"])
@pytest.mark.parametrize("webhook,delivery,detail", [("empty", "sent", "웹훅 미설정"), ("configured", "failed", "HTTP 500")])
def test_click_preserves_skipped_or_failed_delivery_warning(label, webhook, delivery, detail):
    app = start_app(webhook=webhook, delivery=delivery)
    app.multiselect[0].set_value(SYMBOLS).run()
    click(app, label)
    reports = [call for call in app.session_state["g06a_calls"] if call[0] == "report"]
    assert reports == [("report", symbol, "discord", webhook == "configured") for symbol in SYMBOLS]
    assert app.session_state["action_message_type"] == "warning"
    assert detail in app.session_state["action_message"]
    assert "Discord 전송 경고" in visible_text(app)


def test_pipeline_only_processes_successful_collection_symbols():
    app = start_app(collection="partial")
    app.multiselect[0].set_value(SYMBOLS).run()
    click(app, "전체 파이프라인")
    calls = app.session_state["g06a_calls"]
    assert calls[0][:2] == ("collect", tuple(SYMBOLS))
    assert calls[1:] == [("indicators", "005930"), ("signals", "005930"), ("report", "005930", "discord", True)]
    assert app.session_state["action_message_type"] == "warning"
    assert "수집 실패 1개" in app.session_state["action_message"]


def test_pipeline_stops_after_total_collection_failure():
    app = start_app(collection="none")
    app.multiselect[0].set_value(SYMBOLS).run()
    click(app, "전체 파이프라인")
    assert len(app.session_state["g06a_calls"]) == 1
    assert app.session_state["g06a_calls"][0][0] == "collect"
    assert app.session_state["action_message_type"] == "error"
    assert "리포트를 갱신하지 않았습니다" in app.session_state["action_message"]
