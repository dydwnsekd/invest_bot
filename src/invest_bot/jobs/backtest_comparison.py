"""Compare existing strategy backtests with same-period price buy-and-hold."""
from __future__ import annotations

import argparse
import json
from datetime import UTC, date, datetime
from dataclasses import replace
from math import isclose, isfinite, prod
from pathlib import Path

import pandas as pd

from invest_bot.backtest.adapters import GOLDEN_CROSS_SIGNALS, build_strategy_signal_rows
from invest_bot.backtest.dates import require_unique_trading_dates
from invest_bot.backtest.parameters import default_backtest_parameters
from invest_bot.backtest.persistence import BacktestInputSources, build_context, build_output_filename, enrich_summary, enrich_trades, BACKTEST_SUMMARY_OUTPUT, BACKTEST_TRADES_OUTPUT
from invest_bot.backtest.runner import DEFAULT_BACKTEST_RUNNER, build_daily_mark_to_market_equity_curve
from invest_bot.backtest.strategy_registry import BACKTEST_STRATEGY_IDS, DAILY_PRICES_INDICATORS, INVESTOR_DAILY
from invest_bot.db.frame_storage import DbFrameStorage

INITIAL_EQUITY = 1_000_000.0
REPORT_SYMBOLS = ('005930','000660','005380','005385','000270','373220','207940','068270','035420','035720','105560','055550','005490','329180','012450','006400')


def comparison_context(symbol, sid, name, price_filename, investor_filename, period, now):
    sources = BacktestInputSources(
        indicator_source_filename=price_filename,
        signal_source_dataset=GOLDEN_CROSS_SIGNALS if sid=='golden-cross' else None,
        signal_source_filename=price_filename if sid=='golden-cross' else None,
        investor_source_dataset='investor_daily_summary' if sid=='investor-flow-custom' else None,
        investor_source_filename=investor_filename if sid=='investor-flow-custom' else None,
        price_source_dataset=DAILY_PRICES_INDICATORS, price_source_filename=price_filename,
    )
    context = build_context(symbol=symbol,strategy_id=sid,strategy_name=name,input_sources=sources,strategy_parameters=default_backtest_parameters(sid),now=now)
    return replace(context,run_group_id=f'backtest_comparison_{context.timestamp_slug}',run_id=f'{symbol}_{sid}_{period}_{context.timestamp_slug}')


def normalize_investor_summary(frame: pd.DataFrame) -> pd.DataFrame:
    result = frame.copy()
    result['date'] = pd.to_datetime(result['stck_bsop_date'].astype(str), format='%Y%m%d', errors='raise')
    result = result.rename(columns={'frgn_ntby_qty':'foreign_net_qty','orgn_ntby_qty':'institutional_net_qty','prsn_ntby_qty':'personal_net_qty'})
    for column in ['foreign_net_qty','institutional_net_qty','personal_net_qty']:
        result[column] = pd.to_numeric(result[column], errors='raise')
    require_unique_trading_dates(result, source='investor_daily_summary')
    return result.sort_values('date').reset_index(drop=True)


def max_drawdown_pct(equity: pd.Series, initial=INITIAL_EQUITY) -> float:
    values = pd.concat([pd.Series([initial]), equity.astype(float).reset_index(drop=True)], ignore_index=True)
    return abs(float(((values / values.cummax() - 1) * 100).min()))


def buy_hold_curve(prices: pd.DataFrame) -> pd.DataFrame:
    require_unique_trading_dates(prices, source='benchmark prices')
    result = prices[['date','close']].sort_values('date').reset_index(drop=True).copy()
    result['close'] = pd.to_numeric(result['close'], errors='raise')
    if result.empty or not result['close'].map(lambda x:isfinite(x) and x>0).all():
        raise ValueError('Benchmark requires positive finite prices')
    result['equity'] = INITIAL_EQUITY * result['close'] / result.iloc[0]['close']
    result['equity_return_pct'] = (result['equity']/INITIAL_EQUITY-1)*100
    return result


