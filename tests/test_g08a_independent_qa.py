"""Independent G08a regressions through the real facade, job and persistence."""
from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import pytest

from invest_bot.config.settings import AppSettings
from invest_bot.db.frame_storage import DbFrameStorage
from invest_bot.jobs import collect_market_data as job
from invest_bot.market import collector as facade_module
from invest_bot.market.collector import MarketDataCollector
from invest_bot.market.price_history import DailyPriceHistoryFetcher
from invest_bot.market.storage import CsvStorage
from tests.helpers import init_test_db

SYMBOL = "005930"
SECRET = "QA_SYNTHETIC_ONLY_DO_NOT_EXPOSE_9731"


def row(day):
    return {"stck_bsop_date": day.strftime("%Y%m%d"), "stck_oprc": "100",
            "stck_hgpr": "110", "stck_lwpr": "90", "stck_clpr": "105", "acml_vol": "10"}


class Clock:
    def __init__(self):
        self.now, self.waits = 0.0, []

    def sleep(self, seconds):
        self.waits.append(seconds)
        self.now += seconds


class SyntheticAPI:
    """No transport, credentials or real KIS client is constructed."""
    def __init__(self, dates, *, listing="", fail_page=None):
        self.dates, self.listing, self.fail_page = dates, listing, fail_page
        self.calls, self.price_calls = [], []

    def get_json(self, api_path, tr_id, params, **kwargs):
        self.calls.append((api_path, tr_id, dict(params)))
        if api_path.endswith("inquire-daily-itemchartprice"):
            self.price_calls.append(dict(params))
            if len(self.price_calls) == self.fail_page:
                raise ConnectionError(SECRET)
            start = date.fromisoformat(pd.Timestamp(params["FID_INPUT_DATE_1"]).date().isoformat())
            end = pd.Timestamp(params["FID_INPUT_DATE_2"]).date()
            days = [d for d in self.dates if start <= d <= end]
            return {"rt_cd": "0", "output1": {"pdno": SYMBOL}, "output2": [row(d) for d in reversed(days)]}
        if api_path.endswith("search-stock-info"):
            return {"rt_cd": "0", "output": {"pdno": SYMBOL, "prdt_abrv_name": "QA synthetic",
                    "scts_mket_lstg_dt": self.listing, "kosdaq_mket_lstg_dt": "00000000"}}
        assert api_path.endswith("investor-trade-by-stock-daily")
        return {"rt_cd": "0", "output1": [{"investor": "synthetic", "net_volume": "1"}],
                "output2": [{"stck_bsop_date": params["FID_INPUT_DATE_1"], "frgn_ntby_qty": "1",
                             "orgn_ntby_qty": "2", "prsn_ntby_qty": "-3"}]}


@pytest.fixture
def harness(monkeypatch, tmp_path):
    def make(kind, dates, *, listing="", calendar=None, fail_page=None):
        if kind == "csv":
            storage = CsvStorage(tmp_path / "csv")
        else:
            url = f"sqlite+pysqlite:///{tmp_path / 'synthetic.db'}"
            init_test_db(url)
            storage = DbFrameStorage(url)
        api, clock = SyntheticAPI(dates, listing=listing, fail_page=fail_page), Clock()
        monkeypatch.setattr(facade_module, "KISClient", lambda settings: api)
        settings = AppSettings(enable_db_write=False)
        collector = MarketDataCollector(settings, storage=storage)
        collector.collector.price_history = DailyPriceHistoryFetcher(
            api, clock=lambda: clock.now, sleep=clock.sleep, calendar=calendar)
        return collector, storage, api, clock
    return make


@pytest.mark.parametrize("kind", ["csv", "sqlite"])
def test_completed_disjoint_windows_roundtrip_real_storage(harness, kind):
    start, end = date(2026, 1, 4), date(2026, 11, 1)
    dates = [d.date() for d in pd.bdate_range(start, end)]
    collector, storage, api, clock = harness(kind, dates)
    result = collector.collect_symbol_bundle(SYMBOL, start, end)
    assert result.status == "success" and result.analysis_ready is True
    coverage = result.price_coverage
    assert coverage["request_complete"] is True and coverage["trading_days_verified"] is False
    assert coverage["requested_start"] == start.isoformat() and coverage["requested_end"] == end.isoformat()
    assert coverage["observed_start"] == dates[0].isoformat() and coverage["observed_end"] == dates[-1].isoformat()
    assert coverage["rows"] == len(dates) and coverage["requests"] == 4
    windows = [(pd.Timestamp(p["FID_INPUT_DATE_1"]).date(), pd.Timestamp(p["FID_INPUT_DATE_2"]).date())
               for p in api.price_calls]
    union = []
    for lower, upper in windows:
        assert 1 <= (upper - lower).days + 1 <= 100
        union += [lower + timedelta(days=n) for n in range((upper - lower).days + 1)]
    assert len(union) == len(set(union)) == (end - start).days + 1
    assert min(union) == start and max(union) == end
    assert len(clock.waits) == 3 and all(abs(seconds - 1.1) < 1e-8 for seconds in clock.waits)
    latest = storage.latest_filename("daily_prices", SYMBOL)
    loaded = storage.load("daily_prices", latest)
    assert loaded.stck_bsop_date.astype(str).tolist() == [d.strftime("%Y%m%d") for d in dates]
    assert len(result.saved_files) == 5


