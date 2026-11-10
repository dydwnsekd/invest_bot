"""G06c renderer and real navigation contracts; browser DOM belongs to main QA."""
from __future__ import annotations

from html.parser import HTMLParser
import re
from types import SimpleNamespace

import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

from invest_bot.config.settings import AppSettings
from invest_bot.dashboard import streamlit_backtest as backtest
from invest_bot.dashboard import streamlit_interpretations as interpretations
from invest_bot.dashboard import streamlit_overview as overview
from invest_bot.dashboard import streamlit_styles as styles
from invest_bot.dashboard.service import DashboardDataService
from tests.qa02_dashboard_fixture import ROOT
from tests.test_streamlit_backtest import _FakeStreamlit


class CardHTML(HTMLParser):
    def __init__(self):
        super().__init__()
        self.classes = []
        self.tags = []
        self.content = []

    def handle_starttag(self, tag, attrs):
        self.tags.append(tag)
        self.classes.extend(dict(attrs).get("class", "").split())

    def handle_data(self, text):
        self.content.append(text)


def cards(markup, card_class, count):
    # An HTML block ends at a blank line in CommonMark; the next indented
    # article becomes a code block. Test actual renderer output at that boundary.
    assert not re.search(r"\n[ \t]*\n[ \t]{4,}<", markup), markup
    assert not re.search(r"\n[ \t]*\n", markup), markup
    parsed = CardHTML()
    parsed.feed(markup)
    assert parsed.classes.count(card_class) == count
    assert "script" not in parsed.tags and "img" not in parsed.tags
    return " ".join(parsed.content)


def emitted(screen, marker):
    return next(body for body in screen.markdown_calls if marker in body)


@pytest.mark.parametrize("selector", [".readiness-card-grid", ".backtest-result-grid"])
@pytest.mark.parametrize("width,expected", [(390, "1fr"), (760, "1fr"),
                                           (761, "repeat(4, minmax(0, 1fr))"),
                                           (1920, "repeat(4, minmax(0, 1fr))")])
def test_actual_css_stacks_backtest_cards_at_mobile_breakpoint(monkeypatch, selector, width, expected):
    screen = _FakeStreamlit()
    monkeypatch.setattr(styles, "st", screen)
    styles.apply_custom_style()
    desktop, mobile = screen.markdown_calls[0].split("@media (max-width: 760px)", 1)
    # This stylesheet has one media breakpoint. Check its emitted cascade,
    # including the desktop side of the boundary; actual DOM is main-owned.
    applicable = desktop + mobile if width <= 760 else desktop
    columns = None
    for selectors, declarations in re.findall(r"([^{}]+)\{([^{}]*)\}", applicable):
        if selector in [item.strip() for item in selectors.split(",")]:
            declaration = re.search(r"grid-template-columns:\s*([^;]+);", declarations)
            if declaration:
                columns = re.sub(r"\s+", "", declaration.group(1))
    assert columns == re.sub(r"\s+", "", expected)


def test_home_actual_renderer_multiple_candidates_escape_and_order(monkeypatch):
    screen = _FakeStreamlit()
    monkeypatch.setattr(overview, "st", screen)
    rows = []
    for index, state in enumerate(["buy", "watch", "sell", "hold"]):
        preview = SimpleNamespace(symbol=f"{index:06}", symbol_name=f"종목{index}")
        row = pd.Series({"symbol": preview.symbol, "symbol_name": f"종목{index}<script>&\"",
                         "final_opinion": state, "trend_state": "bullish", "summary": "0 <img>\n\n& 근거"})
        rows.append((preview, row))
    overview.render_watch_targets(rows, [], service=DashboardDataService())
    text = cards(emitted(screen, "watch-target-grid"), "watch-target-card", 4)
    assert [text.index(f"종목{index}") for index in range(4)] == sorted(text.index(f"종목{index}") for index in range(4))
    assert "<script>" in text and "<img>" in text and "0" in text
    assert all(label in text for label in ["매수 관점", "관심 관찰", "매도 관점", "관망"])