def run_comparison(symbol, signal_rows, *, evaluation_start=None):
    """Start in cash; signals before the comparison window never open positions."""
    signal_rows = signal_rows.copy()
    signal_rows['date'] = pd.to_datetime(signal_rows['date'])
    if evaluation_start is not None:
        signal_rows = signal_rows[signal_rows['date'] >= pd.Timestamp(evaluation_start)].copy()
    signal_rows = signal_rows.sort_values('date').reset_index(drop=True)
    result = DEFAULT_BACKTEST_RUNNER.run(symbol, signal_rows)
    equity = build_daily_mark_to_market_equity_curve(signal_rows, result.trades, initial_equity=INITIAL_EQUITY)
    benchmark = buy_hold_curve(signal_rows)
    assert equity['date'].equals(benchmark['date'])
    row = result.summary.iloc[0].to_dict()
    product_return = (prod(1+float(v)/100 for v in result.trades.get('return_pct', []))-1)*100
    curve_return = float(equity.iloc[-1]['equity_return_pct'])
    if not isclose(product_return, curve_return, abs_tol=1e-8) or not isclose(float(row['total_return_pct']), curve_return, abs_tol=1e-8):
        raise ValueError('Trade compounding, daily equity and summary disagree')
    if not isclose(float(row['max_drawdown_pct']), max_drawdown_pct(equity['equity']), abs_tol=1e-8):
        raise ValueError('Daily equity drawdown disagrees with summary')
    bh_return = float(benchmark.iloc[-1]['equity_return_pct'])
    row.update(
        start_date=str(signal_rows.iloc[0]['date'].date()), end_date=str(signal_rows.iloc[-1]['date'].date()),
        evaluation_rows=len(signal_rows), benchmark_return_pct=bh_return,
        excess_return_pp=curve_return-bh_return, benchmark_mdd_pct=max_drawdown_pct(benchmark['equity']),
        invested_observation_pct=float(equity['position_state'].isin(['보유','청산']).mean()*100),
        forced_exit_count=int(result.trades['exit_reason'].isin(['final_close','sell_signal_final_close']).sum()) if not result.trades.empty else 0,
        final_equity_won=float(equity.iloc[-1]['equity']), benchmark_final_equity_won=float(benchmark.iloc[-1]['equity']),
    )
    return row, result.trades, equity, benchmark, signal_rows


def portfolio_comparison(curves, summaries):
    rows = []
    equity = pd.DataFrame(curves)
    for (period, strategy), group in equity.groupby(['evaluation_period','strategy_id'], sort=False):
        matrix = group.pivot(index='date', columns='symbol', values='equity')
        bh = group.pivot(index='date', columns='symbol', values='benchmark_equity')
        if matrix.isna().any().any() or bh.isna().any().any():
            raise ValueError('Portfolio constituents have different dates')
        pooled = matrix.mean(axis=1); benchmark = bh.mean(axis=1)
        sub = [r for r in summaries if r['evaluation_period']==period and r['strategy_id']==strategy]
        ret=float((pooled.iloc[-1]/INITIAL_EQUITY-1)*100)
        bh_ret=float((benchmark.iloc[-1]/INITIAL_EQUITY-1)*100)
        rows.append({'evaluation_period':period,'strategy_id':strategy,'start_date':str(matrix.index.min().date()),'end_date':str(matrix.index.max().date()),'constituents':len(matrix.columns),'total_return_pct':ret,'benchmark_return_pct':bh_ret,'excess_return_pp':ret-bh_ret,'max_drawdown_pct':max_drawdown_pct(pooled),'benchmark_mdd_pct':max_drawdown_pct(benchmark),'trade_count':sum(r['trade_count'] for r in sub),'outperform_count':sum(r['excess_return_pp']>1e-8 for r in sub),'profitable_count':sum(r['total_return_pct']>1e-8 for r in sub),'mean_invested_observation_pct':sum(r['invested_observation_pct'] for r in sub)/len(sub),'history':[[str(day.date()),float(a),float(b)] for day,a,b in zip(matrix.index,pooled,benchmark)]})
    return rows


