import numpy as np
import pandas as pd
import pytest

from invest_bot.jobs.earnings_us_research import (
    align_us_features, earnings_cooldown, event_reactions, factor_statistics,
    factor_window_definitions, gate_entries, normalize_us, validated_earnings,
)


def us(dates, values, series='SP500'):
    return pd.DataFrame({'observation_date': dates, series: values})


def test_us_close_precedes_kr_open_and_changes_dst_correctly():
    frame = us(['2026-03-05', '2026-03-06', '2026-03-09'], [99, 100, 101])
    aligned = align_us_features(['2026-03-09', '2026-03-10'], {'SP500': frame})
    assert aligned.SP500_date.dt.strftime('%Y-%m-%d').tolist() == ['2026-03-06', '2026-03-09']
    assert aligned.SP500_available_at.dt.hour.tolist() == [7, 6]
    assert aligned.SP500_interval_change.iloc[-1] == pytest.approx(1)


def test_korean_holiday_accumulates_us_sessions_and_never_uses_same_day_us_close():
    frame = us(['2026-09-30', '2026-10-01', '2026-10-02', '2026-10-05', '2026-10-06'], [100, 101, 102, 106, 999])
    aligned = align_us_features(['2026-10-01', '2026-10-06'], {'SP500': frame})
    assert aligned.SP500_interval_change.iloc[-1] == pytest.approx(6)
    assert aligned.SP500_daily_change.iloc[-1] == pytest.approx((106/102-1)*100)
    frame.loc[4, 'SP500'] = 1
    pd.testing.assert_frame_equal(aligned, align_us_features(['2026-10-01', '2026-10-06'], {'SP500': frame}))


def test_us_holiday_is_zero_new_interval_without_duplicate_shock_observation():
    frame = us(['2026-05-21', '2026-05-22'], [101, 100])
    aligned = align_us_features(['2026-05-25', '2026-05-26'], {'SP500': frame})
    assert not aligned.SP500_new_close.iloc[-1]
    assert aligned.SP500_interval_change.iloc[-1] == 0
    assert aligned.SP500_level.iloc[-1] == 100


def test_stale_us_and_missing_observation_remain_missing_not_flat():
    frame = us(['2026-10-01', '2026-10-02'], ['.', 100])
    aligned = align_us_features(['2026-10-06', '2026-10-09'], {'SP500': frame})
    assert aligned.SP500_level.iloc[0] == 100
    assert pd.isna(aligned.SP500_level.iloc[1])
    assert pd.isna(aligned.SP500_interval_change.iloc[1])
    with pytest.raises(ValueError, match='duplicate'):
        normalize_us(us(['2026-10-01']*2, [100, 101]), 'SP500')
    with pytest.raises(ValueError, match='malformed'):
        normalize_us(us(['2026-10-01'], ['oops']), 'SP500')


def test_treasury_moves_are_basis_points_and_negative_yields_are_valid():
    frame = us(['2026-03-05', '2026-03-06', '2026-03-09'], [-.1, 0, .25], 'DGS10')
    aligned = align_us_features(['2026-03-09', '2026-03-10'], {'DGS10': frame})
    assert aligned.DGS10_interval_change.iloc[-1] == 25


def test_partial_correlation_removes_shared_domestic_market_component():
    rng = np.random.default_rng(14)
    kr = rng.normal(size=1000)
    x = 2*kr + rng.normal(size=1000)*.1
    y = 3*kr + rng.normal(size=1000)*.1
    stats = factor_statistics(y, x, kr)
    assert stats['correlation'] > .99
    assert abs(stats['partial_correlation']) < .08
    assert stats['n'] == 1000
    assert factor_statistics([1]*20, range(20), range(20))['correlation'] is None
    assert factor_statistics(range(9), range(9), range(9))['correlation'] is None


def test_publication_date_only_is_not_known_before_release_and_weekend_uses_next_session():
    dates = pd.bdate_range('2026-10-05', '2026-10-16')
    event = {'issuer_symbol':'005380', 'date':'2026-10-09'}
    mask = earnings_cooldown(dates, [event], '005380')
    assert dates[mask].strftime('%Y-%m-%d').tolist() == ['2026-10-12','2026-10-13','2026-10-14']
    weekend = earnings_cooldown(dates, [{**event, 'date':'2026-10-10'}], '005380')
    assert np.array_equal(mask, weekend)
    assert not earnings_cooldown(dates, [event], '005930').any()
    assert not earnings_cooldown(dates[:5], [event], '005380').any()
    assert not earnings_cooldown(dates, [{**event,'date':'2026-10-19'}], '005380').any()


def test_gate_preserves_sell_and_hold_and_original_data():
    signal = pd.DataFrame({'signal':['buy','sell','hold','buy']})
    actual = gate_entries(signal, [True,True,True,False])
    assert actual.signal.tolist() == ['hold','sell','hold','buy']
    assert signal.signal.tolist() == ['buy','sell','hold','buy']
    with pytest.raises(ValueError, match='length mismatch'):
        gate_entries(signal, [True])


