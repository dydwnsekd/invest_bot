from datetime import date
from dataclasses import asdict
import json

import pandas as pd
import pytest

from invest_bot.clients.kis_client import KISClient
from invest_bot.config.settings import AppSettings
from invest_bot.market.collector import MarketDataCollector
from invest_bot.market.storage import CsvStorage
from invest_bot.market.domestic_stock import DailyPriceRequest, DomesticStockDataCollector
from invest_bot.market.price_history import DailyPriceHistoryFetcher, PriceHistoryError, assess_price_coverage, listing_date_evidence
from invest_bot.jobs.collect_market_data import collect_market_data_for_symbols
from invest_bot.market.collector import BatchCollectionResult
from invest_bot.db.frame_storage import DbFrameStorage
from invest_bot.db.write_path import SqlAlchemyMarketDataWriter
from tests.helpers import init_test_db


def price_row(day, close='100'):
    return dict(stck_bsop_date=day, stck_oprc=close, stck_hgpr=close,
                stck_lwpr=close, stck_clpr=close, acml_vol='10')


def test_regular_facade_fetches_full_requested_history_before_saving(tmp_path, monkeypatch):
    calls = []
    start, end = date(2025, 1, 1), date(2026, 1, 1)

    def get_json(self, api_path, tr_id, params, **kwargs):
        assert api_path.endswith('inquire-daily-itemchartprice')
        calls.append(params)
        days = pd.date_range(params['FID_INPUT_DATE_1'], params['FID_INPUT_DATE_2'])
        return {'rt_cd': '0', 'output1': {'symbol': '005930'},
                'output2': [price_row(d.strftime('%Y%m%d')) for d in days[-100:][::-1]]}

    monkeypatch.setattr(KISClient, 'get_json', get_json)
    # Fake pacing only: no real sleep, even after regular history is connected.
    monkeypatch.setattr('time.sleep', lambda _: None)
    collector = MarketDataCollector(AppSettings(), storage=CsvStorage(tmp_path))
    summary, prices = collector.collect_daily_prices('005930', start, end)

    assert len(prices) == 366
    assert len(calls) == 4
    assert prices.stck_bsop_date.iloc[0] == '20250101'
    assert prices.stck_bsop_date.iloc[-1] == '20260101'
    assert prices.attrs['price_coverage']['status'] == 'complete'


class Clock:
    def __init__(self):
        self.now = 0
        self.sleeps = []

    def sleep(self, seconds):
        self.sleeps.append(seconds)
        self.now += seconds


class Pages:
    def __init__(self, pages):
        self.pages = iter(pages)
        self.calls = []

    def get_json(self, path, tr_id, params):
        self.calls.append((path, tr_id, params))
        value = next(self.pages)
        if isinstance(value, Exception):
            raise value
        return value if isinstance(value, dict) else {'rt_cd': '0', 'output1': {'page': len(self.calls)}, 'output2': value}


def fetcher(pages, **kwargs):
    client, clock = Pages(pages), Clock()
    return DailyPriceHistoryFetcher(client, clock=lambda: clock.now, sleep=clock.sleep, **kwargs), client, clock


def request(start='2026-01-01', end='2026-01-02', **kwargs):
    return DailyPriceRequest('005930', date.fromisoformat(start), date.fromisoformat(end), **kwargs)


def test_windows_are_disjoint_bounded_paced_and_preserve_request_parameters():
    h, client, clock = fetcher([
        [price_row('20260415'), price_row('20260106')],
        [price_row('20260105'), price_row('20260101')],
    ])
    summary, prices = h.collect(request(end='2026-04-15', market_code='NX', adjusted_price=False))
    assert len(client.calls) == 2
    first, second = [c[2] for c in client.calls]
    assert (first['FID_INPUT_DATE_1'], first['FID_INPUT_DATE_2']) == ('20260106', '20260415')
    assert (second['FID_INPUT_DATE_1'], second['FID_INPUT_DATE_2']) == ('20260101', '20260105')
    assert all(p['FID_COND_MRKT_DIV_CODE'] == 'NX' and p['FID_PERIOD_DIV_CODE'] == 'D' and p['FID_ORG_ADJ_PRC'] == '1' for p in (first, second))
    assert clock.sleeps == [1.1]
    assert prices.stck_bsop_date.tolist() == ['20260101', '20260105', '20260106', '20260415']
    assert summary.iloc[0]['page'] == 1
    assert prices.attrs['price_coverage']['requests'] == 2


