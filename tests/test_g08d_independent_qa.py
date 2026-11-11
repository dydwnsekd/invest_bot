"""Independent G08d checks against real Figures, emitters and SQLite screens."""
from __future__ import annotations

import base64
from datetime import date
import json
import re

import numpy as np
import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

from invest_bot.config.settings import AppSettings
from invest_bot.dashboard import streamlit_charts as charts
from invest_bot.dashboard.streamlit_state import DashboardFrameLoader
from tests.g06c_layout_fixture import G06cHarness


def values(value):
    if isinstance(value, dict):
        value = np.frombuffer(base64.b64decode(value["bdata"]), dtype=value["dtype"])
    return [None if pd.isna(item) else float(item) for item in value]


def traces(spec):
    return {trace["name"]: trace for trace in spec["data"]}


def automatic_layout(spec, *, flow=False):
    layout = spec["layout"]
    assert layout["autosize"] and "width" not in layout
    assert layout["margin"]["autoexpand"] and layout["margin"]["t"] >= 56
    legend = layout["legend"]
    assert (legend["orientation"], legend["yref"], legend["yanchor"], legend["y"]) == ("h", "container", "bottom", 0)
    assert legend.get("itemclick", "toggle") == "toggle"
    assert legend.get("itemdoubleclick", "toggleothers") == "toggleothers"
    assert "maxheight" not in legend and "entrywidth" not in legend
    for key, axis in layout.items():
        if not key.startswith(("xaxis", "yaxis")):
            continue
        assert axis["automargin"] and not axis.get("fixedrange", False)
        if key == "yaxis4" and flow:
            assert axis["nticks"] == 3
            assert not {"range", "dtick", "tickvals", "ticktext", "tickformat", "tickfont"}.intersection(axis)
            assert axis.get("tickmode", "auto") == "auto"
        else:
            assert "nticks" not in axis


@pytest.fixture(scope="module")
def stored_frames(tmp_path_factory):
    harness = G06cHarness(tmp_path_factory.mktemp("qa-g08d-source"))
    # The real seed completes before observation; no runtime settings are read.
    with harness.observe():
        snapshot = harness.service.build_snapshot()
        loader = DashboardFrameLoader(harness.service, snapshot.latest_records)
        loaded = {symbol: loader.load_professional(symbol) for symbol in ("035420", "005380", "005930")}
        assert len(harness.selects) == 2
        assert all(phase == "snapshot" for phase, _sql in harness.selects)
    assert not harness.write_attempts
    return loaded


@pytest.mark.parametrize("symbol,length,source,foreign,institution", [
    ("035420", 5, "summary", None, None),
    ("005380", 5, "detail", [None, None, None, None, 0.0], None),
    ("005930", 4, "summary", [None, -11.0, None, 0.0], [None, 5.0, None, None]),
])
def test_sqlite_sources_keep_literal_price_flow_and_axis_contracts(stored_frames, symbol, length, source, foreign, institution):
    frame = stored_frames[symbol]
    original = frame.copy(deep=True)
    figure = charts.build_professional_plotly_chart(frame, height=640)
    spec = json.loads(figure.to_json())
    data = traces(spec)
    expected_names = ["캔들", "5일선", "20일선", "60일선", "거래량", "RSI 14"]
    if foreign is not None:
        expected_names.append("외국인 순매수")
    if institution is not None:
        expected_names.append("기관 순매수")
    assert list(data) == expected_names
    assert frame.attrs["investor_flow_source"] == source
    candle = data["캔들"]
    for field, start in (("open", 98), ("high", 102), ("low", 97), ("close", 100)):
        assert values(candle[field]) == list(range(start, start + length))
    assert [str(item)[:10] for item in candle["x"]] == ["2026-10-16", "2026-10-19", "2026-10-20", "2026-10-21", "2026-10-22"][:length]
    assert candle["increasing"]["line"]["color"] == "#dc2626"
    assert candle["decreasing"]["line"]["color"] == "#2563eb"
    assert all(token in candle["hovertemplate"] for token in ("시가", "고가", "저가", "종가", "%Y-%m-%d"))
    assert values(data["거래량"]["y"]) == [1000 + 100 * i for i in range(length)]
    for name, color, expected in (("외국인 순매수", "#2563eb", foreign), ("기관 순매수", "#059669", institution)):
        if expected is None:
            assert name not in data
        else:
            trace = data[name]
            assert values(trace["y"]) == expected
            assert trace["mode"] == "lines+markers" and trace["connectgaps"] is False
            assert trace["line"]["color"] == color and ":,.0f" in trace["hovertemplate"]
    assert spec["layout"]["yaxis3"]["range"] == [0, 100]
    assert spec["layout"]["yaxis"]["tickformat"] == ","
    assert [shape["y0"] for shape in spec["layout"]["shapes"]] == ([30, 70, 0] if foreign is not None else [30, 70])
    automatic_layout(spec, flow=foreign is not None)
    pd.testing.assert_frame_equal(frame, original)


