"""HTML data boundaries: keep window/model identities and unrounded metrics."""
import importlib.util
import json
from copy import deepcopy
from html.parser import HTMLParser
from pathlib import Path

import pytest


SPEC = importlib.util.spec_from_file_location(
    "rolling_report_renderer", Path(__file__).resolve().parents[1] / "scripts/render_rolling_backtest_report.py"
)
renderer = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(renderer)


class PayloadParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.scripts = []
        self.payload = []
        self.in_payload = False

    def handle_starttag(self, tag, attrs):
        if tag == "script":
            attrs = dict(attrs)
            self.scripts.append(attrs)
            self.in_payload = attrs.get("id") == "stock-explorer-data"

    def handle_endtag(self, tag):
        if tag == "script":
            self.in_payload = False

    def handle_data(self, data):
        if self.in_payload:
            self.payload.append(data)


@pytest.fixture
def research():
    windows = [
        {"id": "old", "kind": "rolling", "length": 20, "start_date": "2026-08-01", "end_date": "2026-08-30", "regime": "상승"},
        {"id": "new", "kind": "rolling", "length": 20, "start_date": "2026-09-01", "end_date": "2026-09-30", "regime": "하락"},
    ]
    models = [{"id": "momentum", "name": "모멘텀", "type": "single"}, {"id": "mixed", "name": "혼합", "type": "signal_mix"}]
    records = []
    for window in windows:
        for model in models:
            for symbol, name in [("005930", "삼성전자"), ("000660", "SK하이닉스")]:
                records.append({
                    "window_id": window["id"], "model_id": model["id"], "symbol": symbol, "symbol_name": name,
                    "net_return_pct": -10.123456789 if window["id"] == "new" else 1000.123456789,
                    "net_mdd_pct": 20.987654321, "bh_net_return_pct": -5.123456789,
                    "etf_net_return_pct": 7.123456789, "trade_count": 3 if model["id"] == "mixed" else 0,
                    "exposure_pct": 10.123456789, "win_rate_net_pct": 100 / 3 if model["id"] == "mixed" else None,
                })
    return {"windows": windows, "models": models, "stock_results": list(reversed(records))}


def test_explorer_retains_identity_and_precision_for_every_result(research):
    original = deepcopy(research)
    payload = renderer.stock_explorer_payload(research)
    records = {(r["window_id"], r["model_id"], r["symbol"]): r for r in research["stock_results"]}
    assert len(payload["results"]) == len(records)
    for row in payload["results"]:
        key = (payload["windows"][row[0]]["id"], payload["models"][row[1]]["id"], payload["symbols"][row[2]]["symbol"])
        record = records.pop(key)
        assert row[3:] == [record[field] for field in (
            "net_return_pct", "net_mdd_pct", "bh_net_return_pct", "etf_net_return_pct", "trade_count", "exposure_pct", "win_rate_net_pct"
        )]
    assert not records
    assert research == original
    assert {s["symbol"] for s in payload["symbols"]} == {"005930", "000660"}


def test_script_payload_handles_html_termination_without_changing_names(research):
    unsafe_name = '</script><script src="https://invalid.example/attack"></script>&\u2028\u2029'
    for record in research["stock_results"]:
        if record["symbol"] == "000660":
            record["symbol_name"] = unsafe_name
    research["models"][0]["name"] = unsafe_name
    parser = PayloadParser()
    parser.feed(renderer.stock_explorer_section(research))
    assert parser.scripts == [{"id": "stock-explorer-data", "type": "application/json"}]
    parsed = json.loads("".join(parser.payload))
    assert parsed["models"][0]["name"] == unsafe_name
    assert unsafe_name in {stock["name"] for stock in parsed["symbols"]}


def test_no_trade_win_rate_is_missing_and_invalid_metrics_fail_explicitly(research):
    record = research["stock_results"][0]
    record["trade_count"] = 0
    record["win_rate_net_pct"] = 0
    payload = renderer.stock_explorer_payload(research)
    assert payload["results"][0][-1] is None
    record["net_return_pct"] = float("nan")
    with pytest.raises(ValueError, match="JSON compliant"):
        renderer.stock_explorer_section(research)