def test_identical_duplicates_reverse_order_and_halt_are_preserved_without_input_mutation():
    halted = price_row('20260101'); halted.update(stck_oprc='0', stck_hgpr='0', stck_lwpr='0', acml_vol='0')
    rows = [price_row('20260102'), halted, price_row('20260102')]
    h, _, _ = fetcher([rows])
    _, prices = h.collect(request())
    assert prices.stck_bsop_date.tolist() == ['20260101', '20260102']
    assert len(rows) == 3
    assert prices.attrs['price_coverage']['status'] == 'complete'


@pytest.mark.parametrize('bad', [
    dict(stck_bsop_date='bad-date'), dict(stck_bsop_date='20260230'), dict(stck_bsop_date='2026011'),
    dict(stck_bsop_date=''), dict(stck_bsop_date=None), dict(stck_bsop_date='20260103'),
    dict(stck_bsop_date='20251231'), dict(stck_clpr='NaN'), dict(stck_clpr='inf'),
    dict(stck_clpr='0'), dict(stck_clpr='bad-secret-value'), dict(stck_oprc=True),
    dict(stck_clpr=['secret']), dict(acml_vol='-1'), dict(acml_vol='1.5'), dict(stck_hgpr='99'),
])
def test_bad_dates_values_or_out_of_range_are_rejected_without_raw_diagnostics(bad):
    row = price_row('20260101'); row.update(bad)
    h, client, _ = fetcher([[row]])
    with pytest.raises(PriceHistoryError) as caught:
        h.collect(request())
    assert len(client.calls) == 1
    assert caught.value.coverage['status'] == 'incomplete'
    assert 'secret' not in str(caught.value)
    json.dumps(caught.value.coverage, allow_nan=False)


@pytest.mark.parametrize('page', [
    {'rt_cd': '1', 'msg1': 'sensitive secret', 'output2': []},
    {'output2': []}, {'rt_cd': '0'}, {'rt_cd': '0', 'output2': 'secret'},
    {'rt_cd': '0', 'output2': [None]}, {'rt_cd': '0', 'output1': ['secret'], 'output2': []},
    RuntimeError('token=secret DATABASE_URL=secret'),
])
def test_malformed_error_payload_or_exception_has_no_retries_or_sensitive_diagnostics(page):
    h, client, clock = fetcher([page])
    with pytest.raises(PriceHistoryError) as caught:
        h.collect(request())
    assert len(client.calls) == 1 and clock.sleeps == []
    assert 'secret' not in str(caught.value)
    assert 'secret' not in json.dumps(caught.value.coverage)


def test_conflicting_duplicate_and_saturated_duplicates_are_not_silent_success():
    for rows in [[price_row('20260101'), price_row('20260101', '101')], [price_row('20260101')] * 100]:
        h, _, _ = fetcher([rows])
        with pytest.raises(PriceHistoryError):
            h.collect(request())


def test_page_limit_and_invalid_range_fail_before_requests():
    h, client, _ = fetcher([], max_pages=1)
    with pytest.raises(PriceHistoryError, match='page_limit'):
        h.collect(request(end='2027-01-01'))
    with pytest.raises(PriceHistoryError, match='invalid_range'):
        h.collect(request(start='2026-01-03'))
    assert client.calls == []