@pytest.mark.parametrize("kind", ["csv", "sqlite"])
def test_page_failure_prevents_storage_and_later_endpoints(harness, kind):
    start, end = date(2026, 1, 1), date(2026, 5, 1)
    dates = [d.date() for d in pd.date_range(start, end)]
    collector, storage, api, _ = harness(kind, dates, fail_page=2)
    result = collector.collect_symbol_bundle(SYMBOL, start, end)
    assert result.status == "failed" and result.analysis_ready is False
    assert result.saved_files == [] and storage.latest_filename("daily_prices", SYMBOL) is None
    assert len(api.calls) == len(api.price_calls) == 2
    assert result.price_coverage["requests"] == 2 and result.price_coverage["rows"] == 100
    assert result.price_coverage["request_complete"] is False and SECRET not in result.error


@pytest.mark.parametrize("kind", ["csv", "sqlite"])
def test_listing_cannot_turn_invalid_calendar_evidence_into_saved_ready_success(harness, monkeypatch, kind):
    start, end = date(2026, 1, 1), date(2026, 4, 10)
    dates = [d.date() for d in pd.date_range(start + timedelta(days=1), end)]
    # The calendar's out-of-range session is explicitly rejected by the history
    # coverage assessor. A valid listing date must not erase that unknown result.
    collector, storage, _, _ = harness(kind, dates, listing="20260102",
        calendar=lambda lower, upper: [upper + timedelta(days=1)])
    _, prices = collector.collect_daily_prices(SYMBOL, start, end)
    assert prices.attrs["price_coverage"]["status"] == "unknown"
    assert prices.attrs["price_coverage"]["reason"] == "invalid_calendar_evidence"

    class FrozenDate(date):
        @classmethod
        def today(cls):
            return end

    monkeypatch.setattr(job, "date", FrozenDate)
    result = job.collect_market_data_for_symbols([SYMBOL], days=(end-start).days,
                                                 settings=collector.settings, collector=collector)
    actual = result["results"][0]
    persisted = storage.latest_filename("daily_prices", SYMBOL)
    assert result["success_count"] == 0, (
        f"Invalid calendar was overridden: status={actual['status']}, "
        f"coverage={actual['price_coverage']}, ready={result['analysis_ready_symbols']}, "
        f"saved_count={len(actual['saved_files'])}, persisted={persisted}")
    assert actual["price_coverage"]["status"] == "unknown"
    assert actual["price_coverage"]["reason"] == "invalid_calendar_evidence"
    assert result["analysis_ready_symbols"] == [] and actual["saved_files"] == []
    assert persisted is None



# Appended after the six preserved original regressions.
import copy
import json
from datetime import datetime
from types import SimpleNamespace
from urllib.error import URLError

from invest_bot.dashboard import streamlit_actions as actions
from invest_bot.dashboard import streamlit_backtest as backtest
from invest_bot.dashboard import streamlit_watchlist as watchlist
from invest_bot.dashboard.service import DashboardDataService
from invest_bot.jobs.scheduled_collection import CollectionScheduleConfig, ScheduledCollectionRunner, load_schedule_status
from invest_bot.market.collector import BatchCollectionResult
from invest_bot.market.symbol_lookup import ResolvedSymbol


def freeze_job(monkeypatch, end):
    class FixedDate(date):
        @classmethod
        def today(cls):
            return end
    monkeypatch.setattr(job, "date", FixedDate)


def prices(days):
    return pd.DataFrame([row(d) for d in days])


def all_datasets_absent(storage, symbol=SYMBOL):
    assert all(storage.latest_filename(dataset, symbol) is None for dataset in (
        "daily_prices_summary", "daily_prices", "stock_info", "investor_daily", "investor_daily_summary"))


