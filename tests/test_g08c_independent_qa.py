"""QA03 minimal real-renderer legacy metadata regressions."""
from __future__ import annotations

from copy import deepcopy
from datetime import UTC, date, datetime
import json

import pandas as pd
import pytest

from invest_bot.backtest import resolve_backtest_combination_settings
from invest_bot.dashboard import streamlit_backtest as app
from invest_bot.dashboard.service import DashboardDataService
from tests.test_streamlit_backtest import _FakeStreamlit


def ui_generated_combination(monkeypatch):
    """Generate through the actual UI execution boundary, adapters and runner."""
    class Clock:
        @classmethod
        def now(cls, tz=None):
            return datetime(2026, 11, 8, 1, 2, 3, tzinfo=UTC)

    monkeypatch.setattr(app, "datetime", Clock)
    frame = pd.DataFrame({
        "date": pd.date_range("2026-05-04", periods=3),
        "close": [100., 105., 110.], "rsi_14": [50., 50., 50.],
        "ma_5": [100., 102., 104.], "ma_20": [99., 101., 103.],
        "ma_60": [98., 100., 102.], "momentum_20": [1., 1., 1.],
    })
    saved = frame[["date", "close"]].assign(signal="hold", signal_reason="QA saved")
    inputs = app.LoadedBacktestInputs(
        symbol="005930",
        indicator=app.LoadedDataset("daily_prices_indicators", "005930_actual_indicators.csv", frame),
        investor=app.LoadedDataset("investor_daily", None, None),
        price=app.LoadedDataset("daily_prices", "005930_unused_raw.csv", frame[["date", "close"]]),
        golden_cross_signal=app.LoadedDataset("golden_cross_signals", "005930_actual_saved.csv", saved),
    )
    return app._execute_backtests(
        [app.ResolvedSymbol("005930", "005930", "QA synthetic")],
        ["rsi", "golden-cross"], {"005930": inputs},
        strategy_parameters={"rsi": {"buy_threshold": 40., "sell_threshold": 60.}},
        combination_settings=resolve_backtest_combination_settings(
            ["rsi", "golden-cross"], "and", {"rsi": 1.5, "golden-cross": .5}),
        preparation_period=(date(2025,5,4), date(2026,5,4)),
    )


@pytest.mark.parametrize("metadata", [
    pytest.param([], id="json-list"),
    pytest.param(None, id="json-null"),
    pytest.param({"metadata_version": 1}, id="incomplete-v1"),
    pytest.param({"mode": [], "weights": {}}, id="invalid-mode-dict"),
    pytest.param({}, id="unversioned-empty-object"),
])
def test_real_results_renderer_does_not_crash_or_infer_legacy_combination(monkeypatch, tmp_path, metadata):
    result = ui_generated_combination(monkeypatch)
    # Perturb only persisted-style metadata in actual generated results. This is
    # not a hand-built successful combination summary or an engine replacement.
    result = deepcopy(result)
    summary = result["summary_frame"].loc[
        result["summary_frame"].strategy_id == "combination-and"].copy()
    assert len(summary) == 1 and "metadata_version" in summary.iloc[0].combination_settings_json
    summary["combination_settings_json"] = json.dumps(metadata)
    summary = summary.drop(columns=["combination_summary", "strategy_parameter_summary"], errors="ignore")
    result["summary_frame"] = summary
    result["comparison_frame"] = app._build_comparison_frame(summary)
    screen = _FakeStreamlit()
    screen.session_state[app.BACKTEST_PARAMETERS_KEY] = {
        "rsi": {"buy_threshold": 20., "sell_threshold": 80.}}
    monkeypatch.setattr(app, "st", screen)

    def forbidden(*args, **kwargs):
        pytest.fail("viewing an old result triggered execution or source generation")

    monkeypatch.setattr(app.DEFAULT_BACKTEST_RUNNER, "run", forbidden)
    monkeypatch.setattr(app.DEFAULT_BACKTEST_ADAPTER_REGISTRY, "build_signal_rows", forbidden)
    for name in ("collect_market_data_for_symbols", "generate_indicators_for_symbol",
                 "generate_golden_cross_signals_for_symbol"):
        monkeypatch.setattr(app, name, forbidden)
    service = DashboardDataService(raw_root=tmp_path/"raw", processed_root=tmp_path/"processed")
    app._render_results_panel(service, result)
    text = " ".join(screen.markdown_calls + screen.caption_calls + screen.info_messages)
    assert any(phrase in text for phrase in ("기록 없음", "잘못된", "해석할 수 없음"))
    assert "매수 RSI 기준 20" not in text and "매도 RSI 기준 80" not in text