@pytest.mark.parametrize("family", ["interpretation", "reason"])
def test_interpretations_and_reasons_actual_renderer_states_missing_zero_escape(family):
    rows = [{"종목": f"종목{index}<script>", "날짜": "2026-10-22", "최종 의견": state,
             "추세": 0, "골든크로스": state, "한 줄 해석": "<img>\n\n& 설명"}
            for index, state in enumerate(["매수 관점", "매도 관점", "관망", "정보 부족"])]
    if family == "interpretation":
        text = cards(interpretations.render_interpretation_cards(rows), "interpretation-card", 4)
        assert all(state in text for state in ["매수 관점", "매도 관점", "관망", "정보 부족"])
        assert "0" in text and "<img>" in text
        return
    reasons = [{"종목": row["종목"], "전략": "RSI", "판단": row["최종 의견"], "근거": "0 <img> & 근거"} for row in rows]
    assert "0 <img> & 근거" in cards(interpretations.render_strategy_reason_cards(reasons), "interpretation-reason-card", 4)
    entries = [{"symbol": "005930", "symbol_name": "가상", "frame": pd.DataFrame([{"final_opinion": "unknown"}])}]
    missing = interpretations.build_strategy_reason_rows(entries, DashboardDataService())
    assert all(row["근거"] == "판단 근거가 아직 없습니다." for row in missing)
    assert "판단 근거가 아직 없습니다." in cards(interpretations.render_strategy_reason_cards(missing), "interpretation-reason-card", 4)


@pytest.mark.parametrize("family", ["readiness", "result"])
def test_backtest_actual_readiness_and_result_renderers_three_cards(monkeypatch, family):
    screen = _FakeStreamlit()
    monkeypatch.setattr(backtest, "st", screen)
    rows = pd.DataFrame([{"symbol": "005930", "symbol_name": "가상<script>", "strategy_name": f"전략{index}<img>",
                          "ready": "준비 완료" if index == 0 else "차단", "blocking_reasons": "-" if index == 0 else "자료 없음 & 확인"}
                         for index in range(3)])
    backtest._render_readiness_panel({"rows": rows, "total_count": 3, "ready_count": 1, "can_run": False,
                                      "blocked_reasons": ("자료 없음 & 확인",)})
    if family == "readiness":
        text = cards(emitted(screen, "readiness-card-grid"), "readiness-card", 3)
        assert "준비 완료" in text and "차단" in text and "자료 없음 & 확인" in screen.warning_messages[0]
        return
    summaries = pd.DataFrame([{"symbol": "005930", "symbol_name": "가상<script>", "strategy_name": f"전략{index}<img>",
                              "total_return_pct": value, "trade_count": 0, "win_rate_pct": 0., "max_drawdown_pct": 0.}
                             for index, value in enumerate([0., 12., -3.])])
    bundle = {"summary_frame": summaries, "comparison_frame": summaries, "trade_frame": pd.DataFrame(),
              "history_warnings": ("이력 경고 유지",)}
    backtest._render_results_panel(DashboardDataService(), bundle)
    text = cards(emitted(screen, "backtest-result-grid"), "backtest-result-card", 3)
    assert "0%" in text and "12%" in text and "-3%" in text
    assert "거래 0건" in text and "기록 없음" in text
    assert "이력 경고 유지" in screen.warning_messages


@pytest.fixture
def real_app(monkeypatch):
    monkeypatch.setattr(AppSettings, "from_file", lambda *a, **kw: pytest.fail("runtime config read"))
    app = AppTest.from_file(str(ROOT / "tests/g06c_layout_fixture.py"), default_timeout=30).run()
    assert not app.exception
    return app


def nav(app, name):
    app.button(key=f"nav_{name}").click().run()
    assert not app.exception
    assert app.session_state["selected_tab"] == name


def read_measurement(app, *, favorites):
    value = app.session_state["g06c_measurement"]
    assert value["frame_consumer_selects"] == 0
    assert value["favorite_selects_after_snapshot"] == favorites
    assert value["total_selects"] == value["snapshot_selects"] + favorites
    assert value["job_calls"] == 0 and value["forbidden_calls"] == []
    assert value["write_attempts"] == [] and value["runner_calls"] == [] and value["seed_count"] == 1