def test_repaired_calendar_guard_retains_whole_metadata_and_no_persistence(harness, monkeypatch):
    end = date(2026, 4, 10)
    days = [d.date() for d in pd.date_range("2026-01-02", end)]
    collector, storage, api, _ = harness("sqlite", days, listing="20260102",
        calendar=lambda lower, upper: [upper + timedelta(days=1)])
    captured = {}
    real = collector.collect_daily_prices

    def collect(*args):
        summary, frame = real(*args)
        captured.update(frame.attrs["price_coverage"])
        return summary, frame

    monkeypatch.setattr(collector, "collect_daily_prices", collect)
    freeze_job(monkeypatch, end)
    payload = job.collect_market_data_for_symbols([SYMBOL], days=99, settings=collector.settings, collector=collector)
    assert payload["results"][0]["price_coverage"] == captured
    assert payload["success_count"] == 0 and payload["analysis_ready_symbols"] == []
    assert payload["results"][0]["saved_files"] == []
    assert sum(path.endswith("search-stock-info") for path, _, _ in api.calls) == 1
    assert not any(path.endswith("investor-trade-by-stock-daily") for path, _, _ in api.calls)
    all_datasets_absent(storage)


@pytest.mark.parametrize("kind", ["csv", "sqlite"])
def test_valid_short_and_empty_windows_save_without_calendar_inference(harness, kind):
    start, end = date(2025, 11, 2), date(2026, 11, 1)
    days = [date(2026, 3, 2), date(2026, 3, 3)]
    collector, storage, api, _ = harness(kind, days)
    result = collector.collect_symbol_bundle(SYMBOL, start, end)
    assert result.status == "success" and result.analysis_ready is False
    assert result.price_coverage["status"] == "complete" and result.price_coverage["requests"] == 4
    assert result.price_coverage["rows"] == 2 and result.price_coverage["trading_days_verified"] is False
    assert result.price_coverage["range_reason"].startswith("unverified")
    assert len(result.saved_files) == 5
    loaded = storage.load("daily_prices", storage.latest_filename("daily_prices", SYMBOL))
    assert loaded.stck_bsop_date.astype(str).tolist() == ["20260302", "20260303"]


@pytest.mark.parametrize("listing,calendar,status,reason", [
    ("20260102", lambda a, b: [date(2026, 1, 1), date(2026, 1, 2)], "incomplete", "calendar_observation_mismatch"),
    ("bad", lambda a, b: [date(2026, 1, 2)], "complete", "calendar_observations_match"),
    ("20990101", None, "complete", "bounded_windows_exhausted"),
])
def test_calendar_and_listing_remain_separate_axes(harness, listing, calendar, status, reason):
    collector, storage, _, _ = harness("sqlite", [date(2026, 1, 2)], listing=listing, calendar=calendar)
    result = collector.collect_symbol_bundle(SYMBOL, date(2026, 1, 1), date(2026, 1, 2))
    assert result.price_coverage["status"] == status and result.price_coverage["reason"] == reason
    if status != "complete":
        assert result.status == "failed" and result.saved_files == []
        all_datasets_absent(storage)
    else:
        assert result.status == "success" and result.analysis_ready is False
        assert result.price_coverage["trading_days_verified"] is (calendar is not None)


@pytest.mark.parametrize("kind", ["csv", "sqlite"])
def test_later_symbol_page_failure_preserves_earlier_real_saves(harness, kind):
    days = [date(2026, 1, 1), date(2026, 1, 2)]
    collector, storage, api, _ = harness(kind, days)
    original = api.get_json

    def query(api_path, tr_id, params, **kwargs):
        if api_path.endswith("inquire-daily-itemchartprice") and params["FID_INPUT_ISCD"] == "000660":
            api.calls.append((api_path, tr_id, dict(params)))
            raise ConnectionError(SECRET)
        return original(api_path, tr_id, params, **kwargs)

    api.get_json = query
    result = collector.collect_symbols_batch([SYMBOL, "000660"], days[0], days[-1])
    assert [r.status for r in result] == ["success", "failed"]
    assert len(result[0].saved_files) == 5 and result[1].saved_files == []
    assert len(storage.load("daily_prices", storage.latest_filename("daily_prices", SYMBOL))) == 2
    all_datasets_absent(storage, "000660")
    assert len(api.calls) == 4 and SECRET not in result[1].error


@pytest.mark.parametrize("kind", ["csv", "sqlite"])
def test_storage_failure_reports_already_saved_summary(harness, monkeypatch, kind):
    collector, storage, _, _ = harness(kind, [date(2026, 1, 1)])
    original = storage.save

    def save(dataset, filename, frame):
        if dataset == "daily_prices":
            raise OSError("synthetic storage failure")
        return original(dataset, filename, frame)

    monkeypatch.setattr(storage, "save", save)
    result = collector.collect_symbol_bundle(SYMBOL, date(2026, 1, 1), date(2026, 1, 1))
    assert result.status == "failed" and result.analysis_ready is False
    assert result.price_coverage["status"] == "complete" and len(result.saved_files) == 1
    assert "daily_prices_summary" in result.saved_files[0]
    assert storage.latest_filename("daily_prices_summary", SYMBOL)
    assert storage.latest_filename("daily_prices", SYMBOL) is None


