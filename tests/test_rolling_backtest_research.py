import itertools

import numpy as np
import pandas as pd
import pytest

from invest_bot.jobs.rolling_backtest_research import (
    Run, apply_costs, benchmark_curves, build_signal_models, candidate_models,
    capital_mix, merge_investor_history, rolling_windows, run_signal, select_model,
    signal_mix, walk_blocks,
)
from invest_bot.jobs.rolling_backtest_research import main, REPORT_SYMBOLS
from invest_bot.market.analysis import DailyPriceAnalyzer


def signals(values, prices=None):
    return pd.DataFrame({'date':pd.date_range('2026-01-01',periods=len(values)),'close':prices or [100.0]*len(values),'signal':values,'strategy_id':'sample','strategy_name':'sample'})


def test_windows_are_exact_length_latest_anchored_and_counted():
    dates=pd.bdate_range('2025-01-08',periods=427)
    windows=rolling_windows(dates)
    assert len(windows)==66
    for length,count in [(20,21),(60,19),(120,16),(240,10)]:
        selected=[w for w in windows if w['length']==length]
        assert len(selected)==count and selected[-1]['end_index']==426
        assert all(w['end_index']-w['start_index']+1==length for w in selected)
        assert all(b['end_index']-a['end_index']==20 for a,b in zip(selected,selected[1:]))
    assert rolling_windows(dates[:19],lengths=[20])==[]


def test_window_fresh_cash_and_terminal_orders():
    frame=signals(['buy','hold','hold','hold'],[100,100,200,300])
    run=run_signal('a',frame.iloc[2:].reset_index(drop=True),.001)
    assert run.net.tolist()==[1000000,1000000]
    assert run.trades.empty
    last_buy=run_signal('a',signals(['hold','hold','buy']),.001)
    assert last_buy.trades.empty and last_buy.net[-1]==1000000


def test_costs_are_applied_on_both_fills_and_forced_exit():
    run=run_signal('a',signals(['buy','hold','hold']),.001)
    assert run.trades.iloc[0].entry_date==pd.Timestamp('2026-01-02')
    assert run.trades.iloc[0].exit_reason=='final_close'
    assert run.net[0]==1000000 and run.net[1]==999000
    assert run.net[-1]==pytest.approx(998001)
    gross,net=benchmark_curves([100,100,100],.001)
    assert net[0]==999000 and net[-1]==pytest.approx(998001)
    assert gross[-1]==1000000


def test_multiple_trade_costs_compound_without_changing_fill_prices():
    frame=signals(['buy','sell','hold','buy','sell','hold'],[100,100,110,110,110,121])
    run=run_signal('a',frame,.001)
    assert len(run.trades)==2
    assert run.gross[-1]==pytest.approx(1210000)
    assert run.net[-1]==pytest.approx(1210000*.999**4)


@pytest.mark.parametrize('a,b',list(itertools.product(['buy','sell','hold'],repeat=2)))
def test_asymmetric_consensus_buy_any_sell_truth_table(a,b):
    model={'id':'mix','name':'mix','mode':'entry_agreement_exit_any','components':{'a':1,'b':1}}
    row=signal_mix({'a':signals([a]),'b':signals([b])},model).iloc[0]
    expected='sell' if 'sell'in (a,b) else 'buy' if a==b=='buy' else 'hold'
    assert row.signal==expected


def test_combination_must_not_silently_intersect_different_dates_prices():
    a=signals(['buy','hold']);b=signals(['buy','hold'],[100,101])
    model={'id':'mix','name':'mix','mode':'and','components':{'a':1,'b':1}}
    with pytest.raises(ValueError,match='different dates or prices'):signal_mix({'a':a,'b':b},model)


def test_capital_split_keeps_cash_sleeve_and_sums_curves():
    moving=run_signal('a',signals(['buy','hold','hold'],[100,100,200]),.001)
    cash=run_signal('a',signals(['hold']*3),.001)
    mixed=capital_mix({'a':moving,'b':cash},{'components':{'a':.5,'b':.5}})
    assert np.allclose(mixed.net,.5*moving.net+.5*cash.net)
    assert mixed.gross[-1]==1500000
    assert mixed.trades.iloc[0].capital_weight==.5
    assert set(mixed.trades.sleeve_id)=={'a'}


def investor(dates, foreign):
    return pd.DataFrame({'stck_bsop_date':dates,'frgn_ntby_qty':foreign,'orgn_ntby_qty':[2]*len(dates),'prsn_ntby_qty':[-2]*len(dates)})