# Additional independent representative integrations, preserving original five.
from pathlib import Path

from invest_bot.backtest.artifacts import BacktestArtifactSaveError, save_backtest_batch
from invest_bot.backtest.persistence import (
    BACKTEST_TRADES_OUTPUT, build_output_filename, read_combination_metadata,
)
from invest_bot.dashboard.streamlit_backtest_history import BACKTEST_HISTORY_SELECTION_KEY
from invest_bot.db.frame_storage import DbFrameStorage
from invest_bot.db.repositories import frame_from_json, frame_to_json
from invest_bot.market.storage import CsvStorage
from tests.helpers import init_test_db

RANGE_FIELDS = (
    "input_range_status", "input_range_reason", "input_start_date", "input_end_date",
    "input_row_count", "input_excluded_rows", "prepare_selection_start_date",
    "prepare_selection_end_date", "prepare_lookback_days",
)


def generated(monkeypatch, *, multiple=False, custom=False, rsi=None, mode="or"):
    class Clock:
        @classmethod
        def now(cls, tz=None):
            return datetime(2026, 11, 8, 2, 3, 4, tzinfo=UTC)

    monkeypatch.setattr(app, "datetime", Clock)
    symbols = ["005930", "000660"] if multiple else ["005930"]
    sources = {}
    for n, symbol in enumerate(symbols):
        frame = pd.DataFrame({
            "date": pd.date_range("2026-06-01", periods=6),
            "close": [100.,120.,60.,100.,110.,108.] if n == 0 else [200.]*6,
            "rsi_14": [35.,50.,50.,65.,50.,50.] if n == 0 else [50.]*6,
            "ma_5": [99.,121.,61.,99.,111.,109.] if n == 0 else [200.]*6,
            "ma_20": [100.,120.,60.,100.,110.,108.] if n == 0 else [200.]*6,
            "ma_60": [95.]*6, "momentum_20": [1.]*6,
        })
        signal = ["buy","hold","hold","sell","hold","hold"] if n == 0 else ["hold"]*6
        saved = frame[["date","close"]].assign(signal=signal, signal_reason="QA_ACTUAL_SAVED")
        sources[symbol] = app.LoadedBacktestInputs(
            symbol=symbol,
            indicator=app.LoadedDataset("daily_prices_indicators", f"{symbol}_recorded_indicators.csv", frame),
            investor=app.LoadedDataset("investor_daily", f"{symbol}_unused_investor.csv", pd.DataFrame()),
            price=app.LoadedDataset("daily_prices", f"{symbol}_unused_price.csv", frame[["date","close"]]),
            golden_cross_signal=app.LoadedDataset("golden_cross_signals", f"{symbol}_recorded_saved.csv", saved),
        )
    parameters = {"rsi": rsi if rsi is not None else {"buy_threshold":40.,"sell_threshold":60.}}
    if custom:
        parameters["golden-cross"] = {"short_window":2.,"long_window":3.}
    result = app._execute_backtests(
        [app.ResolvedSymbol(s,s,"QA "+s) for s in symbols], ["rsi","golden-cross"], sources,
        strategy_parameters=parameters,
        combination_settings=resolve_backtest_combination_settings(
            ["rsi","golden-cross"],mode,{"rsi":1.75,"golden-cross":.25}),
        preparation_period=(date(2025,6,1),date(2026,6,1)))
    return result