@pytest.mark.parametrize("ready", [True, None, False, "true", "false", 0, 1, [], {}])
def test_root_readiness_identity_and_coverage_classifications(ready):
    record = BatchCollectionResult(SYMBOL, "success", 1, 61, 0, 0, 0, [],
                                   price_coverage={"status": "complete"}, analysis_ready=ready)
    fake = SimpleNamespace(collect_symbols_batch=lambda **kwargs: [record])
    payload = job.collect_market_data_for_symbols([SYMBOL], settings=AppSettings(), collector=fake)
    expected = ready is True or ready is None
    assert payload["analysis_ready_symbols"] == ([SYMBOL] if expected else [])
    assert payload["analysis_unready_symbols"] == ([] if expected else [SYMBOL])
    assert payload["analysis_ready_count"] == int(expected)
    assert payload["analysis_unready_count"] == int(not expected)
    assert payload["coverage_complete_symbols"] == [SYMBOL]


class UIState(dict):
    __getattr__ = dict.get
    def __setattr__(self, key, value):
        self[key] = value


@pytest.fixture
def connected_ui(harness, monkeypatch):
    end = date(2026, 11, 2)
    long = [d.date() for d in pd.date_range(end=end, periods=61)]
    short = long[-2:]
    collector, storage, api, _ = harness("sqlite", long)
    freeze_job(monkeypatch, end)
    events, returned = [], []
    state = UIState()
    ui = SimpleNamespace(session_state=state, rerun=lambda: events.append(("rerun",)))
    monkeypatch.setattr(actions, "st", ui)
    monkeypatch.setattr(backtest, "st", ui)
    for module in (actions, backtest):
        monkeypatch.setattr(module, "generate_indicators_for_symbol", lambda symbol: events.append(("indicator", symbol)))
        monkeypatch.setattr(module, "generate_golden_cross_signals_for_symbol", lambda symbol: events.append(("signal", symbol)))
    def report(symbol, *, delivery_target, settings):
        events.append(("report", symbol, delivery_target))
        return {"symbol": symbol, "delivery": {"status": "sent"}}
    monkeypatch.setattr(actions, "generate_market_report_for_symbol", report)
    original = api.get_json
    mode = {"case": "mixed"}

    def query(api_path, tr_id, params, **kwargs):
        if api_path.endswith("inquire-daily-itemchartprice"):
            symbol = params["FID_INPUT_ISCD"]
            api.dates = short if mode["case"] == "short" or (mode["case"] == "mixed" and symbol == "000660") else long
        result = original(api_path, tr_id, params, **kwargs)
        if api_path.endswith("search-stock-info"):
            result["output"]["pdno"] = params["PDNO"]
        if api_path.endswith("inquire-daily-itemchartprice"):
            result["output1"]["pdno"] = params["FID_INPUT_ISCD"]
        return result

    api.get_json = query

    def collect(symbols, days):
        result = job.collect_market_data_for_symbols(symbols, days, settings=collector.settings, collector=collector)
        malformed = {"empty": [], "none": None, "string": SYMBOL, "mixed_type": [SYMBOL, 1],
                     "foreign": ["999999"]}
        if mode["case"] in malformed:
            result["analysis_ready_symbols"] = malformed[mode["case"]]
        elif mode["case"] == "legacy":
            result.pop("analysis_ready_symbols")
        returned.append(result)
        return result
    monkeypatch.setattr(actions, "collect_market_data_for_symbols", collect)
    monkeypatch.setattr(backtest, "collect_market_data_for_symbols", collect)
    items = [ResolvedSymbol(raw_input=s, symbol=s, symbol_name=s) for s in (SYMBOL, "000660")]
    return SimpleNamespace(state=state, events=events, mode=mode, returned=returned,
                           items=items, storage=storage, settings=collector.settings)


