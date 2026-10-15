import math
import pandas as pd
import pytest

from invest_bot.jobs.backtest_comparison import buy_hold_curve, max_drawdown_pct, normalize_investor_summary, run_comparison, portfolio_comparison
from invest_bot.jobs.backtest_comparison import comparison_context
from invest_bot.backtest.persistence import enrich_summary
from datetime import UTC, datetime


def signals(prices,values):
    return pd.DataFrame({'date':pd.date_range('2026-01-01',periods=len(prices)),'close':prices,'signal':values,'strategy_id':'sample','strategy_name':'Sample'})


def test_benchmark_uses_sorted_same_period_prices_and_daily_drawdown():
    f=signals([100,50,100],['hold']*3).iloc[::-1]
    curve=buy_hold_curve(f)
    assert curve.equity.tolist()==[1000000,500000,1000000]
    assert max_drawdown_pct(curve.equity)==50


def test_cash_strategy_is_compared_with_market_return_not_trade_average():
    row,trades,equity,bh,_=run_comparison('005930',signals([100,150,200],['hold']*3))
    assert row['total_return_pct']==0 and row['benchmark_return_pct']==100
    assert row['excess_return_pp']==-100 and row['trade_count']==0
    assert row['invested_observation_pct']==0


def test_next_close_execution_and_final_exit_match_equity_and_compounding():
    row,trades,_,_,_=run_comparison('005930',signals([100,120,90,180],['buy','hold','hold','hold']))
    assert trades.iloc[0]['entry_price']==120 and trades.iloc[0]['exit_price']==180
    assert math.isclose(row['total_return_pct'],50) and row['max_drawdown_pct']==25
    assert row['benchmark_return_pct']==80 and math.isclose(row['excess_return_pp'],-30)
    assert row['forced_exit_count']==1


def test_common_window_starts_in_cash_without_carrying_earlier_position():
    f=signals([100,100,200,300],['buy','hold','hold','hold'])
    full,*_=run_comparison('005930',f)
    common,*_=run_comparison('005930',f,evaluation_start='2026-01-03')
    assert full['total_return_pct']==200
    assert common['total_return_pct']==0 and common['trade_count']==0
    assert common['benchmark_return_pct']==50


def test_terminal_sell_is_counted_as_final_liquidation():
    row,trades,*_=run_comparison('005930',signals([100,100,110],['buy','hold','sell']))
    assert row['forced_exit_count']==1
    assert trades.iloc[0]['exit_reason']=='sell_signal_final_close'


def test_comparison_sources_and_period_identity_share_an_actual_batch_time():
    now=datetime(2026,10,13,tzinfo=UTC)
    full=comparison_context('005930','investor-flow-custom','수급','prices.csv','investor.csv','full',now)
    common=comparison_context('005930','investor-flow-custom','수급','prices.csv','investor.csv','common_ready',now)
    assert full.run_group_id==common.run_group_id
    assert full.run_id!=common.run_id and full.timestamp_slug==common.timestamp_slug
    row=enrich_summary(pd.DataFrame([{'total_return_pct':1}]),full).iloc[0]
    assert row.price_source_dataset=='daily_prices_indicators' and row.price_source_filename=='prices.csv'
    assert row.investor_source_dataset=='investor_daily_summary' and row.investor_source_filename=='investor.csv'


def test_investor_observation_dates_are_normalized_without_request_date():
    f=pd.DataFrame({'stck_bsop_date':['20260102','20260101'],'frgn_ntby_qty':['1','2'],'orgn_ntby_qty':['-1','-2'],'prsn_ntby_qty':['0','0']})
    result=normalize_investor_summary(f)
    assert result.date.tolist()==list(pd.date_range('2026-01-01',periods=2))
    assert result.foreign_net_qty.tolist()==[2,1]


def test_portfolio_drawdown_is_from_pooled_curve_not_average_constituent_mdd():
    curves=[]
    for symbol,values in [('a',[1000000,500000,1000000]),('b',[1000000,1500000,1000000])]:
        curves.extend({'date':day,'symbol':symbol,'strategy_id':'s','evaluation_period':'full','equity':value,'benchmark_equity':value} for day,value in zip(pd.date_range('2026-01-01',periods=3),values))
    summaries=[{'strategy_id':'s','evaluation_period':'full','trade_count':1,'excess_return_pp':0,'total_return_pct':0,'invested_observation_pct':100}]*2
    result=portfolio_comparison(curves,summaries)[0]
    assert result['max_drawdown_pct']==0 and result['constituents']==2


@pytest.mark.parametrize('bad',[0,float('nan'),float('inf')])
def test_invalid_benchmark_prices_fail(bad):
    with pytest.raises(ValueError): buy_hold_curve(signals([100,bad],['hold']*2))