@pytest.mark.parametrize("timeframe,dates,ohlc,flow", [
    ("weekly", ["2026-01-30", "2026-02-05", "2026-02-10"],
     [[10, 14, 8, 12, 300], [12, 18, 10, 16, 700], [16, 20, 14, 18, 500]], [None, 0, -4]),
    ("monthly", ["2026-01-30", "2026-02-10"],
     [[10, 14, 8, 12, 300], [12, 20, 10, 18, 1200]], [None, -4]),
])
def test_manual_calendar_expectations_preserve_unobserved_period_and_real_zero(timeframe, dates, ohlc, flow):
    frame = pd.DataFrame({
        "date": pd.to_datetime(["2026-01-29", "2026-01-30", "2026-02-02", "2026-02-05", "2026-02-10"]),
        "open": [10, 11, 12, 14, 16], "high": [13, 14, 16, 18, 20], "low": [8, 9, 10, 12, 14],
        "close": [11, 12, 14, 16, 18], "volume": [100, 200, 300, 400, 500],
        "foreign_net": [None, None, 0, None, -4],
    })
    original = frame.copy(deep=True)
    aggregate = charts.aggregate_professional_chart_frame(frame, timeframe)
    assert aggregate.date.dt.strftime("%Y-%m-%d").tolist() == dates
    assert aggregate[["open", "high", "low", "close", "volume"]].values.tolist() == ohlc
    assert values(aggregate.foreign_net) == flow
    spec = json.loads(charts.build_professional_plotly_chart(aggregate, timeframe=timeframe).to_json())
    assert values(traces(spec)["외국인 순매수"]["y"]) == flow
    assert traces(spec)["외국인 순매수"]["connectgaps"] is False
    assert spec["layout"]["annotations"][0]["text"] == ("가격 (주봉)" if timeframe == "weekly" else "가격 (월봉)")
    automatic_layout(spec, flow=True)
    pd.testing.assert_frame_equal(frame, original)


@pytest.mark.parametrize("basis,expected", [("price", [[20, 30, 40], [80, 40, 0]]), ("indexed", [[100, 150, 200], [100, 50, 0]])])
def test_comparison_shared_dates_values_zero_and_native_layout(basis, expected):
    frames = {
        "A": pd.DataFrame({"date": ["2026-10-16", "2026-10-19", "2026-10-20", "2026-10-21"], "close": [10, 20, 30, 40]}),
        "B": pd.DataFrame({"date": ["2026-10-19", "2026-10-20", "2026-10-21", "2026-10-22"], "close": [80, 40, 0, 5]}),
    }
    comparison = charts.build_stock_comparison_frame(frames)
    assert not comparison.unavailable_labels
    frame = comparison.frame
    if basis == "indexed":
        frame = charts.normalize_stock_comparison_frame(frame)
    spec = json.loads(charts.build_stock_comparison_chart(frame, basis=basis, library="plotly").to_json())
    assert [trace["name"] for trace in spec["data"]] == ["A", "B"]
    assert [values(trace["y"]) for trace in spec["data"]] == expected
    assert all([str(day)[:10] for day in trace["x"]] == ["2026-10-19", "2026-10-20", "2026-10-21"] for trace in spec["data"])
    assert spec["layout"]["yaxis"]["title"]["text"] == ("기준값 100" if basis == "indexed" else "종가 (원)")
    automatic_layout(spec)