@pytest.mark.parametrize("entry", ["full", "prepare"])
@pytest.mark.parametrize("mode", ["short", "mixed", "ready", "legacy", "empty", "none", "string", "mixed_type", "foreign"])
def test_actual_root_storage_to_ui_pipeline_gates(connected_ui, entry, mode):
    ctx = connected_ui
    ctx.mode["case"] = mode
    if entry == "full":
        actions.run_full_pipeline_action(ctx.items, 100, settings=ctx.settings)
    else:
        backtest._run_prepare_action(ctx.items, 100)
    eligible = [SYMBOL] if mode == "mixed" else [SYMBOL, "000660"] if mode in {"ready", "legacy"} else []
    assert [e[1] for e in ctx.events if e[0] == "indicator"] == eligible
    assert [e[1] for e in ctx.events if e[0] == "signal"] == eligible
    assert [e[1] for e in ctx.events if e[0] == "report"] == (eligible if entry == "full" else [])
    assert all(e[2] == "discord" for e in ctx.events if e[0] == "report")
    assert ctx.returned[0]["success_count"] == 2
    assert all(ctx.storage.latest_filename("daily_prices", s) for s in (SYMBOL, "000660"))
    assert "수집 성공 0" not in ctx.state.action_message
    for text in ("2026-07-25", "2026-11-02", "행", "회", "거래일 검증", "[005930]", "[000660]"):
        assert text in ctx.state.action_message
    if not eligible:
        assert ctx.state.action_message_type == "warning" and "분석" in ctx.state.action_message
    assert SECRET not in ctx.state.action_message



def watch_service(collector, storage, kind, tmp_path):
    if kind == "csv":
        return DashboardDataService(raw_root=storage.root_dir, processed_root=tmp_path / "processed",
                                    settings=collector.settings)
    return DashboardDataService(dataset_storage=storage, settings=collector.settings)


def refresh(service, callbacks, *, today=date(2026, 11, 2), **kwargs):
    return watchlist.refresh_favorite_symbols_if_needed(service, {SYMBOL}, today=today,
        analyze_callback=lambda s: callbacks.append(("indicator", s)),
        signal_callback=lambda s: callbacks.append(("signal", s)),
        report_callback=lambda s: callbacks.append(("report", s)), **kwargs)


@pytest.mark.parametrize("kind", ["csv", "sqlite"])
def test_actual_watchlist_one_day_increment_from_persisted_sixty_rows(harness, monkeypatch, tmp_path, kind):
    target = date(2026, 11, 2)
    existing = [d.date() for d in pd.date_range(end=target-timedelta(days=1), periods=60)]
    collector, storage, api, _ = harness(kind, [target])
    collector.save_daily_prices(SYMBOL, existing[0], existing[-1],
                               pd.DataFrame({"pdno": [SYMBOL]}), prices(existing))
    storage.save("investor_daily_summary", f"{SYMBOL}_old.csv",
                 pd.DataFrame({"stck_bsop_date": [existing[-1].strftime("%Y%m%d")]}))
    service = watch_service(collector, storage, kind, tmp_path)
    monkeypatch.setattr(watchlist, "MarketDataCollector", lambda settings: collector)
    calls = []
    result = refresh(service, calls)
    assert result["collected_symbols"] == [SYMBOL] and result["pipeline_symbols"] == [SYMBOL]
    assert calls == [("indicator", SYMBOL), ("signal", SYMBOL), ("report", SYMBOL)]
    assert len(api.price_calls) == 1
    assert api.price_calls[0]["FID_INPUT_DATE_1"] == api.price_calls[0]["FID_INPUT_DATE_2"] == "20261102"
    loaded = storage.load("daily_prices", storage.latest_filename("daily_prices", SYMBOL))
    assert len(loaded) == 61
    assert result["collection_results"][0]["analysis_ready"] is True


@pytest.mark.parametrize("kind", ["csv", "sqlite"])
def test_actual_watchlist_short_bootstrap_saves_but_never_analyzes(harness, monkeypatch, tmp_path, kind):
    end = date(2026, 11, 2)
    collector, storage, _, _ = harness(kind, [end-timedelta(days=1), end])
    service = watch_service(collector, storage, kind, tmp_path)
    monkeypatch.setattr(watchlist, "MarketDataCollector", lambda settings: collector)
    calls = []
    result = refresh(service, calls)
    assert result["collected_symbols"] == [SYMBOL] and result["pipeline_symbols"] == []
    assert result["analysis_unready_symbols"] == [SYMBOL] and calls == []
    assert storage.latest_filename("daily_prices", SYMBOL)
    assert result["collection_results"][0]["price_coverage"]["request_complete"] is True


@pytest.mark.parametrize("metadata", [None, [], {}, {"status": "unknown", "request_complete": True},
    {"status": "complete", "request_complete": 1}, {"status": "complete", "request_complete": "true"}])