def main():
    parser=argparse.ArgumentParser(description='Run all seven strategies against a fixed historical snapshot and export benchmark comparisons.')
    parser.add_argument('--output',default='data/backtests/2026-10-13')
    parser.add_argument('--as-of',type=date.fromisoformat,default=date(2026,10,12))
    args=parser.parse_args(); folder=Path(args.output); folder.mkdir(parents=True,exist_ok=True)
    storage=DbFrameStorage.from_settings(); now=datetime.now(UTC)
    symbols=REPORT_SYMBOLS
    inputs={}; ready_dates=[]
    for symbol in symbols:
        filename=f'{symbol}_20241013_20261013_history.csv'
        inv_name=f'{symbol}_20241013_20261012_history.csv'
        indicators=storage.load(DAILY_PRICES_INDICATORS,filename).copy(); indicators['date']=pd.to_datetime(indicators['date'])
        indicators=indicators[indicators['date']<=pd.Timestamp(args.as_of)].sort_values('date').reset_index(drop=True)
        signals=storage.load(GOLDEN_CROSS_SIGNALS,filename).copy(); signals['date']=pd.to_datetime(signals['date']); signals=signals[signals['date']<=pd.Timestamp(args.as_of)].sort_values('date').reset_index(drop=True)
        investor=normalize_investor_summary(storage.load('investor_daily_summary',inv_name)); investor=investor[investor['date']<=pd.Timestamp(args.as_of)].reset_index(drop=True)
        if indicators.empty or set(indicators['date'])!=set(investor['date']):
            raise ValueError(f'{symbol}: price/investor observation dates do not match')
        if args.as_of==date(2026,10,12) and len(indicators)!=485:
            raise ValueError(f'{symbol}: the fixed snapshot must contain 485 closed observations')
        first_ready=indicators.dropna(subset=['ma_5','ma_20','ma_60','rsi_14','momentum_20']).iloc[0]['date']; ready_dates.append(first_ready)
        report=storage.load('market_reports',f'{symbol}_20261012.csv').iloc[0]
        inputs[symbol]=(indicators,signals,investor,filename,inv_name,str(report['symbol_name']))
    common_start=max(ready_dates)
    summaries=[]; curves=[]; bundles=[]
    for symbol,(indicators,signals,investor,filename,inv_name,name) in inputs.items():
        datasets={DAILY_PRICES_INDICATORS:indicators,GOLDEN_CROSS_SIGNALS:signals,INVESTOR_DAILY:investor}
        rows_by_strategy={sid:build_strategy_signal_rows(sid,datasets) for sid in BACKTEST_STRATEGY_IDS}
        assert rows_by_strategy['mean-reversion']['signal'].equals(rows_by_strategy['disparity']['signal']),symbol
        for period,start in [('full',None),('common_ready',common_start)]:
            period_curves={}
            for sid,signal_rows in rows_by_strategy.items():
                row,trades,equity,benchmark,used=run_comparison(symbol,signal_rows,evaluation_start=start)
                row.update(symbol=symbol,symbol_name=name,strategy_id=sid,evaluation_period=period)
                context=comparison_context(symbol,sid,str(signal_rows.iloc[0]['strategy_name']),filename,inv_name,period,now)
                summary=enrich_summary(pd.DataFrame([row]),context); trade_frame=enrich_trades(trades,context)
                trade_frame['evaluation_period']=period
                summary_filename=build_output_filename(summary,BACKTEST_SUMMARY_OUTPUT).replace('_backtest_summary.csv',f'_{period}_backtest_summary.csv')
                trades_filename=build_output_filename(trade_frame,BACKTEST_TRADES_OUTPUT).replace('_backtest_trades.csv',f'_{period}_backtest_trades.csv')
                storage.save('backtest_summaries',summary_filename,summary)
                storage.save('backtest_trades',trades_filename,trade_frame)
                row=summary.iloc[0].to_dict(); summaries.append(row)
                prefix=f'{symbol}_{sid}_{period}'
                summary.to_csv(folder/f'{prefix}_summary.csv',index=False)
                trade_frame.to_csv(folder/f'{prefix}_trades.csv',index=False)
                used.to_csv(folder/f'{prefix}_signals.csv',index=False)
                curve=equity.copy(); curve['benchmark_equity']=benchmark['equity']; curve.to_csv(folder/f'{prefix}_equity.csv',index=False)
                period_curves[sid]=[[str(r['date'].date()),float(r['equity_return_pct'])] for _,r in equity.iterrows()]
                curves.extend({'date':r['date'],'equity':r['equity'],'benchmark_equity':benchmark.iloc[i]['equity'],'symbol':symbol,'strategy_id':sid,'evaluation_period':period} for i,r in equity.iterrows())
            bundles.append({'symbol':symbol,'name':name,'evaluation_period':period,'curves':period_curves,'benchmark_curve':[[str(r['date'].date()),float(r['equity_return_pct'])] for _,r in benchmark.iterrows()]})
        print(json.dumps({'symbol':symbol,'name':name,'strategies':7,'periods':2,'status':'completed'},ensure_ascii=False),flush=True)
    portfolios=portfolio_comparison(curves,summaries)
    payload={'generated_at':str(now),'comparison_run_id':summaries[0]['run_group_id'],'full_start':str(next(iter(inputs.values()))[0].iloc[0]['date'].date()),'common_start':str(common_start.date()),'end_date':str(args.as_of),'full_rows':len(next(iter(inputs.values()))[0]),'common_rows':len(next(iter(inputs.values()))[0][lambda f:f['date']>=common_start]),'initial_equity':INITIAL_EQUITY,'summaries':summaries,'portfolio_summaries':portfolios,'bundles':bundles,'assumptions':{'fees':0,'tax':0,'slippage':0,'dividends':False,'fractional_shares':True,'cash_interest':0,'execution':'next close; terminal positions liquidated at final close','benchmark':'adjusted-price buy-and-hold, not brokerage realized return','point_in_time_investor_publication_verified':False},'strategy_parameters':{s:default_backtest_parameters(s) for s in BACKTEST_STRATEGY_IDS}}
    (folder/'comparison.json').write_text(json.dumps(payload,ensure_ascii=False,default=str).replace(': NaN',': null'))
    pd.DataFrame(summaries).to_csv(folder/'comparison_summary.csv',index=False)
    pd.DataFrame([{k:v for k,v in p.items() if k!='history'} for p in portfolios]).to_csv(folder/'portfolio_summary.csv',index=False)
    print('FINAL_JSON '+json.dumps({'symbols':len(inputs),'strategies':7,'runs':len(summaries),'common_start':payload['common_start'],'common_rows':payload['common_rows'],'output':str(folder)},ensure_ascii=False),flush=True)


if __name__=='__main__':
    main()
