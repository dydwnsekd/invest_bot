from datetime import date, datetime
import json
from types import SimpleNamespace

import pandas as pd
import pytest

from invest_bot.config.settings import AppSettings
from invest_bot.dashboard import streamlit_actions as actions, streamlit_backtest as backtest, streamlit_watchlist as watchlist
from invest_bot.jobs.scheduled_collection import CollectionScheduleConfig, ScheduledCollectionRunner, load_schedule_status
from invest_bot.market.symbol_lookup import ResolvedSymbol


class Session(dict):
    __getattr__ = dict.get
    def __setattr__(self, key, value):
        self[key] = value


def coverage(rows=2):
    return dict(status='complete', reason='bounded_windows_exhausted', request_complete=True,
                requested_start='2025-11-02', requested_end='2026-11-02',
                observed_start='2026-01-01', observed_end='2026-01-02', rows=rows,
                requests=4, window_count=4, trading_days_verified=False,
                range_reason='unverified_start_boundary')


def result(ready=()):
    return dict(success_count=1, failed_count=0, successful_symbols=['005930'],
                failed_symbols=[], symbols=['005930'], analysis_ready_symbols=list(ready),
                analysis_unready_symbols=[] if ready else ['005930'],
                results=[dict(symbol='005930', status='success', analysis_ready=bool(ready),
                              price_coverage=coverage(), saved_files=['safe.csv'],
                              error='do-not-log-raw-error', raw_response={'secret': 'do-not-log'})])


@pytest.fixture
def ui(monkeypatch):
    session = Session()
    st = SimpleNamespace(session_state=session, rerun=lambda: None)
    monkeypatch.setattr(actions, 'st', st)
    monkeypatch.setattr(backtest, 'st', st)
    calls = []
    for module in [actions, backtest]:
        for name in ['generate_indicators_for_symbol', 'generate_golden_cross_signals_for_symbol']:
            monkeypatch.setattr(module, name, lambda symbol, name=name: calls.append((name, symbol)))
    monkeypatch.setattr(actions, 'generate_market_report_for_symbol', lambda symbol, **kw: calls.append(('report', symbol)) or {})
    items = [ResolvedSymbol(raw_input='005930', symbol='005930', symbol_name='삼성전자')]
    return session, calls, items


@pytest.mark.parametrize('entry', ['full', 'prepare'])
@pytest.mark.parametrize('ready', [[], None, '005930', [False], ['009999']])
def test_collected_short_or_invalid_readiness_never_runs_analysis(ui, monkeypatch, entry, ready):
    session, calls, items = ui
    payload = result(); payload['analysis_ready_symbols'] = ready
    module = actions if entry == 'full' else backtest
    monkeypatch.setattr(module, 'collect_market_data_for_symbols', lambda **kw: payload)
    if entry == 'full': actions.run_full_pipeline_action(items, 365, settings=AppSettings())
    else: backtest._run_prepare_action(items, 365)
    assert calls == []
    assert '분석' in session.action_message and '1' in session.action_message
    assert session.action_message_type == 'warning'
    assert '2025-11-02' in session.action_message and '2026-01-01' in session.action_message


@pytest.mark.parametrize('entry', ['full', 'prepare'])
def test_mixed_readiness_runs_only_eligible_collected_symbol(ui, monkeypatch, entry):
    session, calls, items = ui
    payload = result(['005930']); payload['successful_symbols'].append('000660'); payload['success_count'] = 2
    payload['analysis_unready_symbols'] = ['000660']
    items.append(ResolvedSymbol(raw_input='000660', symbol='000660', symbol_name='SK하이닉스'))
    module = actions if entry == 'full' else backtest
    monkeypatch.setattr(module, 'collect_market_data_for_symbols', lambda **kw: payload)
    if entry == 'full': actions.run_full_pipeline_action(items, 365, settings=AppSettings())
    else: backtest._run_prepare_action(items, 365)
    assert calls and all(symbol == '005930' for _, symbol in calls)
    assert session.action_message_type == 'warning'
    assert '분석' in session.action_message


@pytest.mark.parametrize('entry', ['full', 'prepare'])
def test_legacy_collection_success_keeps_existing_pipeline(ui, monkeypatch, entry):
    _, calls, items = ui
    payload = dict(success_count=1, failed_count=0, successful_symbols=['005930'])
    module = actions if entry == 'full' else backtest
    monkeypatch.setattr(module, 'collect_market_data_for_symbols', lambda **kw: payload)
    if entry == 'full': actions.run_full_pipeline_action(items, 365, settings=AppSettings())
    else: backtest._run_prepare_action(items, 365)
    assert calls and all(symbol == '005930' for _, symbol in calls)


def test_collection_message_displays_dates_counts_and_uncertainty(ui, monkeypatch):
    session, calls, items = ui
    monkeypatch.setattr(actions, 'collect_market_data_for_symbols', lambda **kw: result())
    actions.run_collect_action(items, 365)
    for text in ['2025-11-02', '2026-11-02', '2026-01-01', '2026-01-02', '2행', '4회', '미확인', '분석']:
        assert text in session.action_message
    assert session.action_message_type == 'warning' and not calls
    assert 'do-not-log' not in session.action_message


