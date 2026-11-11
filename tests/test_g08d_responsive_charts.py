"""G08d: actual emitter/layout, frozen traces and real SQLite/router contracts."""
from __future__ import annotations

import base64
from datetime import date
import hashlib
import json
import re
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

from invest_bot.config.settings import AppSettings
from invest_bot.dashboard import streamlit_charts as charts
from invest_bot.dashboard import streamlit_styles as styles
from invest_bot.dashboard.streamlit_state import DashboardFrameLoader
from tests.qa02_dashboard_fixture import QA02Harness, ROOT


# Captured from main66dbfed before any product edit, with unchanged QA02 data.
# Freeze all trace fields plus annotations/shapes/axis semantics. Only the
# presentation-only axis automargin and authorized UI-02 yaxis4.nticks are excluded.
BASELINE_DIGESTS = {
    "035420/daily": "99c01372ff92ed6cf6a9cb9a00f81250cd53943c2245fa0668fe0cc09c0828fb",
    "035420/weekly": "816de609b2090ae474356e0ab328ec086ce297fa4982c9ee5fc8a4fac102233c",
    "035420/monthly": "ba76cb87d74d5e61cb78aa057f80ee6b5954dc00c8e16e5cebd09cb4695e7156",
    "005380/daily": "3c80e4a9c77b573b7bb09bd18de65e41ba82b8ea0db8b8027c9a57c97c646e3b",
    "005380/weekly": "952bd97454732e748e83afef52ef536a7076a967fa03c546a911534e4fc5aaf3",
    "005380/monthly": "3b41c60d30389ba4ff49fe688187fe1a5499eb56c44dbd351113220b9b192d78",
    "005930/daily": "d7282144a6fec656ea54e37395c56dd4ca53f7100430e2a46b1fa5222fcb497d",
    "005930/weekly": "0379d0163c5926bd6fa609c501ab8eb0f57ae658540a88958f8f550bfcee6a08",
    "005930/monthly": "cb11becc81e12d2e3b44f25db0af4087668ad7ab302bb6cd27afbe423e6b8654",
    "generic/close_ma": "4022f462d0978545ba75d6314bb960efc578467ffc0ffe17c8ecf237e0c946e8",
    "generic/candlestick": "ddadc4d10817846e55e4b6c7d68153622d816b88cd36682e522b401615f6024d",
    "generic/volume": "c3f73bfe0c5c684aeb1e986e575724e523977dc468595325aded488bca0e83cc",
    "generic/rsi": "03bfdbf84b57f8e4d988e06ea932a5c33839090de78374c7a19fdd89d2417d70",
    "generic/flow": "1c2c668cfdaf33ebe97fa7fcf577df0d5825ae1712a90ea2cc77aa87a0aa3412",
    "generic/close_only": "9b54dc2806e34eff16e326a1ca7f5a8b05a9b2b40d44a66eb9cac61b5969eedf",
    "comparison/indexed": "9aee06ed7d84a95e49d3c665041db5efdd79eb9ac04e5d7e323b5a09c02fc56b",
    "comparison/price": "c8db4b6d6c55346abec1514c513a45aef4ff23e4925b2729e0c22ef0720af7cb"
}

SYMBOLS = ("035420", "005380", "005930")


def test_actual_css_keeps_plotly_auxiliary_svg_labels_at_least_point_eight_rem(monkeypatch):
    emitted = []
    monkeypatch.setattr(styles, "st", SimpleNamespace(markdown=lambda body, **kw: emitted.append(body)))
    styles.apply_custom_style()
    targets = {
        '[data-testid="stPlotlyChart"] text.legendtext',
        '[data-testid="stPlotlyChart"] g[class$="tick"] > text',
    }
    css = re.sub(r"/\*.*?\*/", "", emitted[0], flags=re.DOTALL)
    rules = [body for selectors, body in re.findall(r"([^{}]+)\{([^{}]*)\}", css)
             if {selector.strip() for selector in selectors.split(",")} == targets]
    assert len(rules) == 1, "Plotly legend and all subplot ticks need a scoped label-size rule"
    minimum = re.search(r"font-size:\s*([\d.]+)rem\s*!important\s*;", rules[0])
    assert minimum and float(minimum.group(1)) >= 0.8
    assert not re.search(r"font-(?:family|weight)|color\s*:|display\s*:", rules[0])
    # At main's measured root15px, 0.8rem must produce at least12px.
    assert float(minimum.group(1)) * 15 >= 12


def protected_spec(spec):
    layout = spec["layout"]
    return {
        "data": spec["data"],
        "annotations": layout.get("annotations", []),
        "shapes": layout.get("shapes", []),
        "axes": {
            key: {name: value for name, value in axis.items()
                  if name != "automargin" and not (key == "yaxis4" and name == "nticks")}
            for key, axis in layout.items() if key.startswith(("xaxis", "yaxis"))
        },
    }


