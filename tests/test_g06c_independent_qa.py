"""Independent G06c acceptance checks; all data is synthetic and local."""
from __future__ import annotations

import json
import re
from html.parser import HTMLParser
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest


def synthetic_main(folder):
    # Imports stay inside the function because AppTest executes its source.
    from datetime import date
    from pathlib import Path
    import streamlit as st
    from tests.g06c_layout_fixture import G06cHarness
    from tests.qa02_dashboard_fixture import NAMES

    class AcceptanceHarness(G06cHarness):
        def _seed(self):
            super()._seed()
            for symbol in NAMES:
                name = f"{symbol}_report.csv"
                frame = self.storage.load("market_reports", name)
                frame["summary"] = 'QA literal <img src=x onerror="bad"> & zero 0\n\nnext'
                frame["golden_cross_reason"] = 'QA reason <script>bad</script> & "quote"'
                frame["rsi_strategy_reason"] = 0
                self.storage.save("market_reports", name, frame)

    if "qa02_harness" not in st.session_state:
        st.session_state["qa02_harness"] = AcceptanceHarness(Path(folder))
        st.session_state["backtest_selected_symbols"] = ["005930"]
        st.session_state["backtest_selected_strategies"] = ["rsi", "golden-cross"]
        st.session_state["backtest_prepare_collection_period"] = (date(2025, 10, 22), date(2026, 10, 22))
    st.session_state["qa02_harness"].render()


class Block(HTMLParser):
    def __init__(self, source):
        super().__init__(convert_charrefs=True)
        self.classes = []
        self.tags = []
        self.words = []
        self.feed(source)

    def handle_starttag(self, tag, attrs):
        self.tags.append(tag)
        self.classes.extend(dict(attrs).get("class", "").split())

    def handle_data(self, data):
        self.words.append(data)

    @property
    def text(self):
        return " ".join(self.words)


@pytest.fixture
def app(tmp_path, monkeypatch):
    from invest_bot.config import AppSettings
    monkeypatch.setattr(AppSettings, "from_file", lambda *a, **k: pytest.fail("unexpected runtime settings"))
    result = AppTest.from_function(synthetic_main, kwargs={"folder": str(tmp_path / "synthetic")}, default_timeout=30).run()
    assert not result.exception
    return result


def visit(app, tab):
    app.button(key="nav_" + tab).click().run()
    assert not app.exception
    assert app.session_state["selected_tab"] == tab


def block(app, class_name, expected):
    found = [(item.value, Block(item.value)) for item in app.markdown]
    found = [(source, parsed) for source, parsed in found if class_name in parsed.classes]
    assert len(found) == 1
    source, parsed = found[0]
    assert parsed.classes.count(class_name) == expected
    assert not {"pre", "code", "img", "script"}.intersection(parsed.tags)
    assert not re.search(r"\n\s*\n[ \t]{4,}<", source)
    assert not any("<article" in item.value or "<div" in item.value for item in app.code)
    return parsed


def audit(app, tmp_path, label, *, backtest=False, runs=0):
    m = dict(app.session_state["g06c_measurement"])
    h = app.session_state["qa02_harness"]
    favorites = 0 if m["tab"] in ("홈", "백테스트") else 1
    assert m["snapshot_selects"] == 2
    assert m["favorite_selects_after_snapshot"] == favorites
    assert m["frame_consumer_selects"] == (10 if backtest else 0)
    assert m["total_selects"] == (12 if backtest else 2 + favorites)
    if backtest:
        assert (m["source_selects"], m["history_selects"]) == (8, 2)
    assert m["seed_count"] == 1
    assert m["job_calls"] == 0 and not m["forbidden_calls"] and not m["write_attempts"]
    assert len(m["runner_calls"]) == runs
    attempts = [dict(item) for item in h.sql_attempts]
    assert attempts and attempts[-1]["completed_render"]
    assert attempts[-1]["total_selects"] == m["total_selects"]
    assert sum(item["total_selects"] for item in attempts) == m["selects_all_script_attempts"]
    record = {"completed_render": m, "all_attempts": attempts, "seed_observed": False}
    (tmp_path / (label + "-measurement.json")).write_text(json.dumps(record, ensure_ascii=False, indent=2))


def execute(app):
    next(button for button in app.button if button.label == "백테스트 실행").click().run()
    app.run()  # Finish the application's explicit rerun before sending a widget event.
    assert not app.exception and not app.error
    return app.session_state["backtest_results"]


@pytest.mark.parametrize("family,tab,card,count", [
    ("home", "홈", "watch-target-card", 4),
    ("interpretation", "투자 리포트", "interpretation-card", 4),
    ("reason", "투자 리포트", "interpretation-reason-card", 16),
    ("readiness", "백테스트", "readiness-card", 2),
    ("result", "백테스트", "backtest-result-card", 3),
])
def test_actual_main_emits_complete_card_families(app, tmp_path, family, tab, card, count):
    if tab != "홈":
        visit(app, tab)
    if tab == "투자 리포트":
        app.toggle(key="report_interpretation_overview_open").set_value(True).run()
    if family == "result":
        execute(app)
    parsed = block(app, card, count)
    if family in ("home", "interpretation"):
        assert 'QA literal <img src=x onerror="bad"> & zero 0' in parsed.text
    if family == "reason":
        assert 'QA reason <script>bad</script> & "quote"' in parsed.text
        assert re.search(r"\b0\b", parsed.text)
        assert "판단 근거가 아직 없습니다." in parsed.text
        # Four adjacent strategies must belong to each symbol, not interleave.
        names = [name for name in ("삼성전자", "SK하이닉스", "NAVER", "현대차") if name in parsed.text]
        assert len(names) == 4
        for name in names:
            assert parsed.text.count(name) == 4
    audit(app, tmp_path, family, backtest=tab == "백테스트", runs=3 if family == "result" else 0)