def test_scheduler_keeps_primitive_coverage_without_raw_payload(tmp_path):
    payload = result()
    config = CollectionScheduleConfig(symbols=['005930'], days=365, log_path=tmp_path/'cycle.jsonl')
    runner = ScheduledCollectionRunner(config, collector_fn=lambda **kw: payload,
                                      now_fn=lambda: datetime(2026, 11, 2, 15))
    runner.run_once()
    entries = [json.loads(line) for line in config.log_path.read_text().splitlines()]
    finished = entries[-1]
    assert finished['collection_results'][0]['price_coverage'] == coverage()
    assert finished['analysis_ready_symbols'] == []
    assert finished['analysis_unready_symbols'] == ['005930']
    assert 'do-not-log' not in config.log_path.read_text()
    schedule_file = tmp_path/'schedule.yaml'
    schedule_file.write_text(f"symbols: ['005930']\nlog_path: {config.log_path}\n")
    assert load_schedule_status(schedule_file).total_logged_runs == 1


def frame(rows, start='2026-01-01', *, metadata=True):
    value = pd.DataFrame({'stck_bsop_date': pd.date_range(start, periods=rows).strftime('%Y%m%d'), 'stck_clpr': [100]*rows})
    if metadata: value.attrs['price_coverage'] = coverage(rows)
    return value


@pytest.fixture
def watch(monkeypatch):
    saved, pipeline = [], []
    state = {'fresh': frame(2), 'existing': None}
    class Collector:
        storage = SimpleNamespace(save=lambda *a, **k: saved.append(('merged', a)))
        def collect_daily_prices(self, symbol, start, end):
            prices = state['fresh'].copy()
            if 'price_coverage' in prices.attrs:
                prices.attrs['price_coverage'] = dict(prices.attrs['price_coverage'], requested_start=start.isoformat(), requested_end=end.isoformat())
            return pd.DataFrame(), prices
        def save_daily_prices(self, *a, **k): saved.append(('price', a))
        def collect_investor_daily(self, *a): return pd.DataFrame(), pd.DataFrame()
        def save_investor_daily(self, *a): saved.append(('investor', a))
    monkeypatch.setattr(watchlist, 'MarketDataCollector', lambda settings: Collector())
    monkeypatch.setattr(watchlist, '_load_latest_dataset_frame', lambda service, dataset, symbol: state['existing'] if dataset=='daily_prices' else pd.DataFrame({'pdno':['005930']}))
    def latest(service, dataset, symbol, columns):
        if dataset=='daily_prices' and state['existing'] is not None:
            return pd.to_datetime(state['existing'].stck_bsop_date.iloc[-1]).date()
        return None
    monkeypatch.setattr(watchlist, '_load_latest_dataset_date', latest)
    monkeypatch.setattr(watchlist, '_latest_expected_market_date', lambda value: value)
    service = SimpleNamespace(_settings=AppSettings())
    def refresh():
        return watchlist.refresh_favorite_symbols_if_needed(service, {'005930'}, today=date(2026,4,30),
                    analyze_callback=lambda s: pipeline.append(('analysis',s)),
                    signal_callback=lambda s: pipeline.append(('signal',s)),
                    report_callback=lambda s: pipeline.append(('report',s)))
    return service, state, saved, pipeline, refresh


def test_watchlist_saves_short_bootstrap_without_pipeline(watch):
    _, _, saved, pipeline, refresh = watch
    outcome = refresh()
    assert saved and outcome['collected_symbols'] == ['005930']
    assert outcome['pipeline_symbols'] == [] and pipeline == []


def test_watchlist_small_increment_uses_existing_history(watch):
    _, state, saved, pipeline, refresh = watch
    state['existing'] = frame(70, metadata=False)
    state['fresh'] = frame(1, start='2026-04-01')
    outcome = refresh()
    assert saved and outcome['pipeline_symbols'] == ['005930'] and len(pipeline)==3


@pytest.mark.parametrize('status', ['unknown','incomplete'])
def test_watchlist_incomplete_result_never_saves(watch, status):
    service, state, saved, _, _ = watch
    state['fresh'].attrs['price_coverage']['status'] = status
    with pytest.raises(ValueError):
        watchlist._collect_watchlist_symbol_range(service,'005930',start_date=date(2026,1,1),end_date=date(2026,4,30))
    assert saved == []


def test_collection_partial_storage_is_not_reported_as_no_saved_data(ui, monkeypatch):
    session, _, items = ui
    payload = result(); payload.update(success_count=0, failed_count=1, successful_symbols=[])
    payload['results'][0]['status'] = 'failed'
    monkeypatch.setattr(actions, 'collect_market_data_for_symbols', lambda **kw: payload)
    actions.run_collect_action(items, 365)
    assert '일부 자료가 저장' in session.action_message
    assert '최신 데이터가 저장되지' not in session.action_message