def test_event_day_is_distinct_from_forward_reaction_and_missing_future_is_null():
    price = pd.DataFrame({'date':pd.bdate_range('2026-10-05',periods=7),'close':[100,110,121,133.1,146.41,161.051,177.1561]})
    etf = price.assign(close=100)
    events = [{'issuer_symbol':'005930','date':'2026-10-06','source_url':'https://example.com/issuer'}]
    row = event_reactions(price, etf, events, '005930')[0]
    assert row['event_day_return_pct'] == pytest.approx(10)
    assert row['post_3_return_pct'] == pytest.approx(33.1)
    assert row['post_5_return_pct'] == pytest.approx(61.051)
    tail = event_reactions(price, etf, [{**events[0],'date':'2026-10-13'}], '005930')[0]
    assert tail['post_5_return_pct'] is None
    assert event_reactions(price, etf, [{**events[0],'date':'2026-10-20'}], '005930') == []


def test_packet_rejects_future_and_deduplicates_verified_publications():
    event = {'date':'2026-10-08','period':'Q3','source_url':'https://example.com/issuer'}
    record = {'issuer_symbol':'005930','release_date':'2026-10-08','event_dates':[event,event]}
    _, events = validated_earnings({'issuers':[record]}, '2026-10-19')
    assert len(events) == 1
    with pytest.raises(ValueError, match='Future'):
        validated_earnings({'issuers':[{**record,'release_date':'2026-10-20'}]}, '2026-10-19')
    with pytest.raises(ValueError, match='HTTPS source'):
        validated_earnings({'issuers':[{**record,'event_dates':[{**event,'source_url':''}]}]}, '2026-10-19')


def test_weekend_release_has_no_calendar_event_day_but_has_first_post_session():
    price = pd.DataFrame({'date':pd.bdate_range('2026-10-08',periods=6),'close':[100,110,121,133.1,146.41,161.051]})
    etf = price.assign(close=100)
    event = {'issuer_symbol':'005930','date':'2026-10-10','source_url':'https://example.com/issuer'}
    row = event_reactions(price, etf, [event], '005930')[0]
    assert row['trading_date'] is None and row['event_day_return_pct'] is None
    assert row['first_post_date'] == '2026-10-12'
    assert row['post_1_return_pct'] == pytest.approx(10)
    assert row['post_3_return_pct'] == pytest.approx(33.1)


def test_gate_applies_to_signal_day_and_does_not_cancel_previously_pending_entry():
    from invest_bot.jobs.rolling_backtest_research import run_signal
    dates = pd.bdate_range('2026-10-05',periods=6)
    source = pd.DataFrame({'date':dates,'close':100.,'signal':['buy','hold','buy','hold','sell','hold'], 'strategy_id':'sample','strategy_name':'sample'})
    blocked = earnings_cooldown(dates, [{'issuer_symbol':'005930','date':'2026-10-05'}], '005930')
    filtered = gate_entries(source, blocked)
    run = run_signal('005930', filtered, .001)
    assert filtered.signal.tolist() == ['buy','hold','hold','hold','sell','hold']
    assert run.trades.iloc[0].entry_date == dates[1]
    assert run.trades.iloc[0].exit_date == dates[5]
    assert filtered.signal.iloc[4] == source.signal.iloc[4]


def test_conflicting_same_day_earnings_releases_fail_without_last_wins():
    record = {'issuer_symbol':'005930','release_date':'2026-10-08', 'event_dates':[
        {'date':'2026-10-08','period':'Q3','source_url':'https://example.com/a'},
        {'date':'2026-10-08','period':'Q2','source_url':'https://example.com/b'},
    ]}
    with pytest.raises(ValueError,match='Conflicting'):
        validated_earnings({'issuers':[record]}, '2026-10-19')


def test_factor_common_history_uses_validated_legacy_eligible_rows():
    dates=pd.bdate_range('2024-01-02',periods=501)
    start=str(dates[59].date());end=str(dates[-1].date())
    legacy={'metadata':{'eligible_start':start,'eligible_rows':442,'as_of':end},'windows':[
        {'id':'full','kind':'full','end_date':end},
        {'id':'roll-240','kind':'rolling','end_date':end},
        {'id':'old','kind':'rolling','end_date':str(dates[-2].date())},
    ]}
    windows=factor_window_definitions(legacy,dates)
    assert windows[0]=={'id':'common-history','length':442,'start_date':start,'end_date':end}
    assert [row['id'] for row in windows]==['common-history','roll-240']
    legacy['metadata']['eligible_rows']=441
    with pytest.raises(ValueError,match='eligible row count'):
        factor_window_definitions(legacy,dates)