def digest(spec):
    return hashlib.sha256(json.dumps(
        protected_spec(spec), sort_keys=True, ensure_ascii=False, separators=(",", ":"),
    ).encode()).hexdigest()


@pytest.fixture(scope="module")
def frames(tmp_path_factory):
    harness = QA02Harness(tmp_path_factory.mktemp("g08d-traces"))
    snapshot = harness.service.build_snapshot()
    loader = DashboardFrameLoader(harness.service, snapshot.latest_records)
    return {symbol: loader.load_professional(symbol) for symbol in SYMBOLS}


def figure_for(case, frames):
    group, kind = case.split("/")
    if group == "generic":
        return charts.build_chart(frames["005930"], kind, height=280, library="plotly")
    if group == "comparison":
        frame = charts.build_stock_comparison_frame({
            "가상A": frames["035420"], "가상B": frames["005930"],
        }).frame
        return charts.build_stock_comparison_chart(frame, basis=kind, library="plotly")
    aggregated = charts.aggregate_professional_chart_frame(frames[group], kind)
    return charts.build_professional_plotly_chart(aggregated, timeframe=kind, height=640)


@pytest.mark.parametrize("symbol", SYMBOLS)
def test_only_professional_flow_axis_limits_automatic_tick_density(symbol, frames):
    spec = json.loads(figure_for(f"{symbol}/daily", frames).to_json())
    for key, axis in spec["layout"].items():
        if not key.startswith(("xaxis", "yaxis")):
            continue
        if key == "yaxis4":
            assert axis.get("nticks") == 3
            assert axis.get("tickmode", "auto") == "auto"
            assert not axis.get("fixedrange", False)
            assert not {"range", "tickvals", "ticktext", "dtick"}.intersection(axis)
        else:
            assert "nticks" not in axis


def test_protection_exempts_only_flow_axis_nticks_and_keeps_other_fields_strict(frames):
    spec = json.loads(figure_for("005380/daily", frames).to_json())
    original = digest(spec)
    changed = json.loads(json.dumps(spec))
    changed["layout"]["yaxis4"]["nticks"] = 5
    assert digest(changed) == original
    for axis_name, field, value in [
        ("yaxis", "nticks", 3), ("yaxis3", "nticks", 3), ("xaxis4", "nticks", 3),
        ("yaxis4", "range", [-1, 1]), ("yaxis4", "tickformat", ","),
        ("yaxis4", "tickfont", {"size": 12}),
    ]:
        changed = json.loads(json.dumps(spec))
        changed["layout"][axis_name][field] = value
        assert digest(changed) != original, (axis_name, field)


@pytest.mark.parametrize("case", sorted(BASELINE_DIGESTS))
def test_preedit_trace_annotation_and_axis_contract_is_unchanged(case, frames):
    before = {name: frame.copy(deep=True) for name, frame in frames.items()}
    figure = figure_for(case, frames)
    assert figure is not None
    assert digest(json.loads(figure.to_json())) == BASELINE_DIGESTS[case]
    for name in frames:
        pd.testing.assert_frame_equal(frames[name], before[name])


@pytest.mark.parametrize("case", [
    "035420/daily", "005380/daily", "005930/daily",
    "generic/flow", "generic/close_only", "comparison/indexed",
])
def test_native_layout_reserves_separate_legend_toolbar_and_axis_space(case, frames):
    spec = json.loads(figure_for(case, frames).to_json())
    layout = spec["layout"]
    assert layout.get("autosize") is True
    assert "width" not in layout
    legend = layout["legend"]
    assert legend["orientation"] == "h"
    # Container-anchored bottom legend reserves its own measured height when it
    # wraps. It no longer shares the upper price-title/native-toolbar region.
    assert legend["yref"] == "container" and legend["y"] == 0
    assert legend["yanchor"] == "bottom"
    assert legend["xanchor"] == "left" and legend["x"] == 0
    assert layout["margin"]["autoexpand"] is True
    assert layout["margin"]["t"] >= 56
    assert layout["hovermode"] == "x unified"
    for key, axis in layout.items():
        if key.startswith(("xaxis", "yaxis")):
            assert axis.get("automargin") is True
    # Retain native legend toggles, axis navigation and range controls.
    assert legend.get("itemclick") is not False
    assert legend.get("itemdoubleclick") is not False
    assert not layout.get("xaxis", {}).get("fixedrange", False)
    assert not layout.get("yaxis", {}).get("fixedrange", False)