@pytest.mark.parametrize("view,query,selection,sort", [
    ("투자 리포트", "report_query", "report_selected_entry_key", "report_sort_option"),
    ("관심종목", "watchlist_query", "watchlist_selected_entry_key", "watchlist_sort_option"),
])
def test_actual_sidebar_search_sort_selection_restore_without_writes_or_jobs(real_app, view, query, selection, sort):
    app = real_app
    read_measurement(app, favorites=0)
    nav(app, view)
    app.text_input(key=query).input("삼성").run()
    assert not app.exception
    assert "005930" in app.session_state[selection]
    read_measurement(app, favorites=1)
    app.text_input(key=query).input("").run()
    app.selectbox(key=sort).select("종목명순").run()
    app.selectbox(key=selection).select_index(1).run()
    chosen = app.session_state[selection]
    nav(app, "홈")
    nav(app, view)
    assert app.session_state[selection] == chosen
    read_measurement(app, favorites=1)
    if view == "투자 리포트":
        app.toggle(key="report_interpretation_overview_open").set_value(True).run()
        assert not app.exception
        bodies = [item.value for item in app.markdown]
        cards(next(body for body in bodies if "<div class='interpretation-grid'>" in body), "interpretation-card", 4)
        # The optional comparison follows the main selector/candidates.
        assert bodies.index(next(body for body in bodies if "리포트 후보" in body)) < bodies.index(next(body for body in bodies if "<div class='interpretation-grid'>" in body))
        read_measurement(app, favorites=1)
        app.text_input(key=query).input("없는종목").run()
        assert not app.exception
        assert app.toggle(key="report_interpretation_overview_open").value
        assert any("현재 검색 조건에 맞는 리포트가 없습니다." in item.value for item in app.warning)
        read_measurement(app, favorites=1)
    else:
        app.text_input(key=query).input("삼성").run()
        assert sum('<div class="watchlist-symbol-card__topline">' in item.value for item in app.markdown) == 4
        assert len(app.selectbox(key=selection).options) == 1
        bodies = [item.value for item in app.markdown]
        assert bodies.index(next(body for body in bodies if "상세 리포트 선택" in body)) < bodies.index(next(body for body in bodies if "등록한 관심종목 전체</h3>" in body))
        next(button for button in app.button if button.key and button.key.startswith("watchlist_overview_") and button.key.endswith("_005380")).click().run()
        assert not app.exception
        assert app.text_input(key=query).value == ""
        assert "005380" in app.session_state[selection]
        read_measurement(app, favorites=1)


def test_actual_seeded_backtest_runs_only_on_click_and_retains_results(real_app):
    app = real_app
    nav(app, "백테스트")
    assert app.multiselect(key="backtest_selected_symbols").value == ["005930"]
    assert app.multiselect(key="backtest_selected_strategies").value == ["rsi", "golden-cross"]
    measurement = app.session_state["g06c_measurement"]
    assert measurement["runner_calls"] == [] and measurement["write_attempts"] == []
    assert measurement["source_selects"] == 8 and measurement["history_selects"] == 2
    assert measurement["snapshot_selects"] == 2 and measurement["total_selects"] == 12
    bodies = [item.value for item in app.markdown]
    cards(next(body for body in bodies if '<div class="readiness-card-grid">' in body), "readiness-card", 2)
    next(button for button in app.button if button.label == "백테스트 실행").click().run()
    # Drain the explicit st.rerun before sending the next widget event. AppTest
    # otherwise keeps the pre-rerun multiselect ID for its first interaction.
    app.run()
    assert not app.exception
    assert not app.error
    bundle = app.session_state["backtest_results"]
    assert len(bundle["summary_frame"]) == 3
    assert set(bundle["summary_frame"].input_row_count) == {4}
    assert len(app.session_state["g06c_measurement"]["runner_calls"]) == 3
    cards(next(item.value for item in app.markdown if '<div class="backtest-result-grid">' in item.value), "backtest-result-card", 3)
    # A third preview strategy yields 3 readiness cards; frozen execution still
    # has exactly the three previous results and does not run automatically.
    app.multiselect(key="backtest_selected_strategies").select("trend-filter").run()
    assert not app.exception
    cards(next(item.value for item in app.markdown if '<div class="readiness-card-grid">' in item.value), "readiness-card", 3)
    cards(next(item.value for item in app.markdown if '<div class="backtest-result-grid">' in item.value), "backtest-result-card", 3)
    measurement = app.session_state["g06c_measurement"]
    assert len(measurement["runner_calls"]) == 3
    assert measurement["source_selects"] == 8 and measurement["history_selects"] == 2
    assert measurement["write_attempts"] == [] and measurement["job_calls"] == 0 and measurement["forbidden_calls"] == []
    assert any("저장" in caption.value for caption in app.caption)
    assert any(button.label == "실행 결과 저장" for button in app.button)
