from datetime import date

import pandas as pd
import pytest

from invest_bot.jobs.backfill_history import HistoryCollectionError, HistoryFetcher, HistoryResult, backfill_symbol, verify_first_window


def row(day, close='100'):
    return dict(stck_bsop_date=day, stck_clpr=close, stck_oprc=close, stck_hgpr=close, stck_lwpr=close, acml_vol='10', frgn_ntby_qty='2', orgn_ntby_qty='-1', prsn_ntby_qty='-1')


class Client:
    def __init__(self, pages):
        self.pages = iter(pages)
        self.calls = []

    def get_json(self, path, tr_id, params):
        self.calls.append((path, tr_id, params))
        return {'rt_cd': '0', 'output1': {}, 'output2': next(self.pages)}


@pytest.mark.parametrize('kind', ['price', 'investor'])
def test_history_moves_to_oldest_date_minus_one_and_filters_window(kind):
    c = Client([[row('20260109'), row('20260108')], [row('20260106'), row('20260107'), row('20260102')]])
    result = HistoryFetcher(c, interval=0).collect(kind, '005930', date(2026, 1, 5), date(2026, 1, 9))
    assert result.frame.stck_bsop_date.tolist() == ['20260106', '20260107', '20260108', '20260109']
    key = 'FID_INPUT_DATE_2' if kind == 'price' else 'FID_INPUT_DATE_1'
    assert c.calls[1][2][key] == '20260107'
    assert result.pages == 2 and result.termination == 'start_reached'
    if kind == 'investor':
        assert c.calls[0][2]['FID_ORG_ADJ_PRC'] == ''


def test_identical_duplicate_is_removed():
    c = Client([[row('20260109'), row('20260109')]])
    result = HistoryFetcher(c, interval=0).collect('price', '005930', date(2026, 1, 9), date(2026, 1, 9))
    assert len(result.frame) == 1


def test_conflicting_duplicate_is_rejected():
    c = Client([[row('20260109'), row('20260109', '101')]])
    with pytest.raises(HistoryCollectionError, match='Conflicting'):
        HistoryFetcher(c, interval=0).collect('price', '005930', date(2026, 1, 9), date(2026, 1, 9))


def test_repeated_page_is_rejected_instead_of_looping():
    c = Client([[row('20260109')], [row('20260109')]])
    with pytest.raises(HistoryCollectionError, match='no progress'):
        HistoryFetcher(c, interval=0).collect('price', '005930', date(2026, 1, 1), date(2026, 1, 9))
    assert len(c.calls) == 2


def test_empty_tail_is_recorded_without_inventing_trading_days():
    c = Client([[row('20260109')], []])
    result = HistoryFetcher(c, interval=0).collect('price', '005930', date(2026, 1, 1), date(2026, 1, 9))
    assert result.termination == 'empty_page' and len(result.frame) == 1


def test_empty_first_page_fails():
    with pytest.raises(HistoryCollectionError, match='No observations'):
        HistoryFetcher(Client([[]]), interval=0).collect('price', '005930', date(2026, 1, 1), date(2026, 1, 9))


@pytest.mark.parametrize('bad', ['invalid', '20260230'])
def test_invalid_dates_fail(bad):
    with pytest.raises(HistoryCollectionError, match='Invalid observation'):
        HistoryFetcher(Client([[row(bad)]]), interval=0).collect('price', '005930', date(2026, 1, 1), date(2026, 1, 9))


def test_page_limit_does_not_return_partial_success():
    with pytest.raises(HistoryCollectionError, match='Maximum'):
        HistoryFetcher(Client([[row('20260109')]]), interval=0, max_pages=1).collect('price', '005930', date(2026, 1, 1), date(2026, 1, 9))


def test_api_error_is_not_treated_as_empty_success(monkeypatch):
    class ErrorClient:
        def get_json(self, *args):
            return {'rt_cd': '1', 'msg_cd': 'TEST_ERROR', 'output2': []}
    monkeypatch.setattr('invest_bot.jobs.backfill_history.time.sleep', lambda _: None)
    with pytest.raises(HistoryCollectionError, match='TEST_ERROR'):
        HistoryFetcher(ErrorClient(), interval=0).collect('price', '005930', date(2026, 1, 1), date(2026, 1, 9))


def test_invalid_window_and_kind_fail_before_api():
    c = Client([])
    with pytest.raises(ValueError):
        HistoryFetcher(c).collect('price', '005930', date(2026, 1, 9), date(2026, 1, 1))
    with pytest.raises(ValueError):
        HistoryFetcher(c).collect('other', '005930', date(2026, 1, 1), date(2026, 1, 9))
    assert c.calls == []