def emitter_script():
    import streamlit as st
    import plotly.graph_objects as go
    from unittest.mock import patch
    from invest_bot.dashboard import streamlit_charts as module
    figure = go.Figure(go.Scatter(x=[1, 2, 3], y=[0, None, -2], mode="lines+markers", connectgaps=False))
    real = st.plotly_chart
    def observe(chart, **kwargs):
        st.session_state["qa_emission"] = {"same_figure": chart is figure, **kwargs}
        return real(chart, **kwargs)
    with patch.object(st, "plotly_chart", observe):
        module.render_chart(figure, key_prefix="qa_native")


def test_actual_streamlit_emitter_keeps_native_config_and_key():
    app = AppTest.from_function(emitter_script).run()
    assert not app.exception
    options = app.session_state["qa_emission"]
    assert options == {"same_figure": True, "width": "stretch", "key": "qa_native_plotly_chart", "config": {"responsive": True, "displayModeBar": True}}
    proto = app.get("plotly_chart")[0].proto
    config = json.loads(proto.config)
    assert config["responsive"] and config["displayModeBar"]
    assert not config.get("staticPlot", False) and not config.get("modeBarButtonsToRemove")
    assert proto.id.endswith("qa_native_plotly_chart")
    trace = json.loads(proto.spec)["data"][0]
    assert trace["y"] == [0, None, -2] and trace["connectgaps"] is False


def main_script(folder):
    from pathlib import Path
    import streamlit as st
    from tests.g06c_layout_fixture import G06cHarness
    if "qa02_harness" not in st.session_state:
        st.session_state["qa02_harness"] = G06cHarness(Path(folder))
    st.session_state["qa02_harness"].render()


@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.setattr(AppSettings, "from_file", lambda *a, **k: pytest.fail("runtime settings access"))
    app = AppTest.from_function(main_script, kwargs={"folder": str(tmp_path / "synthetic")}, default_timeout=30).run()
    assert not app.exception
    return app


def navigate(app, tab):
    app.button(key="nav_" + tab).click().run()
    assert not app.exception


def output(app):
    assert not app.exception
    proto = app.get("plotly_chart")[0].proto
    config = json.loads(proto.config)
    assert config["responsive"] and config["displayModeBar"]
    return json.loads(proto.spec), proto.id.split("-", 2)[-1]


def checkpoint(app, records, label, *, favorite):
    assert not app.exception
    measurement = dict(app.session_state["g06c_measurement"])
    assert (measurement["snapshot_selects"], measurement["favorite_selects_after_snapshot"], measurement["frame_consumer_selects"]) == (2, favorite, 0)
    assert measurement["total_selects"] == 2 + favorite
    assert measurement["job_calls"] == 0 and measurement["forbidden_calls"] == []
    assert measurement["runner_calls"] == [] and measurement["write_attempts"] == [] and measurement["seed_count"] == 1
    attempts = [dict(item) for item in app.session_state["qa02_harness"].sql_attempts]
    assert attempts[-1]["completed_render"]
    assert all(item["frame_consumer_selects"] == 0 for item in attempts)
    assert sum(item["total_selects"] for item in attempts) == measurement["selects_all_script_attempts"]
    records.append({"label": label, "completed_render": measurement, "all_attempts": attempts})