@pytest.mark.parametrize('kwargs', [dict(max_pages=0), dict(max_pages=True), dict(max_pages=1.5), dict(interval=-1), dict(interval=float('inf')), dict(interval=float('nan'))])
def test_invalid_request_controls_fail_without_api(kwargs):
    with pytest.raises(ValueError):
        fetcher([], **kwargs)


def test_empty_windows_continue_without_repeating_queries_but_do_not_prove_listing_or_holidays():
    h, client, _ = fetcher([[], []])
    _, prices = h.collect(request(end='2026-04-15'))
    assert len(client.calls) == 2
    assert prices.empty
    assert prices.attrs['price_coverage']['status'] == 'unknown'
    assert prices.attrs['price_coverage']['requests'] == 2


def test_repeated_previous_window_page_is_rejected_as_no_progress():
    h, client, _ = fetcher([[price_row('20260415')], [price_row('20260415')]])
    with pytest.raises(PriceHistoryError, match='no_progress'):
        h.collect(request(end='2026-04-15'))
    assert len(client.calls) == 2


@pytest.mark.parametrize(('days', 'expected', 'status', 'reason'), [
    ([], None, 'unknown', 'no_observations_without_calendar'),
    (['20260102'], None, 'complete', 'bounded_windows_exhausted'),
    (['20260101'], None, 'complete', 'bounded_windows_exhausted'),
    ([], [], 'complete', 'calendar_no_sessions'),
    (['20260102'], [date(2026, 1, 2)], 'complete', 'calendar_observations_match'),
    (['20260102'], [date(2026, 1, 1), date(2026, 1, 2)], 'incomplete', 'calendar_observation_mismatch'),
    (['20260102'], [date(2026, 1, 3)], 'unknown', 'invalid_calendar_evidence'),
])
def test_coverage_uses_evidence_not_weekend_counts(days, expected, status, reason):
    frame = pd.DataFrame([price_row(d) for d in days])
    coverage = assess_price_coverage(frame, date(2026, 1, 1), date(2026, 1, 2), expected_dates=expected, request_complete=True)
    assert (coverage['status'], coverage['reason']) == (status, reason)


@pytest.mark.parametrize(('listing', 'days', 'status'), [
    (date(2026, 1, 2), ['20260102', '20260103'], 'complete'),
    (date(2026, 1, 2), ['20260103'], 'complete'),
    (date(2026, 1, 2), ['20260101', '20260103'], 'incomplete'),
    (date(2099, 1, 2), ['20260102', '20260103'], 'complete'),
    (date(2026, 1, 4), [], 'unknown'),
])
def test_listing_must_explain_observed_start_and_not_be_future_or_contradict_data(listing, days, status):
    c = assess_price_coverage(pd.DataFrame([price_row(d) for d in days]), date(2026, 1, 1), date(2026, 1, 3), listing_date=listing, request_complete=True)
    assert c['status'] == status


@pytest.mark.parametrize(('info', 'expected'), [
    ({'pdno': '005930', 'scts_mket_lstg_dt': '20260102'}, date(2026, 1, 2)),
    ({'pdno': '005930', 'kosdaq_mket_lstg_dt': '20260102', 'scts_mket_lstg_dt': '00000000'}, date(2026, 1, 2)),
    ({'pdno': '000660', 'scts_mket_lstg_dt': '20260102'}, None),
    ({'pdno': '005930', 'scts_mket_lstg_dt': '20260230'}, None),
    ({'pdno': '005930', 'scts_mket_lstg_dt': '20260102', 'kosdaq_mket_lstg_dt': '20260101'}, None),
])
def test_listing_evidence_requires_identity_validity_and_no_exchange_ambiguity(info, expected):
    actual, _ = listing_date_evidence(pd.DataFrame([info]), '005930')
    assert actual == expected