@pytest.mark.parametrize('bad', ['0', 'not-a-number'])
def test_invalid_prices_fail_before_persistence(bad):
    with pytest.raises(HistoryCollectionError):
        HistoryFetcher(Client([[row('20260109', bad)]]), interval=0).collect('price', '005930', date(2026, 1, 9), date(2026, 1, 9))


def test_backfill_preserves_old_snapshot_names_and_exposes_missing_flow():
    class Fetcher:
        def collect(self, kind, *_):
            days = ['20200106', '20200108'] if kind == 'price' else ['20200106']
            return HistoryResult(pd.DataFrame([row(d) for d in days]), pd.DataFrame([{'latest': True}]), 1, 'start_reached')
    class Storage:
        def __init__(self): self.saved = []
        def save(self, dataset, filename, frame): self.saved.append((dataset, filename, len(frame)))
    storage = Storage()
    result = backfill_symbol('005930', date(2020, 1, 6), date(2020, 1, 8), Fetcher(), storage)
    assert len(storage.saved) == 4
    assert all(name.endswith('_history.csv') for _,name,_ in storage.saved)
    assert result['missing_investor_dates'] == ['20200108']
    assert result['price_rows'] == 2 and result['investor_rows'] == 1


def test_investor_failure_prevents_partial_snapshots():
    class Fetcher:
        def collect(self, kind, *_):
            if kind == 'investor': raise HistoryCollectionError('unavailable')
            return HistoryResult(pd.DataFrame([row('20200106')]), pd.DataFrame(), 1, 'start_reached')
    class Storage:
        def save(self, *_): raise AssertionError('must not save')
    with pytest.raises(HistoryCollectionError, match='unavailable'):
        backfill_symbol('005930', date(2020, 1, 6), date(2020, 1, 8), Fetcher(), Storage())


def test_truncated_long_history_is_rejected_by_independent_first_window():
    class Fetcher:
        def collect(self, *_):
            return HistoryResult(pd.DataFrame([row('20240102')]), pd.DataFrame(), 1, 'start_reached')
    incomplete = HistoryResult(pd.DataFrame([row('20260109')]), pd.DataFrame(), 2, 'empty_page')
    with pytest.raises(HistoryCollectionError, match='beginning missing'):
        verify_first_window(Fetcher(), 'price', '005930', date(2024, 1, 1), date(2026, 1, 9), incomplete)


def test_empty_initial_window_does_not_claim_two_year_coverage():
    class Fetcher:
        def collect(self, *_): raise HistoryCollectionError('No observations')
    incomplete = HistoryResult(pd.DataFrame([row('20260109')]), pd.DataFrame(), 2, 'empty_page')
    with pytest.raises(HistoryCollectionError, match='No observations'):
        verify_first_window(Fetcher(), 'price', '005930', date(2024, 1, 1), date(2026, 1, 9), incomplete)


def test_first_window_dates_must_all_be_in_history():
    class Fetcher:
        def collect(self, *_):
            return HistoryResult(pd.DataFrame([row('20240102'),row('20240103')]), pd.DataFrame(), 1, 'start_reached')
    incomplete = HistoryResult(pd.DataFrame([row('20240102'),row('20260109')]), pd.DataFrame(), 2, 'empty_page')
    with pytest.raises(HistoryCollectionError, match='beginning missing'):
        verify_first_window(Fetcher(), 'price', '005930', date(2024, 1, 1), date(2026, 1, 9), incomplete)


@pytest.mark.parametrize('bad', ['inf', '-inf', 'NaN', 'nan'])
def test_nonfinite_price_values_are_rejected(bad):
    with pytest.raises(HistoryCollectionError):
        HistoryFetcher(Client([[row('20260109', bad)]]), interval=0).collect('price', '005930', date(2026, 1, 9), date(2026, 1, 9))


def test_negative_volume_is_rejected():
    value=row('20260109'); value['acml_vol']='-1'
    with pytest.raises(HistoryCollectionError):
        HistoryFetcher(Client([[value]]), interval=0).collect('price', '005930', date(2026, 1, 9), date(2026, 1, 9))


def test_active_price_must_be_inside_high_low():
    value=row('20260109'); value['stck_hgpr']='99'
    with pytest.raises(HistoryCollectionError, match='OHLC'):
        HistoryFetcher(Client([[value]]), interval=0).collect('price', '005930', date(2026, 1, 9), date(2026, 1, 9))


def test_zero_ohl_with_zero_volume_can_represent_a_trading_halt():
    value=row('20260109'); value.update(stck_oprc='0',stck_hgpr='0',stck_lwpr='0',acml_vol='0')
    result=HistoryFetcher(Client([[value]]), interval=0).collect('price', '005930', date(2026, 1, 9), date(2026, 1, 9))
    assert len(result.frame)==1