def test_merge_requires_equal_overlap_and_appends_only_new_observations():
    a=investor(['20260101','20260102'],[1,3]);b=investor(['20260102','20260103'],[3,4])
    assert len(merge_investor_history(a,b))==3
    b.loc[0,'frgn_ntby_qty']=100
    with pytest.raises(ValueError,match='Conflicting'):merge_investor_history(a,b)


def test_walk_tests_are_disjoint_training_uses_only_past_and_ids_exist():
    dates=pd.bdate_range('2025-01-08',periods=427);blocks=walk_blocks(dates);windows={w['id'] for w in rolling_windows(dates)}
    assert len(blocks)==15 and blocks[-1]['test_end_index']==426
    seen=set()
    for b in blocks:
        assert b['train_end_index']+1==b['test_start_index']
        assert b['train_end_index']-b['train_start_index']+1==120
        test=set(range(b['test_start_index'],b['test_end_index']+1));assert len(test)==20 and not seen&test;seen|=test
        assert f"roll-120-{b['train_end_index']}"in windows and f"roll-20-{b['test_end_index']}"in windows
    assert len(seen)==300


def test_selector_is_deterministic_and_only_reads_training_rows():
    train=[{'model_id':'b','net_return_pct':10,'net_mdd_pct':5},{'model_id':'a','net_return_pct':10,'net_mdd_pct':5},{'model_id':'c','net_return_pct':8,'net_mdd_pct':1}]
    assert select_model(train,'max_return')['model_id']=='a'
    assert select_model(train,'return_minus_mdd')['model_id']=='c'
    # Future test outcomes are deliberately not an argument to the selector.
    train[0]['test_net_return_pct']=10000
    assert select_model(train,'max_return')['model_id']=='a'


def test_future_price_and_flow_changes_do_not_change_prefix_signals():
    n=90;dates=pd.bdate_range('2025-01-01',periods=n)
    raw=pd.DataFrame({'date':dates,'close':100+np.sin(np.arange(n))*10+np.arange(n),'volume':1000})
    inv=pd.DataFrame({'date':dates,'foreign_net_qty':np.where(np.arange(n)%2,10,-10),'institutional_net_qty':10,'personal_net_qty':0})
    analyzer=DailyPriceAnalyzer.__new__(DailyPriceAnalyzer)
    original=build_signal_models(analyzer.calculate_indicators(raw),inv,candidate_models())
    mutated=raw.copy();mutated.loc[70:,'close']*=100
    changed_inv=inv.copy();changed_inv.loc[70:,'foreign_net_qty']=1000000
    changed=build_signal_models(analyzer.calculate_indicators(mutated),changed_inv,candidate_models())
    for mid,frame in original.items():
        pd.testing.assert_series_equal(frame.iloc[:70].signal,changed[mid].iloc[:70].signal)


def test_candidates_do_not_double_vote_equivalent_default_rules():
    models=candidate_models();assert len(models)==17
    unique=next(m for m in models if m['id']=='mix-unique6-weighted')
    assert len(unique['components'])==6 and 'disparity'not in unique['components']


def test_clean_output_preflight_uses_explicit_immutable_benchmark(tmp_path,monkeypatch,capsys):
    weekly=tmp_path/'weekly';history=tmp_path/'history';weekly.mkdir();history.mkdir()
    dates=pd.bdate_range('2024-10-14',periods=486)
    f=pd.DataFrame({'date':dates,'close':100,'volume':1000,'ma_5':100.,'ma_20':100.,'ma_60':100.,'rsi_14':50.,'momentum_20':0.})
    f.loc[:58,'ma_60']=np.nan
    for symbol in REPORT_SYMBOLS:
        f.to_csv(weekly/f'{symbol}_indicators.csv',index=False)
        investor(dates[:485].strftime('%Y%m%d'),[1]*485).to_csv(history/f'{symbol}_investor.csv',index=False)
        investor(dates[-13:].strftime('%Y%m%d'),[1]*13).to_csv(weekly/f'{symbol}_investor.csv',index=False)
    benchmark=tmp_path/'benchmark.csv';pd.DataFrame({'stck_bsop_date':dates.strftime('%Y%m%d'),'stck_clpr':100}).to_csv(benchmark,index=False)
    out=tmp_path/'new-output'
    monkeypatch.setattr('sys.argv',['run','--weekly-input',str(weekly),'--history-input',str(history),'--benchmark-input',str(benchmark),'--output',str(out),'--validate-inputs-only'])
    main()
    assert '"eligible_rows": 427'in capsys.readouterr().out
    assert not (out/'069500_prices.csv').exists()