def test_direct_watchlist_invalid_metadata_cannot_save(harness, monkeypatch, tmp_path, metadata):
    end = date(2026, 11, 2)
    collector, storage, api, _ = harness("sqlite", [end])
    original = collector.collect_daily_prices

    def altered(*args):
        summary, frame = original(*args)
        frame.attrs["price_coverage"] = metadata
        return summary, frame

    monkeypatch.setattr(collector, "collect_daily_prices", altered)
    monkeypatch.setattr(watchlist, "MarketDataCollector", lambda settings: collector)
    service = watch_service(collector, storage, "sqlite", tmp_path)
    with pytest.raises(ValueError):
        watchlist._collect_watchlist_symbol_range(service, SYMBOL, start_date=end, end_date=end)
    all_datasets_absent(storage)
    assert len(api.calls) == len(api.price_calls) == 1


def test_direct_watchlist_empty_result_and_legacy_attrs_compatibility(harness, monkeypatch, tmp_path):
    end = date(2026, 11, 2)
    collector, storage, api, _ = harness("sqlite", [])
    monkeypatch.setattr(watchlist, "MarketDataCollector", lambda settings: collector)
    service = watch_service(collector, storage, "sqlite", tmp_path)
    assert watchlist._collect_watchlist_symbol_range(service, SYMBOL, start_date=end, end_date=end) is False
    all_datasets_absent(storage)
    api.dates = [end]
    original = collector.collect_daily_prices

    def legacy(*args):
        summary, frame = original(*args)
        frame.attrs.clear()
        return summary, frame

    monkeypatch.setattr(collector, "collect_daily_prices", legacy)
    assert watchlist._collect_watchlist_symbol_range(service, SYMBOL, start_date=end, end_date=end) is True
    assert storage.latest_filename("daily_prices", SYMBOL)


@pytest.mark.parametrize("layout,ready", [("short", False), ("duplicate", False), ("invalid", False),
                                         ("compact", True), ("iso", True), ("numeric", True)])
def test_stored_unique_date_gate_without_collection(harness, monkeypatch, tmp_path, layout, ready):
    end = date(2026, 11, 2)
    days = [d.date() for d in pd.date_range(end=end, periods=60)]
    frame = prices(days)
    if layout == "short":
        frame = frame.iloc[-59:].copy()
    elif layout == "duplicate":
        frame = pd.concat([frame.iloc[-5:]] * 15, ignore_index=True)
    elif layout == "invalid":
        frame.loc[:4, "stck_bsop_date"] = "invalid"
    elif layout == "iso":
        frame["stck_bsop_date"] = [d.isoformat() for d in days]
    elif layout == "numeric":
        frame["stck_bsop_date"] = frame["stck_bsop_date"].astype(float)
    collector, storage, api, _ = harness("sqlite", [])
    storage.save("daily_prices", f"{SYMBOL}_existing.csv", frame)
    storage.save("investor_daily_summary", f"{SYMBOL}_flow.csv",
                 pd.DataFrame({"stck_bsop_date": [end.strftime("%Y%m%d")]}))
    service = watch_service(collector, storage, "sqlite", tmp_path)
    # Existing numeric storage is a supported representation; this call checks
    # the real service's date acquisition as well as the new analysis gate.
    monkeypatch.setattr(watchlist, "MarketDataCollector", lambda settings: collector)
    calls = []
    result = refresh(service, calls)
    assert result["collected_symbols"] == []
    assert result["pipeline_symbols"] == ([SYMBOL] if ready else [])
    assert len(calls) == (3 if ready else 0) and api.calls == []


@pytest.mark.parametrize("outcome,expected", [(True, True), (False, False),
    ({"collected": True, "analysis_ready": True}, True),
    ({"collected": True, "analysis_ready": 1}, False),
    ({"collected": True, "analysis_ready": "true"}, False)])
def test_watchlist_typed_outcomes_and_legacy_bool_callbacks(harness, tmp_path, outcome, expected):
    collector, storage, _, _ = harness("sqlite", [])
    service = watch_service(collector, storage, "sqlite", tmp_path)
    calls = []
    result = refresh(service, calls, collect_callback=lambda *args: outcome)
    assert result["pipeline_symbols"] == ([SYMBOL] if expected else [])
    assert len(calls) == (3 if expected else 0)