def test_actual_emitter_stretches_and_retains_native_modebar_without_bridge(monkeypatch):
    calls = []
    monkeypatch.setattr(charts, "st", SimpleNamespace(
        plotly_chart=lambda chart, **kwargs: calls.append((chart, kwargs)),
    ))
    chart = charts.go.Figure(charts.go.Scatter(x=[1, 2], y=[0, None]))
    charts.render_chart(chart, key_prefix="stable_selected_report")
    assert len(calls) == 1 and calls[0][0] is chart
    options = calls[0][1]
    assert options["key"] == "stable_selected_report_plotly_chart"
    assert options.get("width") == "stretch"
    assert options.get("config", {}).get("responsive") is True
    assert options["config"]["displayModeBar"] is True
    assert not options["config"].get("staticPlot", False)
    assert not options["config"].get("modeBarButtonsToRemove", [])
    assert options.get("on_select", "ignore") == "ignore"


def trace_values(trace):
    values = trace["y"]
    if isinstance(values, dict):
        return np.frombuffer(base64.b64decode(values["bdata"]), dtype=values["dtype"]).tolist()
    return values


@pytest.mark.parametrize("view,query_key,selection_key", [
    ("투자 리포트", "report_query", "report_selected_entry_key"),
    ("관심종목", "watchlist_query", "watchlist_selected_entry_key"),
])
@pytest.mark.parametrize("symbol", SYMBOLS)
def test_real_router_controls_restore_and_keep_all_sql_attempts_read_only(
    monkeypatch, record_testsuite_property, view, query_key, selection_key, symbol,
):
    monkeypatch.setattr(AppSettings, "from_file", lambda *a, **kw: pytest.fail("runtime config read"))
    app = AppTest.from_file(str(ROOT / "tests/g06c_layout_fixture.py"), default_timeout=30).run()
    assert not app.exception
    app.button(key=f"nav_{view}").click().run()
    app.text_input(key=query_key).input(symbol).run()
    assert not app.exception and symbol in app.session_state[selection_key]
    measurements = []

    def observe(label):
        assert not app.exception
        measurement = app.session_state["g06c_measurement"]
        assert measurement["total_selects"] == 3
        assert measurement["snapshot_selects"] == 2
        assert measurement["favorite_selects_after_snapshot"] == 1
        assert measurement["frame_consumer_selects"] == 0
        assert measurement["job_calls"] == 0 and measurement["forbidden_calls"] == []
        assert measurement["runner_calls"] == [] and measurement["write_attempts"] == []
        measurements.append({"checkpoint": label, **measurement})
        proto = app.get("plotly_chart")[0].proto
        assert proto.id.endswith("_plotly_chart")
        config = json.loads(proto.config)
        assert config.get("responsive") is True and config.get("displayModeBar") is True
        return json.loads(proto.spec)

    for timeframe in ("daily", "weekly", "monthly"):
        next(widget for widget in app.radio if widget.label == "봉 기준").set_value(timeframe).run()
        spec = observe(timeframe)
        assert digest(spec) == BASELINE_DIGESTS[f"{symbol}/{timeframe}"]
        flow = [trace for trace in spec["data"] if trace["name"] in {"외국인 순매수", "기관 순매수"}]
        assert len(flow) == {"035420": 0, "005380": 1, "005930": 2}[symbol]
        for trace in flow:
            assert trace["mode"] == "lines+markers" and trace["connectgaps"] is False
        if symbol == "005380":
            assert [value for value in trace_values(flow[0]) if value is not None and not pd.isna(value)] == [0.]

    next(widget for widget in app.radio if widget.label == "조회 기간 방식").set_value("custom").run()
    next(widget for widget in app.date_input if widget.label == "직접 조회 기간").set_value(
        (date(2026, 10, 19), date(2026, 10, 20)),
    ).run()
    observe("custom_range")
    assert any("2026-10-19 ~ 2026-10-20" in item.value for item in app.caption)
    next(widget for widget in app.radio if widget.label == "조회 기간 방식").set_value("preset").run()
    next(widget for widget in app.radio if widget.label == "빠른 조회 기간").set_value("all").run()
    observe("preset_all")
    chosen = app.session_state[selection_key]
    app.button(key="nav_홈").click().run()
    app.button(key=f"nav_{view}").click().run()
    restored = observe("restored")
    assert app.session_state[selection_key] == chosen
    assert next(widget for widget in app.radio if widget.label == "봉 기준").value == "monthly"
    assert digest(restored) == BASELINE_DIGESTS[f"{symbol}/monthly"]

    harness = app.session_state["qa02_harness"]
    attempts = harness.sql_attempts
    assert all(attempt["frame_consumer_selects"] == 0 for attempt in attempts)
    assert all(attempt["total_selects"] == attempt["snapshot_selects"] + attempt["favorite_selects_after_snapshot"] for attempt in attempts)
    assert app.session_state["g06c_measurement"]["selects_all_script_attempts"] == sum(attempt["total_selects"] for attempt in attempts)
    assert len(attempts) == len(harness.classified_attempts)
    record_testsuite_property(f"g08d_sql_{view}_{symbol}", json.dumps({
        "completed_measurements": measurements, "all_script_attempts": attempts,
        "raw_sql_attempts": harness.classified_attempts,
    }, ensure_ascii=False))