def storage_service(tmp_path, kind):
    if kind == "sqlite":
        url = f"sqlite:///{tmp_path/'qa03.db'}"
        init_test_db(url)
        storage = DbFrameStorage(url)
        service = DashboardDataService(dataset_storage=storage)
    else:
        storage = CsvStorage(tmp_path/"processed")
        service = DashboardDataService(raw_root=tmp_path/"raw",processed_root=storage.root_dir)
    service._load_symbol_name_map = lambda: {}
    return storage, service


def normalized_field(field, value):
    if value is None or pd.isna(value) or value == "":
        return None
    if field in ("input_row_count","input_excluded_rows","prepare_lookback_days"):
        return int(value)
    return str(value)


def forbid_execution(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("save/history performed execution or source generation")
    for name in ("collect_market_data_for_symbols","generate_indicators_for_symbol",
                 "generate_golden_cross_signals_for_symbol","_load_backtest_inputs"):
        monkeypatch.setattr(app,name,forbidden)
    monkeypatch.setattr(app.DEFAULT_BACKTEST_RUNNER,"run",forbidden)
    monkeypatch.setattr(app.DEFAULT_BACKTEST_ADAPTER_REGISTRY,"build_signal_rows",forbidden)


@pytest.mark.parametrize("kind", ["csv","sqlite"])
def test_actual_ui_output_explicit_save_new_service_history_roundtrip(monkeypatch,tmp_path,kind):
    result = generated(monkeypatch,multiple=True)
    original_summary = deepcopy(result["summary_frame"])
    original_trades = deepcopy(result["trade_frame"])
    assert len(original_summary)==6 and len(original_trades)==3
    combo = original_summary.query("symbol=='005930' and strategy_id=='combination-or'").iloc[0]
    assert combo["trade_count"]==1
    assert combo["final_equity"]==pytest.approx(11/12,rel=1e-12,abs=1e-12)
    assert combo["total_return_pct"]==pytest.approx(-100/12,rel=1e-12,abs=1e-12)
    assert combo["max_drawdown_pct"]==pytest.approx(50.,rel=1e-12,abs=1e-12)
    assert original_summary.query("symbol=='000660'")["trade_count"].eq(0).all()
    storage,service = storage_service(tmp_path,kind)
    writes = []
    original_save = storage.save

    def save(dataset,filename,frame):
        writes.append((dataset,filename))
        return original_save(dataset,filename,frame)

    monkeypatch.setattr(storage,"save",save)
    assert writes==[]
    if kind=="csv":
        assert len(save_backtest_batch(storage,original_summary,original_trades))==12
    else:
        screen = _FakeStreamlit(button_values={app.BACKTEST_SAVE_RESULTS_KEY:True})
        monkeypatch.setattr(app,"st",screen)
        app._render_save_results_panel(service,result)
        assert screen.success_messages and not screen.error_messages
        assert len(result["saved_artifacts"])==12
        app._render_save_results_panel(service,result)
        assert len(writes)==12
    assert len(writes)==12
    # A new service observes only the saved artifacts. No originals are seeded.
    fresh = DashboardDataService(dataset_storage=storage) if kind=="sqlite" else DashboardDataService(
        raw_root=tmp_path/"raw",processed_root=storage.root_dir)
    fresh._load_symbol_name_map=lambda:{}
    forbid_execution(monkeypatch)
    original_load=storage.load
    def load(dataset,filename):
        assert dataset in ("backtest_summaries","backtest_trades"),"source artifact reread"
        return original_load(dataset,filename)
    monkeypatch.setattr(storage,"load",load)
    entries,messages=app._load_backtest_history_entries(fresh)
    assert not messages and len(entries)==6
    assert {entry["symbol"] for entry in entries}=={"005930","000660"}
    expected=original_summary.set_index("run_id",drop=False)
    codec_summary=frame_from_json(frame_to_json(original_summary)).set_index("run_id",drop=False) if kind=="sqlite" else None
    json_fields=("combination_settings_json","strategy_parameters_json","input_sources_json")
    for entry in entries:
        row=entry["summary_frame"].iloc[0]
        old=expected.loc[row["run_id"]]
        for field in ("run_id","run_group_id","symbol","strategy_id",*json_fields,*RANGE_FIELDS):
            assert normalized_field(field,row[field])==normalized_field(field,old[field])
        for field in ("final_equity","max_drawdown_pct","total_return_pct"):
            if kind=="sqlite":
                assert float(row[field])==float(codec_summary.loc[row["run_id"],field])
            else:
                assert float(row[field])==pytest.approx(float(old[field]),rel=1e-12,abs=1e-12)
    previews=fresh.list_backtest_history_previews("backtest_trades")
    all_trades=pd.concat([fresh.load_preview_frame(p) for p in previews],ignore_index=True)
    assert len(all_trades)==3 and set(all_trades.symbol)=={"005930"}
    before=original_trades.sort_values("run_id").reset_index(drop=True)
    after=all_trades.sort_values("run_id").reset_index(drop=True)
    codec_trades=frame_from_json(frame_to_json(before)) if kind=="sqlite" else None
    for n,old in before.iterrows():
        row=after.iloc[n]
        for field in ("run_id","symbol","strategy_id","combination_settings_json","strategy_parameters_json"):
            assert row[field]==old[field]
        for field in ("entry_date","exit_date","entry_signal_date","exit_signal_date"):
            assert pd.Timestamp(row[field]).isoformat()==pd.Timestamp(old[field]).isoformat()
        for field in ("entry_price","exit_price","return_pct"):
            if kind=="sqlite":
                assert float(row[field])==float(codec_trades.iloc[n][field])
            else:
                assert float(row[field])==pytest.approx(float(old[field]),rel=1e-12,abs=1e-12)
    selected=next(e for e in entries if e["symbol"]=="005930" and e["strategy_id"]=="combination-or")
    screen=_FakeStreamlit(selectbox_values={BACKTEST_HISTORY_SELECTION_KEY:selected["entry_id"]})
    screen.session_state[app.BACKTEST_PARAMETERS_KEY]={"rsi":{"buy_threshold":20.,"sell_threshold":80.}}
    monkeypatch.setattr(app,"st",screen)
    loaded=app._render_backtest_history_panel(fresh)
    assert loaded is not None
    app._render_results_panel(fresh,loaded)
    text=" ".join(screen.caption_calls+screen.markdown_calls)
    assert "40" in text and "60" in text and "005930_recorded_indicators.csv" in text
    assert len(writes)==12 and loaded["daily_equity_frame"].empty
    empty=next(e for e in entries if e["symbol"]=="000660" and e["strategy_id"]=="combination-or")
    zero,errors=app._load_backtest_history_result(fresh,empty)
    assert not errors and zero["trade_frame"].empty and zero["summary_frame"].iloc[0]["trade_count"]==0
    pd.testing.assert_frame_equal(result["summary_frame"],original_summary)
    pd.testing.assert_frame_equal(result["trade_frame"],original_trades)


@pytest.mark.parametrize("custom", [False,True])
def test_recorded_provenance_matches_actual_saved_or_computed_adapter(monkeypatch,custom):
    seen={}
    original=app.DEFAULT_BACKTEST_ADAPTER_REGISTRY.build_signal_rows
    def build(strategy_id,*args,**kwargs):
        output=original(strategy_id,*args,**kwargs)
        seen[strategy_id]=deepcopy(output.signal_rows)
        return output
    monkeypatch.setattr(app.DEFAULT_BACKTEST_ADAPTER_REGISTRY,"build_signal_rows",build)
    result=generated(monkeypatch,custom=custom,mode="weighted")
    combo=result["summary_frame"].query("strategy_id=='combination-weighted'").iloc[0]
    record=read_combination_metadata(combo.combination_settings_json)
    assert record.status=="recorded"
    metadata=record.metadata
    assert metadata["mode"]=="weighted" and metadata["weights"]=={"rsi":1.75,"golden-cross":.25}
    components=metadata["components"]
    assert components["rsi"]["strategy_parameters"]=={"buy_threshold":40.,"sell_threshold":60.}
    actual_saved=bool(seen["golden-cross"]["signal_reason"].eq("QA_ACTUAL_SAVED").all())
    assert actual_saved is not custom
    golden=components["golden-cross"]
    assert golden["uses_saved_signal"] is (not custom)
    assert golden["strategy_parameters"]==({"short_window":2.,"long_window":3.} if custom else {"short_window":5.,"long_window":20.})
    assert golden["input_sources"]["signal"]==({"dataset":None,"filename":None} if custom else
        {"dataset":"golden_cross_signals","filename":"005930_recorded_saved.csv"})
    for component in components.values():
        assert component["input_sources"]["indicator"]["filename"]=="005930_recorded_indicators.csv"
        assert component["input_sources"]["price"]==component["input_sources"]["investor"]=={"dataset":None,"filename":None}


def test_default_parameters_and_detached_reader_do_not_replace_recorded_settings(monkeypatch):
    recorded=generated(monkeypatch)
    default=generated(monkeypatch,rsi={})
    first=recorded["summary_frame"].query("strategy_id=='combination-or'").iloc[0].combination_settings_json
    second=default["summary_frame"].query("strategy_id=='combination-or'").iloc[0].combination_settings_json
    assert read_combination_metadata(first).metadata["components"]["rsi"]["strategy_parameters"]=={"buy_threshold":40.,"sell_threshold":60.}
    assert read_combination_metadata(second).metadata["components"]["rsi"]["strategy_parameters"]=={"buy_threshold":30.,"sell_threshold":70.}
    detached=read_combination_metadata(first).metadata
    detached["components"]["rsi"]["strategy_parameters"]["buy_threshold"]=999.
    assert read_combination_metadata(first).metadata["components"]["rsi"]["strategy_parameters"]["buy_threshold"]==40.


def test_save_panel_without_click_does_not_even_open_storage(monkeypatch):
    result=generated(monkeypatch)
    screen=_FakeStreamlit()
    monkeypatch.setattr(app,"st",screen)
    from types import SimpleNamespace
    service=SimpleNamespace(get_dataset_storage=lambda:pytest.fail("storage touched without save click"))
    forbid_execution(monkeypatch)
    app._render_save_results_panel(service,result)
    assert not screen.success_messages and "saved_artifacts" not in result



@pytest.mark.parametrize("kind", ["existing-batch","late-zero-byte"])
def test_existing_artifact_collision_never_overwrites_or_starts_batch(monkeypatch,tmp_path,kind):
    result=generated(monkeypatch)
    storage,_=storage_service(tmp_path,"csv")
    if kind=="existing-batch":
        save_backtest_batch(storage,result["summary_frame"],result["trade_frame"])
    else:
        last=result["summary_frame"].iloc[[-1]]
        filename=build_output_filename(last,BACKTEST_TRADES_OUTPUT)
        path=storage.root_dir/"backtest_trades"/filename
        path.parent.mkdir(parents=True)
        path.write_bytes(b"")
    import hashlib
    before={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in storage.root_dir.glob("backtest_*/*.csv")}
    writes=[]
    monkeypatch.setattr(storage,"save",lambda *a,**k:writes.append(a) or pytest.fail("collision wrote a file"))
    with pytest.raises(FileExistsError):
        save_backtest_batch(storage,result["summary_frame"],result["trade_frame"])
    assert writes==[]
    assert before=={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in storage.root_dir.glob("backtest_*/*.csv")}


@pytest.mark.parametrize("case", ["late-identity","late-legacy-combo","orphan-trade"])
def test_whole_batch_invalid_late_run_has_zero_backend_writes(monkeypatch,tmp_path,case):
    result=generated(monkeypatch)
    summary=deepcopy(result["summary_frame"])
    trades=deepcopy(result["trade_frame"])
    if case=="late-identity":
        summary.loc[summary.index[-1],"run_id"]="invalid"
    elif case=="late-legacy-combo":
        summary.loc[summary.index[-1],"combination_settings_json"]="{}"
    else:
        extra=trades.iloc[[0]].copy()
        extra["run_id"]="foreign_run"
        trades=pd.concat([trades,extra],ignore_index=True)
    storage,_=storage_service(tmp_path,"csv")
    writes=[]
    monkeypatch.setattr(storage,"save",lambda *a,**k:writes.append(a) or pytest.fail("invalid batch wrote output"))
    with pytest.raises(ValueError):
        save_backtest_batch(storage,summary,trades)
    assert writes==[] and not list(storage.root_dir.glob("backtest_*/*.csv"))


def test_partial_backend_failure_exposes_confirmed_saves_and_refuses_retry_overwrite(monkeypatch,tmp_path):
    result=generated(monkeypatch)
    storage,_=storage_service(tmp_path,"csv")
    original=storage.save
    attempts=[]
    def fail_third(dataset,filename,frame):
        attempts.append((dataset,filename))
        if len(attempts)==3:
            raise OSError("QA injected backend failure")
        return original(dataset,filename,frame)
    monkeypatch.setattr(storage,"save",fail_third)
    with pytest.raises(BacktestArtifactSaveError) as error:
        save_backtest_batch(storage,result["summary_frame"],result["trade_frame"])
    assert len(error.value.saved)==2
    assert error.value.failed_dataset=="backtest_summaries"
    assert isinstance(error.value.__cause__,OSError)
    assert len(list(storage.root_dir.glob("backtest_*/*.csv")))==2
    with pytest.raises(FileExistsError):
        save_backtest_batch(storage,result["summary_frame"],result["trade_frame"])
    assert len(attempts)==3


def test_actual_save_button_partial_failure_is_not_success(monkeypatch,tmp_path):
    result=generated(monkeypatch)
    storage,service=storage_service(tmp_path,"sqlite")
    original=storage.save
    attempts=[]
    def fail_second(dataset,filename,frame):
        attempts.append((dataset,filename))
        if len(attempts)==2:
            raise OSError("QA injected partial failure")
        return original(dataset,filename,frame)
    monkeypatch.setattr(storage,"save",fail_second)
    screen=_FakeStreamlit(button_values={app.BACKTEST_SAVE_RESULTS_KEY:True})
    monkeypatch.setattr(app,"st",screen)
    forbid_execution(monkeypatch)
    app._render_save_results_panel(service,result)
    assert not screen.success_messages and "saved_artifacts" not in result
    assert any("1" in text and "일부" in text for text in screen.error_messages)
    assert len(service.list_backtest_history_previews("backtest_summaries"))==1


def test_unsupported_record_renderer_does_not_reuse_current_or_explicit_defaults(monkeypatch,tmp_path):
    result=generated(monkeypatch)
    row=result["summary_frame"].query("strategy_id=='combination-or'").copy()
    record=json.loads(row.iloc[0].combination_settings_json)
    record["metadata_version"]=99
    row["combination_settings_json"]=json.dumps(record)
    result["summary_frame"]=row
    assert read_combination_metadata(row.iloc[0].combination_settings_json).status=="unsupported"
    screen=_FakeStreamlit()
    screen.session_state[app.BACKTEST_PARAMETERS_KEY]={"rsi":{"buy_threshold":20,"sell_threshold":80}}
    monkeypatch.setattr(app,"st",screen)
    forbid_execution(monkeypatch)
    service=DashboardDataService(raw_root=tmp_path/"raw",processed_root=tmp_path/"processed")
    app._render_results_panel(service,result)
    text=" ".join(screen.caption_calls+screen.markdown_calls)
    assert "미지원" in text
    assert "매수 RSI 기준 20" not in text and "매도 RSI 기준 80" not in text