def test_report_controls_precede_optional_grid_and_restore_route_state(app, tmp_path):
    visit(app, "투자 리포트")
    assert not app.toggle(key="report_interpretation_overview_open").value
    app.toggle(key="report_favorites_only").set_value(True).run()
    app.selectbox(key="report_sort_option").select("종목명순").run()
    app.text_input(key="report_query").input("현대").run()
    chosen = app.session_state["report_selected_entry_key"]
    assert "005380" in chosen
    app.toggle(key="report_interpretation_overview_open").set_value(True).run()
    # Native element traversal proves control order, not just markdown order.
    nodes = list(app.main)
    grid = next(i for i, node in enumerate(nodes) if node.type == "markdown" and "interpretation-card" in Block(node.value).classes)
    for key in ("report_query", "report_favorites_only", "report_sort_option", "report_selected_entry_key"):
        assert next(i for i, node in enumerate(nodes) if getattr(node, "key", None) == key) < grid
    visit(app, "홈")
    visit(app, "투자 리포트")
    assert app.session_state["report_selected_entry_key"] == chosen
    assert app.text_input(key="report_query").value == "현대"
    app.text_input(key="report_query").input("absent-symbol-QA").run()
    assert any("현재 검색 조건에 맞는 리포트가 없습니다" in item.value for item in app.warning)
    audit(app, tmp_path, "report-route")


def test_watchlist_board_bypasses_detail_filter_then_restores_clicked_report(app, tmp_path):
    visit(app, "관심종목")
    app.text_input(key="watchlist_query").input("NAVER").run()
    assert len(app.selectbox(key="watchlist_selected_entry_key").options) == 1
    assert sum(Block(item.value).classes.count("watchlist-symbol-card__topline") for item in app.markdown) == 4
    target = next(button for button in app.button if button.key and button.key.startswith("watchlist_overview_") and button.key.endswith("_000660"))
    target.click().run()
    assert not app.exception
    assert app.text_input(key="watchlist_query").value == ""
    chosen = app.session_state["watchlist_selected_entry_key"]
    assert "000660" in chosen
    visit(app, "투자 리포트")
    visit(app, "관심종목")
    assert app.session_state["watchlist_selected_entry_key"] == chosen
    assert len(app.selectbox(key="watchlist_selected_entry_key").options) == 4
    audit(app, tmp_path, "watchlist-route")


def test_backtest_disclosure_and_preview_do_not_repeat_execution(app, tmp_path):
    visit(app, "백테스트")
    flow = next(item for item in app.expander if item.label == "전략 검증 흐름")
    assert not flow.proto.expanded
    audit(app, tmp_path, "backtest-before", backtest=True)
    result = execute(app)
    original = result["summary_frame"].copy(deep=True)
    assert len(original) == 3 and set(original.input_row_count) == {4}
    app.multiselect(key="backtest_selected_strategies").select("trend-filter").run()
    import pandas as pd
    pd.testing.assert_frame_equal(app.session_state["backtest_results"]["summary_frame"], original)
    block(app, "readiness-card", 3)
    block(app, "backtest-result-card", 3)
    assert not result.get("saved_artifacts")
    assert any(button.label == "실행 결과 저장" for button in app.button)
    assert not any("선택 종목" == item.label for item in app.expander)
    audit(app, tmp_path, "backtest-preview", backtest=True, runs=3)


def test_explicit_save_persists_real_artifacts_once(app, tmp_path, monkeypatch):
    from invest_bot.dashboard import streamlit_backtest as module
    from invest_bot.dashboard.service import DashboardDataService
    from tests.test_streamlit_backtest import _FakeStreamlit
    visit(app, "백테스트")
    results = dict(execute(app))
    output = tmp_path / "explicit-save"
    service = DashboardDataService(processed_root=output)
    screen = _FakeStreamlit()
    monkeypatch.setattr(module, "st", screen)
    module._render_save_results_panel(service, results)
    assert not output.exists() and not results.get("saved_artifacts")
    screen.button_values[module.BACKTEST_SAVE_RESULTS_KEY] = True
    module._render_save_results_panel(service, results)
    assert not screen.error_messages
    paths = [Path(path) for path in results["saved_artifacts"]]
    assert len(paths) == 6 and all(path.is_file() and path.stat().st_size for path in paths)
    before = {str(path): path.read_bytes() for path in paths}
    module._render_save_results_panel(service, results)
    assert {str(path): path.read_bytes() for path in output.rglob("*.csv")} == before


def test_emitted_css_keeps_mobile_and_accessibility_contracts(monkeypatch):
    from invest_bot.dashboard import streamlit_styles as styles
    from tests.test_streamlit_backtest import _FakeStreamlit
    screen = _FakeStreamlit()
    monkeypatch.setattr(styles, "st", screen)
    styles.apply_custom_style()
    css = "\n".join(screen.markdown_calls)
    mobile = css.split("@media (max-width: 760px)")[-1]
    for selector in (".readiness-card-grid", ".backtest-result-grid"):
        assert selector in mobile and "grid-template-columns: 1fr;" in mobile
        desktop = css[:css.index("@media (max-width: 760px)")]
        assert re.search(re.escape(selector) + r"[^{}]*\{[^{}]*grid-template-columns:\s*repeat\(4,\s*minmax\(0,\s*1fr\)\)", desktop)
    sizes = [float(value) for value in re.findall(r"font-size:\s*([\d.]+)rem", css)]
    assert sizes and min(sizes) >= 0.8
    assert "Material Symbols Rounded" in css and "Material Symbols Outlined" in css
    assert "button:focus-visible" in css and "outline: 2px solid var(--app-accent)" in css
    assert "outline-offset: 2px" in css