def bundle_collector(tmp_path, monkeypatch, pages, *, info=None, **fetcher_kwargs):
    h, client, clock = fetcher(pages, **fetcher_kwargs)
    collector = MarketDataCollector(AppSettings(), storage=CsvStorage(tmp_path))
    collector.collector = DomesticStockDataCollector(client, price_history=h)
    later = []

    def stock_info(symbol):
        later.append('stock_info')
        return pd.DataFrame([info or {'pdno': symbol, 'prdt_abrv_name': 'example'}])

    def investors(symbol, end):
        later.append('investor')
        return pd.DataFrame([{'price': '100'}]), pd.DataFrame([{'stck_bsop_date': end.strftime('%Y%m%d'), 'frgn_ntby_qty': '1'}])

    monkeypatch.setattr(collector, 'collect_stock_info', stock_info)
    monkeypatch.setattr(collector, 'collect_investor_daily', investors)
    return collector, later, client


def test_complete_short_history_is_saved_without_marking_analysis_ready(tmp_path, monkeypatch):
    collector, later, _ = bundle_collector(tmp_path, monkeypatch, [[price_row('20260101'), price_row('20260102')]])
    result = collector.collect_symbol_bundle('005930', date(2026, 1, 1), date(2026, 1, 2))
    assert result.status == 'success' and result.analysis_ready is False
    assert result.daily_price_rows == 2 and len(result.saved_files) == 5
    assert later == ['stock_info', 'investor']
    json.dumps(asdict(result), allow_nan=False)


def test_known_new_listing_can_preserve_short_valid_history(tmp_path, monkeypatch):
    info = {'pdno': '005930', 'prdt_abrv_name': 'new', 'scts_mket_lstg_dt': '20260102'}
    collector, _, _ = bundle_collector(tmp_path, monkeypatch, [[price_row('20260102'), price_row('20260103')]], info=info)
    result = collector.collect_symbol_bundle('005930', date(2026, 1, 1), date(2026, 1, 3))
    assert result.status == 'success' and result.analysis_ready is False
    assert result.price_coverage['range_reason'] == 'verified_listing_date'


def test_unexplained_short_range_is_saved_with_uncertainty_and_analysis_unready(tmp_path, monkeypatch):
    collector, later, _ = bundle_collector(tmp_path, monkeypatch, [[price_row('20260102')]])
    result = collector.collect_symbol_bundle('005930', date(2026, 1, 1), date(2026, 1, 2))
    assert result.status == 'success' and result.price_coverage['status'] == 'complete'
    assert result.price_coverage['range_reason'] == 'unverified_start_boundary'
    assert not result.price_coverage['trading_days_verified'] and result.analysis_ready is False
    assert len(result.saved_files) == 5 and later == ['stock_info', 'investor']


def test_second_page_failure_returns_diagnostics_without_partial_saves_or_later_calls(tmp_path, monkeypatch):
    collector, later, _ = bundle_collector(tmp_path, monkeypatch, [[price_row('20260415')], RuntimeError('secret')])
    result = collector.collect_symbol_bundle('005930', date(2026, 1, 1), date(2026, 4, 15))
    assert result.status == 'failed' and result.saved_files == []
    assert result.daily_price_rows == 1 and result.price_coverage['requests'] == 2
    assert later == [] and not list(tmp_path.rglob('*.csv'))
    assert 'secret' not in json.dumps(asdict(result))


def test_closed_calendar_interval_is_complete_but_never_analysis_ready_or_saved(tmp_path, monkeypatch):
    collector, later, _ = bundle_collector(tmp_path, monkeypatch, [[]], calendar=lambda start, end: [])
    result = collector.collect_symbol_bundle('005930', date(2026, 1, 1), date(2026, 1, 2))
    assert result.status == 'success' and result.analysis_ready is False
    assert result.saved_files == [] and later == ['stock_info']