def test_multiple_coverage_messages_identify_symbols(ui, monkeypatch):
    session, _, items = ui
    payload = result()
    payload['results'] += [dict(payload['results'][0], symbol='000660')]
    monkeypatch.setattr(actions, 'collect_market_data_for_symbols', lambda **kw: payload)
    actions.run_collect_action(items, 365)
    assert '[005930]' in session.action_message and '[000660]' in session.action_message


@pytest.mark.parametrize('complete', [False, None])
def test_watchlist_requires_explicit_completed_requests(watch, complete):
    service, state, saved, _, _ = watch
    state['fresh'].attrs['price_coverage']['request_complete'] = complete
    with pytest.raises(ValueError):
        watchlist._collect_watchlist_symbol_range(service,'005930',start_date=date(2026,1,1),end_date=date(2026,4,30))
    assert not saved


@pytest.mark.parametrize('rows', [20,70])
@pytest.mark.parametrize('numeric_dates', [False,True])
def test_watchlist_stale_report_checks_stored_history_without_recollection(watch, monkeypatch, rows, numeric_dates):
    _, state, saved, pipeline, refresh = watch
    state['existing'] = frame(rows, metadata=False)
    if numeric_dates:
        state['existing']['stck_bsop_date'] = state['existing']['stck_bsop_date'].astype(float)
    monkeypatch.setattr(watchlist,'_load_latest_dataset_date', lambda service,dataset,symbol,columns: None if dataset=='market_reports' else date(2026,4,30))
    outcome = refresh()
    assert saved == []
    assert outcome['pipeline_symbols'] == (['005930'] if rows>=60 else [])
    assert len(pipeline) == (3 if rows>=60 else 0)


def test_scheduler_old_results_keep_old_finished_shape(tmp_path):
    config = CollectionScheduleConfig(symbols=['005930'],log_path=tmp_path/'legacy.jsonl')
    ScheduledCollectionRunner(config,collector_fn=lambda **kw: dict(success_count=1,failed_count=0,symbols=['005930'])).run_once()
    finished=json.loads(config.log_path.read_text().splitlines()[-1])
    assert 'collection_results' not in finished and 'analysis_ready_symbols' not in finished


def _encoded_saved_days(days, encoding):
    if encoding == 'compact':
        return [day.strftime('%Y%m%d') for day in days]
    if encoding == 'integer':
        return [int(day.strftime('%Y%m%d')) for day in days]
    if encoding == 'float':
        return [float(day.strftime('%Y%m%d')) for day in days]
    if encoding == 'float-string':
        return [day.strftime('%Y%m%d') + '.00' for day in days]
    if encoding == 'iso':
        return [day.isoformat() for day in days]
    return [pd.Timestamp(day).tz_localize('Asia/Seoul') for day in days]


@pytest.mark.parametrize('encoding', ['compact', 'integer', 'float', 'float-string', 'iso', 'local-timezone'])
def test_saved_daily_boundaries_use_local_calendar_dates(encoding):
    from invest_bot.dashboard.data_status import latest_frame_date

    days = [date(2026, 10, 31), date(2026, 11, 2), date(2026, 11, 1)]
    frame = pd.DataFrame({'stck_bsop_date': _encoded_saved_days(days, encoding)}, index=[8, 8, 1])
    frame.attrs['source'] = 'unchanged'
    before = frame.copy(deep=True)
    assert latest_frame_date(frame, ('stck_bsop_date',)) == date(2026, 11, 2)
    assert watchlist._resolve_first_daily_date(frame) == date(2026, 10, 31)
    assert watchlist._resolve_last_daily_date(frame) == date(2026, 11, 2)
    pd.testing.assert_frame_equal(frame, before)
    assert frame.attrs == before.attrs


@pytest.mark.parametrize('bad', [True, None, float('nan'), float('inf'), 1, 20261102.5, '20260230', [20261102], {'date': '20261102'}])
def test_invalid_saved_dates_do_not_become_epoch_days_and_preserve_column_fallback(bad):
    from invest_bot.dashboard.data_status import latest_frame_date

    invalid = pd.DataFrame({'stck_bsop_date': [bad]})
    assert latest_frame_date(invalid, ('stck_bsop_date',)) is None
    assert watchlist._watchlist_history_ready(invalid) is False
    with pytest.raises(ValueError, match='parseable dates'):
        watchlist._resolve_first_daily_date(invalid)
    with pytest.raises(ValueError, match='parseable dates'):
        watchlist._resolve_last_daily_date(invalid)
    frame = pd.DataFrame({'date': [bad], 'trade_date': ['20261101'], 'stck_bsop_date': ['20261102']})
    assert latest_frame_date(frame, ('date', 'trade_date', 'stck_bsop_date')) == date(2026, 11, 1)


@pytest.mark.parametrize('encoding', ['compact', 'integer', 'float', 'float-string', 'iso', 'local-timezone'])
def test_saved_history_readiness_uses_same_calendar_date_rules(encoding):
    days = [day.date() for day in pd.date_range(end='2026-11-02', periods=60)]
    frame = pd.DataFrame({'stck_bsop_date': _encoded_saved_days(days, encoding)})
    assert watchlist._watchlist_history_ready(frame) is True