def test_scheduler_actual_root_job_jsonl_failure_then_success(harness, monkeypatch, tmp_path):
    end = date(2026, 11, 2)
    collector, storage, _, _ = harness("sqlite", [end-timedelta(days=1), end])
    freeze_job(monkeypatch, end)
    clock = Clock()
    attempts, returned = [], []

    def collect(symbols, days):
        attempts.append(1)
        if len(attempts) == 1:
            raise URLError("synthetic temporary interruption")
        payload = job.collect_market_data_for_symbols(symbols, days, settings=collector.settings, collector=collector)
        payload["results"][0]["error"] = SECRET
        payload["results"][0]["raw_response"] = {"secret": SECRET}
        payload["results"][0]["price_coverage"]["untrusted_raw"] = SECRET
        returned.append(payload)
        return payload

    config = CollectionScheduleConfig(symbols=[SYMBOL], days=100, interval_minutes=1,
                                      log_path=tmp_path / "actual-cycle.jsonl")
    runner = ScheduledCollectionRunner(config, collector_fn=collect, sleep_fn=clock.sleep,
        now_fn=lambda: datetime(2026, 11, 2, 15) + timedelta(seconds=clock.now))
    assert runner.run_forever(max_runs=2) == 2
    entries = [json.loads(line) for line in config.log_path.read_text().splitlines()]
    assert [e["event"] for e in entries] == ["collection_started", "collection_failed", "collection_waiting",
                                             "collection_started", "collection_finished"]
    assert clock.waits == [60]
    finished = entries[-1]
    record = finished["collection_results"][0]
    assert record["status"] == "success" and record["saved_count"] == 5 and record["analysis_ready"] is False
    assert record["price_coverage"] == {k:v for k,v in returned[0]["results"][0]["price_coverage"].items() if k != "untrusted_raw"}
    assert finished["analysis_ready_symbols"] == [] and finished["analysis_unready_symbols"] == [SYMBOL]
    assert SECRET not in config.log_path.read_text() and "saved_files" not in json.dumps(finished)
    schedule_path = tmp_path / "schedule.yaml"
    schedule_path.write_text(f"symbols: ['{SYMBOL}']\nlog_path: {config.log_path}\n")
    status = load_schedule_status(schedule_path)
    assert status.total_logged_runs == 1 and status.last_success_count == 1
    assert status.last_failed_at and status.last_finished_at and status.last_error
    assert status.recent_entries[-1] == finished
    assert storage.latest_filename("daily_prices", SYMBOL)


def test_passive_snapshot_reads_do_not_collect_or_query_again(harness, monkeypatch, tmp_path):
    from sqlalchemy import Engine, event
    from invest_bot.dashboard.streamlit_state import DashboardFrameLoader

    collector, storage, api, _ = harness("sqlite", [])
    days = [date(2026, 11, 1), date(2026, 11, 2)]
    storage.save("daily_prices", f"{SYMBOL}_prices.csv", prices(days))
    service = watch_service(collector, storage, "sqlite", tmp_path)
    monkeypatch.setattr(service, "_load_symbol_name_map", lambda: {})
    snapshot = service.build_snapshot()
    statements = []

    def observe(conn, cursor, statement, parameters, context, executemany):
        if statement.lstrip().upper().startswith("SELECT"):
            statements.append(statement)

    event.listen(Engine, "before_cursor_execute", observe)
    try:
        processing = watchlist.build_watchlist_processing_times(snapshot, {SYMBOL})
        statuses = watchlist.build_watchlist_data_statuses(service, {SYMBOL}, today=days[-1],
                           processing_times=processing, latest_records=snapshot.latest_records)
        assert statuses and statuses[0].symbol == SYMBOL
        loader = DashboardFrameLoader(service, snapshot.latest_records)
        assert len(loader.read_preview(snapshot.raw_previews[0])) == 2
        assert loader.load_indicator(SYMBOL) is None
    finally:
        event.remove(Engine, "before_cursor_execute", observe)
    assert statements == [] and api.calls == []


def test_actual_collection_only_short_data_message(connected_ui):
    ctx = connected_ui
    ctx.mode["case"] = "short"
    actions.run_collect_action(ctx.items, 100)
    assert ctx.returned[0]["success_count"] == 2 and ctx.events == [("rerun",)]
    assert ctx.state.action_message_type == "warning"
    for text in ("2026-07-25", "2026-11-01", "2026-11-02", "2행", "2회", "미확인", "분석"):
        assert text in ctx.state.action_message



@pytest.mark.parametrize("kind", ["csv", "sqlite"])
def test_increment_snapshot_and_summary_match_actual_sixty_one_day_bounds(harness, monkeypatch, tmp_path, kind):
    captured = {}

    def retain(*args, **kwargs):
        value = harness(*args, **kwargs)
        captured["storage"] = value[1]
        return value

    test_actual_watchlist_one_day_increment_from_persisted_sixty_rows(retain, monkeypatch, tmp_path, kind)
    storage = captured["storage"]
    filename = f"{SYMBOL}_20260903_20261102.csv"
    assert storage.latest_filename("daily_prices", SYMBOL) == filename
    assert storage.latest_filename("daily_prices_summary", SYMBOL) == filename
    summary = storage.load("daily_prices_summary", filename).iloc[0]
    assert summary["start_date"] == "2026-09-03" and summary["end_date"] == "2026-11-02"
    assert int(summary["row_count"]) == 61
    assert len(storage.load("daily_prices", filename)) == 61