def test_batch_job_preserves_collection_success_and_adds_analysis_gates_for_legacy_results():
    def result(symbol, *, ready=None, coverage=None):
        return BatchCollectionResult(symbol, 'success', 1, 2, 1, 1, 1, ['saved'],
                                     analysis_ready=ready, price_coverage=coverage or {})

    class Collector:
        def collect_symbols_batch(self, **kwargs):
            return [result('005930', ready=False, coverage={'status': 'complete'}), result('000660')]

    summary = collect_market_data_for_symbols(['005930', '000660'], settings=AppSettings(), collector=Collector())
    assert summary['successful_symbols'] == ['005930', '000660']
    assert summary['analysis_ready_symbols'] == ['000660']
    assert summary['analysis_unready_symbols'] == ['005930']
    assert summary['coverage_complete_symbols'] == ['005930']
    json.dumps(summary, allow_nan=False)


@pytest.mark.parametrize(('readiness', 'ready'), [
    (True, True), (False, False), (None, True), ('false', False), (0, False),
    (1, False), ('true', False), ([], False), ({}, False),
])
def test_job_analysis_readiness_accepts_only_bool_or_legacy_none(readiness, ready):
    class Collector:
        def collect_symbols_batch(self, **kwargs):
            return [BatchCollectionResult('005930', 'success', 1, 2, 1, 1, 1, ['saved'], analysis_ready=readiness)]

    summary = collect_market_data_for_symbols(['005930'], settings=AppSettings(), collector=Collector())
    assert summary['analysis_ready_symbols'] == (['005930'] if ready else [])
    assert summary['analysis_unready_symbols'] == ([] if ready else ['005930'])
    assert summary['analysis_ready_count'] == int(ready)
    assert summary['analysis_unready_count'] == int(not ready)


@pytest.mark.parametrize(('start', 'end', 'first', 'last', 'reason'), [
    (date(2025, 1, 5), date(2026, 1, 5), '2025-01-06', '2026-01-05', 'unverified_start_boundary'),
    (date(2025, 1, 10), date(2026, 1, 10), '2025-01-10', '2026-01-09', 'unverified_end_boundary'),
])
def test_completed_365_day_request_with_weekend_boundaries_is_saved(tmp_path, monkeypatch, start, end, first, last, reason):
    calls = []
    clock = Clock()

    class Weekdays:
        def get_json(self, path, tr_id, params):
            calls.append(params)
            days = pd.bdate_range(params['FID_INPUT_DATE_1'], params['FID_INPUT_DATE_2'])
            return {'rt_cd': '0', 'output1': {}, 'output2': [price_row(d.strftime('%Y%m%d')) for d in days]}

    h = DailyPriceHistoryFetcher(Weekdays(), clock=lambda: clock.now, sleep=clock.sleep)
    collector = MarketDataCollector(AppSettings(), storage=CsvStorage(tmp_path))
    collector.collector = DomesticStockDataCollector(h.client, price_history=h)
    monkeypatch.setattr(collector, 'collect_stock_info', lambda symbol: pd.DataFrame())
    monkeypatch.setattr(collector, 'collect_investor_daily', lambda *args: (pd.DataFrame(), pd.DataFrame()))
    result = collector.collect_symbol_bundle('005930', start, end)
    assert result.status == 'success' and result.analysis_ready is True
    assert result.price_coverage['observed_start'] == first
    assert result.price_coverage['observed_end'] == last
    assert result.price_coverage['request_complete'] is True
    assert result.price_coverage['trading_days_verified'] is False
    assert result.price_coverage['range_reason'] == reason
    assert len(calls) == 4 and len(result.saved_files) == 4

    result = collector.collect_symbol_bundle('005930', date(2026, 1, 3), date(2026, 1, 11))
    assert result.status == 'success' and result.analysis_ready is False
    assert result.price_coverage['observed_start'] == '2026-01-05'
    assert result.price_coverage['observed_end'] == '2026-01-09'