@pytest.mark.parametrize("tab,symbol", [("투자 리포트", "005380"), ("관심종목", "005930"), ("데이터 보기", "035420")])
def test_real_main_period_selection_keys_and_read_boundaries(app, tmp_path, tab, symbol):
    records = []
    navigate(app, tab)
    if tab == "데이터 보기":
        app.selectbox(key="data_symbol_filter").select(symbol).run()
        app.multiselect(key="data_comparison_symbols").set_value(["035420", "005930"]).run()
        app.radio(key="data_comparison_basis").set_value("price").run()
        spec, key = output(app)
        assert [values(trace["y"]) for trace in spec["data"]] == [[100, 101, 102, 103, 104]] * 2
        favorite = 0
        chosen = list(app.multiselect(key="data_comparison_symbols").value)
        checkpoint(app, records, "comparison-price", favorite=0)
    else:
        prefix = "report" if tab == "투자 리포트" else "watchlist"
        app.text_input(key=prefix + "_query").input(symbol).run()
        chosen = app.session_state[prefix + "_selected_entry_key"]
        assert symbol in chosen
        spec, key = output(app)
        assert len(spec["data"]) == (7 if symbol == "005380" else 8)
        assert any("상세" in item.value if symbol == "005380" else "요약" in item.value for item in app.caption)
        favorite = 1
        next(item for item in app.radio if item.label == "봉 기준").set_value("weekly").run()
        checkpoint(app, records, "weekly", favorite=1)
    next(item for item in app.radio if item.label == "조회 기간 방식").set_value("custom").run()
    next(item for item in app.date_input if item.label == "직접 조회 기간").set_value((date(2026, 10, 19), date(2026, 10, 21))).run()
    spec, current_key = output(app)
    assert current_key == key
    if tab == "데이터 보기":
        assert [values(trace["y"]) for trace in spec["data"]] == [[101, 102, 103]] * 2
        app.radio(key="data_comparison_basis").set_value("indexed").run()
    else:
        assert values(spec["data"][0]["close"]) == [103]
        assert len(spec["data"]) == (6 if symbol == "005380" else 8)
        next(item for item in app.radio if item.label == "봉 기준").set_value("monthly").run()
    checkpoint(app, records, "custom-period", favorite=favorite)
    before, before_key = output(app)
    navigate(app, "홈")
    navigate(app, tab)
    restored, restored_key = output(app)
    assert restored_key == before_key == key and restored["data"] == before["data"]
    assert next(item for item in app.radio if item.label == "조회 기간 방식").value == "custom"
    assert any("2026-10-19 ~ 2026-10-21" in item.value for item in app.caption)
    if tab == "데이터 보기":
        assert app.multiselect(key="data_comparison_symbols").value == chosen
        assert app.radio(key="data_comparison_basis").value == "indexed"
    else:
        assert app.session_state[prefix + "_selected_entry_key"] == chosen
        assert next(item for item in app.radio if item.label == "봉 기준").value == "monthly"
    checkpoint(app, records, "restored", favorite=favorite)
    next(item for item in app.radio if item.label == "조회 기간 방식").set_value("preset").run()
    next(item for item in app.radio if item.label == "빠른 조회 기간").set_value("all").run()
    checkpoint(app, records, "all-period", favorite=favorite)
    assert records[-1]["completed_render"]["selects_all_script_attempts"] > records[0]["completed_render"]["selects_all_script_attempts"]
    (tmp_path / "qa-g08d-measurements.json").write_text(json.dumps(records, ensure_ascii=False, indent=2))


def test_actual_style_rule_sizes_only_native_auxiliary_svg_text(app):
    emitted = [item.value for item in app.markdown if "<style>" in item.value]
    assert len(emitted) == 1
    css = re.sub(r"/\*.*?\*/", "", emitted[0], flags=re.S)
    rules = [(selectors.strip(), body.strip()) for selectors, body in re.findall(r"([^{}]+)\{([^{}]*)\}", css)]
    scoped = [(selectors, body) for selectors, body in rules if "stPlotlyChart" in selectors]
    assert len(scoped) == 1
    selectors, body = scoped[0]
    assert set(map(str.strip, selectors.split(","))) == {'[data-testid="stPlotlyChart"] text.legendtext', '[data-testid="stPlotlyChart"] g[class$="tick"] > text'}
    assert body == "font-size: 0.8rem !important;"
    assert not any(token in selectors for token in ("annotation", "xtitle", "ytitle", "modebar", "span"))
    assert "Material Symbols Rounded" in css and "button:focus-visible" in css