@pytest.mark.parametrize("mode,reason", [
    ("ohlc", "invalid_or_conflicting_observations"),
    ("nonfinite", "invalid_or_conflicting_observations"),
    ("conflict", "invalid_or_conflicting_observations"),
    ("date", "invalid_date"),
    ("payload", "invalid_response"),
    ("row_cap", "response_limit_exceeded"),
    ("stale_page", "out_of_window_no_progress"),
    ("zero_volume", None),
])
def test_representative_page_quality_at_actual_batch_storage_boundary(harness, mode, reason):
    start, end = date(2026, 1, 1), date(2026, 1, 2)
    if mode == "stale_page":
        end = date(2026, 5, 1)
    days = [d.date() for d in pd.date_range(start, end)]
    collector, storage, api, _ = harness("sqlite", days)
    original, first = api.get_json, {}

    def query(api_path, tr_id, params, **kwargs):
        payload = original(api_path, tr_id, params, **kwargs)
        if not api_path.endswith("inquire-daily-itemchartprice"):
            return payload
        rows = payload["output2"]
        if mode == "ohlc":
            rows[0]["stck_hgpr"] = "99"
        elif mode == "nonfinite":
            rows[0]["stck_clpr"] = "inf"
        elif mode == "conflict":
            changed = dict(rows[0], stck_clpr="106")
            rows.append(changed)
        elif mode == "date":
            rows[0]["stck_bsop_date"] = "2026-01-02"
        elif mode == "payload":
            payload["output2"] = SECRET
        elif mode == "row_cap":
            payload["output2"] = [rows[0]] * 101
        elif mode == "stale_page":
            if len(api.price_calls) == 1:
                first["rows"] = copy.deepcopy(rows)
            else:
                payload["output2"] = copy.deepcopy(first["rows"])
        elif mode == "zero_volume":
            rows[0].update(stck_oprc="0", stck_hgpr="0", stck_lwpr="0", acml_vol="0")
        return payload

    api.get_json = query
    result = collector.collect_symbol_bundle(SYMBOL, start, end)
    if reason is not None:
        assert result.status == "failed" and result.price_coverage["reason"] == reason
        assert result.analysis_ready is False and result.saved_files == []
        assert len(api.calls) == len(api.price_calls) == (2 if mode == "stale_page" else 1)
        assert SECRET not in result.error
        all_datasets_absent(storage)
    else:
        assert result.status == "success" and result.analysis_ready is False
        assert result.price_coverage["rows"] == 2
        filename = storage.latest_filename("daily_prices", SYMBOL)
        loaded = storage.load("daily_prices", filename)
        assert len(loaded) == 2 and 0 in pd.to_numeric(loaded.acml_vol).tolist()


def test_planned_window_cap_rejects_before_any_endpoint_or_storage(harness):
    collector, storage, api, _ = harness("sqlite", [date(2026, 1, 1)])
    collector.collector.price_history.max_pages = 1
    result = collector.collect_symbol_bundle(SYMBOL, date(2026, 1, 1), date(2026, 5, 1))
    assert result.status == "failed" and result.price_coverage["reason"] == "page_limit"
    assert result.price_coverage["requests"] == 0 and api.calls == [] and result.saved_files == []
    all_datasets_absent(storage)


@pytest.mark.parametrize("mode,expected_reason", [
    ("matching", "verified_listing_date"),
    ("wrong_symbol", "listing_symbol_mismatch"),
    ("ambiguous", "ambiguous_listing_dates"),
])
def test_listing_explanation_uses_only_matching_unambiguous_official_evidence(harness, mode, expected_reason):
    collector, storage, api, _ = harness("sqlite", [date(2026, 1, 2), date(2026, 1, 3)], listing="20260102")
    original = api.get_json

    def query(api_path, tr_id, params, **kwargs):
        payload = original(api_path, tr_id, params, **kwargs)
        if api_path.endswith("search-stock-info"):
            if mode == "wrong_symbol":
                payload["output"]["pdno"] = "000660"
            elif mode == "ambiguous":
                payload["output"]["kosdaq_mket_lstg_dt"] = "20260101"
        return payload

    api.get_json = query
    result = collector.collect_symbol_bundle(SYMBOL, date(2026, 1, 1), date(2026, 1, 3))
    assert result.status == "success" and result.analysis_ready is False
    assert result.price_coverage["range_reason"] == expected_reason
    assert result.price_coverage["trading_days_verified"] is False
    assert result.price_coverage["listing_date"] == ("2026-01-02" if mode == "matching" else "")
    assert len(storage.load("daily_prices", storage.latest_filename("daily_prices", SYMBOL))) == 2