@pytest.mark.parametrize('pages', [
    [[], [price_row('20260701')], [], [price_row('20260101')]],
    [[price_row('20261102')], [], [], []],
    [[], [], [], [price_row('20260101')]],
])
def test_empty_internal_front_or_tail_windows_do_not_invalidate_completed_nonempty_results(pages):
    h, client, _ = fetcher(pages)
    _, prices = h.collect(request(end='2026-11-02'))
    assert len(client.calls) == 4
    assert prices.attrs['price_coverage']['status'] == 'complete'
    assert prices.attrs['price_coverage']['request_complete'] is True
    assert prices.attrs['price_coverage']['trading_days_verified'] is False


def test_calendar_proven_missing_session_remains_failure_even_with_listing_metadata(tmp_path, monkeypatch):
    info = {'pdno': '005930', 'prdt_abrv_name': 'new', 'scts_mket_lstg_dt': '20260102'}
    collector, later, _ = bundle_collector(tmp_path, monkeypatch, [[price_row('20260102')]], info=info,
                                          calendar=lambda *args: [date(2026, 1, 1), date(2026, 1, 2)])
    result = collector.collect_symbol_bundle('005930', date(2026, 1, 1), date(2026, 1, 2))
    assert result.status == 'failed' and result.saved_files == []
    assert result.price_coverage['reason'] == 'calendar_observation_mismatch'
    assert later == ['stock_info']


def test_observations_alone_cannot_claim_unperformed_requests_are_complete():
    c = assess_price_coverage(pd.DataFrame([price_row('20260101'), price_row('20260102')]),
                              date(2026, 1, 1), date(2026, 1, 2))
    assert c['status'] == 'unknown' and c['request_complete'] is False


def test_invalid_listing_cannot_override_calendar_proven_missing_observation():
    c = assess_price_coverage(pd.DataFrame([price_row('20260102')]), date(2026, 1, 1), date(2026, 1, 2),
                             request_complete=True, listing_date=date(2099, 1, 1),
                             expected_dates=[date(2026, 1, 1), date(2026, 1, 2)])
    assert c['status'] == 'incomplete' and c['reason'] == 'calendar_observation_mismatch'


@pytest.mark.parametrize('page', [[], [price_row('20260101')] * 101, [{'stck_clpr': '100'}]])
def test_nonempty_payload_shape_cap_and_missing_date_are_checked(page):
    h, client, _ = fetcher([page])
    if not page:
        _, prices = h.collect(request())
        assert prices.attrs['price_coverage']['status'] == 'unknown'
    else:
        with pytest.raises(PriceHistoryError):
            h.collect(request())
    assert len(client.calls) == 1


def test_regular_history_repeat_preserves_all_prices_flow_rows_and_snapshots_in_sqlite(tmp_path, monkeypatch):
    url = f"sqlite:///{tmp_path / 'history.sqlite'}"
    init_test_db(url)
    storage = DbFrameStorage(url)
    writer = SqlAlchemyMarketDataWriter(url)
    clock = Clock()

    class CalendarRows:
        def get_json(self, path, tr_id, params):
            days = pd.date_range(params['FID_INPUT_DATE_1'], params['FID_INPUT_DATE_2'])
            return {'rt_cd': '0', 'output1': {}, 'output2': [price_row(d.strftime('%Y%m%d')) for d in days[::-1]]}

    h = DailyPriceHistoryFetcher(CalendarRows(), clock=lambda: clock.now, sleep=clock.sleep)
    collector = MarketDataCollector(AppSettings(), storage=storage, db_writer=writer)
    collector.collector = DomesticStockDataCollector(h.client, price_history=h)
    monkeypatch.setattr(collector, 'collect_stock_info', lambda symbol: pd.DataFrame([{'pdno': symbol, 'prdt_abrv_name': 'example'}]))
    monkeypatch.setattr(collector, 'collect_investor_daily', lambda *args: (
        pd.DataFrame([{'stck_clpr': '100'}]),
        pd.DataFrame([{'stck_bsop_date': '20260101', 'frgn_ntby_qty': '1'}, {'stck_bsop_date': '20251231', 'frgn_ntby_qty': '2'}]),
    ))
    for _ in range(2):
        result = collector.collect_symbol_bundle('005930', date(2025, 1, 1), date(2026, 1, 1))
        assert result.status == 'success' and result.analysis_ready is True
        assert result.daily_price_rows == 366 and len(result.saved_files) == 5
    assert len(writer.daily_price_repository.list_for_symbol('005930')) == 366
    assert len(writer.investor_daily_repository.list_for_symbol('005930')) == 2
    assert len(storage.load('daily_prices', '005930_20250101_20260101.csv')) == 366
    assert storage.repository.latest_for_symbol('daily_prices', '005930').as_of_date == date(2026, 1, 1)


def test_later_symbol_failure_preserves_earlier_success_and_its_coverage(tmp_path, monkeypatch):
    collector, later, _ = bundle_collector(tmp_path, monkeypatch, [
        [price_row('20260101'), price_row('20260102')], RuntimeError('secret'),
    ])
    results = collector.collect_symbols_batch(['005930', '000660'], date(2026, 1, 1), date(2026, 1, 2))
    assert [r.status for r in results] == ['success', 'failed']
    assert len(results[0].saved_files) == 5 and results[1].saved_files == []
    assert results[0].price_coverage['requests'] == 1 and results[1].price_coverage['requests'] == 1
    assert later == ['stock_info', 'investor']


@pytest.mark.parametrize('kind', ['csv', 'sqlite'])
@pytest.mark.parametrize(('calendar_days', 'listing', 'status'), [
    ([date(2026, 1, 3)], '20260102', 'unknown'),
    ([date(2026, 1, 3)], 'bad-listing', 'unknown'),
    ([date(2026, 1, 1), date(2026, 1, 2)], '20260102', 'incomplete'),
    ([date(2026, 1, 2)], 'bad-listing', 'complete'),
])
def test_listing_preserves_original_calendar_diagnostics_and_storage_gate(tmp_path, monkeypatch, kind, calendar_days, listing, status):
    from invest_bot.jobs import collect_market_data as job

    collector, later, _ = bundle_collector(tmp_path, monkeypatch, [[price_row('20260102')]],
        info={'pdno': '005930', 'prdt_abrv_name': 'example', 'scts_mket_lstg_dt': listing},
        calendar=lambda *args: calendar_days)
    if kind == 'sqlite':
        url = f"sqlite:///{tmp_path / 'calendar-gate.sqlite'}"
        init_test_db(url)
        collector.storage = DbFrameStorage(url)
    captured = {}
    original_collect = collector.collect_daily_prices

    def capture(*args):
        summary, prices = original_collect(*args)
        captured.update(prices.attrs['price_coverage'])
        return summary, prices

    class FrozenDate(date):
        @classmethod
        def today(cls):
            return date(2026, 1, 2)

    monkeypatch.setattr(collector, 'collect_daily_prices', capture)
    monkeypatch.setattr(job, 'date', FrozenDate)
    summary = job.collect_market_data_for_symbols(['005930'], days=1, settings=collector.settings, collector=collector)
    result = summary['results'][0]
    assert captured['status'] == status
    assert result['price_coverage'] == captured
    assert summary['analysis_ready_symbols'] == []
    if status != 'complete':
        assert summary['success_count'] == 0 and result['analysis_ready'] is False
        assert result['saved_files'] == [] and later == ['stock_info']
        for dataset in ('daily_prices_summary', 'daily_prices', 'stock_info', 'investor_daily', 'investor_daily_summary'):
            assert collector.storage.latest_filename(dataset, '005930') is None
    else:
        assert summary['success_count'] == 1 and summary['analysis_unready_symbols'] == ['005930']
        assert len(result['saved_files']) == 5 and later == ['stock_info', 'investor']
