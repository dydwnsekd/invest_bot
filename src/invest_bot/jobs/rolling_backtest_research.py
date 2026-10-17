"""Fixed-candidate rolling-window research from immutable local market exports."""
from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

from invest_bot.backtest.adapters import build_strategy_signal_rows
from invest_bot.backtest.combination import combine_strategy_signal_rows, resolve_backtest_combination_settings
from invest_bot.backtest.dates import require_unique_trading_dates
from invest_bot.backtest.parameters import default_backtest_parameters
from invest_bot.backtest.strategy_registry import BACKTEST_STRATEGY_IDS, DAILY_PRICES_INDICATORS, INVESTOR_DAILY
from invest_bot.jobs.backtest_comparison import INITIAL_EQUITY, REPORT_SYMBOLS, normalize_investor_summary, run_comparison

NAMES = {'golden-cross':'골든크로스','rsi':'RSI','trend-filter':'추세 필터','mean-reversion':'평균회귀','disparity':'이격도','momentum':'모멘텀','investor-flow-custom':'수급 결합'}
SINGLE_RULES = {
    'golden-cross':'5일선이20일선을 상향 돌파하면 매수, 하향 돌파하면 매도',
    'rsi':'앱의 단순14일 평균 RSI≤30이면 매수, ≥70이면 매도; 결측이면 관망',
    'trend-filter':'종가가60일선 위이고 직전 종가보다 높으면 매수; 60일선 아래이고 직전 종가보다 낮으면 매도',
    'mean-reversion':'종가/20일선≤0.97이면 매수, ≥1.03이면 매도',
    'disparity':'종가/20일선×100≤97이면 매수, ≥103이면 매도; 기본 평균회귀와 동일',
    'momentum':'20거래일 가격 변화≥10%이면 매수, ≤−10%이면 매도',
    'investor-flow-custom':'외국인·기관 모두 순매수이고 종가가20일선 위이면 매수; 모두 순매도이고 종가가20일선 아래이면 매도',
}


def candidate_models():
    models = [dict(id=s,name=NAMES[s],type='single',mode='single',components={s:1.0},rules=SINGLE_RULES[s],parameters={s:default_backtest_parameters(s)},includes_flow=s=='investor-flow-custom') for s in BACKTEST_STRATEGY_IDS]
    presets = [
        ('mix-mt-and','모멘텀·추세 AND','and',{'momentum':1,'trend-filter':1}),
        ('mix-mt-or','모멘텀·추세 OR','or',{'momentum':1,'trend-filter':1}),
        ('mix-mt-weighted','모멘텀·추세 2:1 투표','weighted',{'momentum':2,'trend-filter':1}),
        ('mix-mt-exit-any','모멘텀·추세 진입합의/청산우선','entry_agreement_exit_any',{'momentum':1,'trend-filter':1}),
        ('mix-mtf-weighted','모멘텀·추세·수급 2:1:1 투표','weighted',{'momentum':2,'trend-filter':1,'investor-flow-custom':1}),
        ('mix-mtf-exit-any','모멘텀·추세·수급 진입합의/청산우선','entry_agreement_exit_any',{'momentum':1,'trend-filter':1,'investor-flow-custom':1}),
        ('mix-unique6-weighted','중복 배제 6전략 동일 투표','weighted',{s:1 for s in BACKTEST_STRATEGY_IDS if s!='disparity'}),
        ('capital-mr-50','모멘텀·RSI 50:50 자금분할','capital',{'momentum':.5,'rsi':.5}),
        ('capital-mtr-40','모멘텀·추세·RSI 40:40:20 자금분할','capital',{'momentum':.4,'trend-filter':.4,'rsi':.2}),
        ('capital-mt-50','모멘텀·추세 50:50 자금분할','capital',{'momentum':.5,'trend-filter':.5}),
    ]
    rules = {'and':'매수·매도 모두 구성 전략의 전원 합의 필요; 그 외 관망','or':'매수 또는 매도 하나라도 충족; 두 방향 충돌 시 관망','weighted':'매수 +가중치, 매도 −가중치; 합계 부호만 사용; 자금 배분 아님','entry_agreement_exit_any':'전원 매수 시 진입; 한 전략이라도 매도하면 청산; 그 외 관망','capital':'독립 계좌별 초기 자금 배분, 종목/계좌 간 재배분 없이 평가금액 합산'}
    for mid,name,mode,components in presets:
        models.append(dict(id=mid,name=name,type='capital_mix' if mode=='capital' else 'signal_mix',mode=mode,components=components,rules=rules[mode],parameters={s:default_backtest_parameters(s) for s in components},includes_flow='investor-flow-custom' in components))
    return models


def merge_investor_history(history, latest):
    a=normalize_investor_summary(history); b=normalize_investor_summary(latest)
    cols=['foreign_net_qty','institutional_net_qty','personal_net_qty']
    overlap=a.set_index('date')[cols].join(b.set_index('date')[cols],how='inner',lsuffix='_old',rsuffix='_new')
    if any(not overlap[c+'_old'].eq(overlap[c+'_new']).all() for c in cols):
        raise ValueError('Conflicting investor history; revisions require explicit handling')
    result=pd.concat([a,b[~b.date.isin(a.date)]],ignore_index=True).sort_values('date').reset_index(drop=True)
    require_unique_trading_dates(result,source='merged investor history')
    return result


def signal_mix(frames, model):
    selected={s:frames[s] for s in model['components']}
    first=next(iter(selected.values()))
    for f in selected.values():
        if not f.date.equals(first.date) or not f.close.equals(first.close):
            raise ValueError('Combination components have different dates or prices')
    if model['mode']=='entry_agreement_exit_any':
        result=first[['date','close']].copy()
        votes=pd.DataFrame({s:f.signal for s,f in selected.items()})
        result['signal']=np.select([votes.eq('sell').any(axis=1),votes.eq('buy').all(axis=1)],['sell','buy'],default='hold')
        result['component_signals']=votes.apply(lambda r:json.dumps(r.to_dict(),ensure_ascii=False),axis=1)
    else:
        settings=resolve_backtest_combination_settings(list(selected),model['mode'],model['components'])
        result=combine_strategy_signal_rows(selected,settings)
    result['strategy_id']=model['id']; result['strategy_name']=model['name']
    return result


def build_signal_models(indicators, investor, models):
    datasets={DAILY_PRICES_INDICATORS:indicators,INVESTOR_DAILY:investor}
    frames={s:build_strategy_signal_rows(s,datasets) for s in BACKTEST_STRATEGY_IDS}
    if not frames['mean-reversion'].signal.equals(frames['disparity'].signal):
        raise ValueError('Expected equivalent default mean-reversion/disparity signals')
    for model in models:
        if model['type']=='signal_mix':frames[model['id']]=signal_mix(frames,model)
    return frames


def rolling_windows(dates, lengths=(20,60,120,240), step=20):
    if step<=0 or any(length<2 for length in lengths):raise ValueError('Invalid window definition')
    windows=[]
    for length in lengths:
        for end in reversed(range(len(dates)-1,length-2,-step)):
            start=end-length+1
            windows.append(dict(id=f'roll-{length}-{end}',kind='rolling',length=length,start_index=start,end_index=end,start_date=str(pd.Timestamp(dates[start]).date()),end_date=str(pd.Timestamp(dates[end]).date())))
    return windows


def mdd(values):
    a=np.r_[INITIAL_EQUITY,np.asarray(values,dtype=float)]
    return float(-(a/np.maximum.accumulate(a)-1).min()*100)


def apply_costs(gross, dates, trades, rate):
    if not 0<=rate<1:raise ValueError('Cost rate must be in [0,1)')
    events=np.zeros(len(dates),dtype=int)
    positions={pd.Timestamp(d):i for i,d in enumerate(dates)}
    for _,trade in trades.iterrows():
        events[positions[pd.Timestamp(trade.entry_date)]]+=1
        events[positions[pd.Timestamp(trade.exit_date)]]+=1
    return np.asarray(gross,dtype=float)*(1-rate)**np.cumsum(events)


def benchmark_curves(close, rate):
    prices=np.asarray(close,dtype=float)
    if len(prices)<2 or not np.isfinite(prices).all() or (prices<=0).any():raise ValueError('Invalid benchmark prices')
    gross=INITIAL_EQUITY*prices/prices[0]; net=gross*(1-rate);net[-1]*=(1-rate)
    return gross,net


def select_model(train_rows, policy):
    if policy not in {'max_return','return_minus_mdd'}:raise ValueError('Unknown selector')
    def order(r):
        score=r['net_return_pct']-(r['net_mdd_pct'] if policy=='return_minus_mdd' else 0)
        return (-score,r['net_mdd_pct'],r['model_id'])
    return min(train_rows,key=order)


def walk_blocks(dates, train_length=120, test_length=20):
    # Training windows can overlap; all test windows are consecutive and disjoint.
    starts=sorted(range(len(dates)-test_length,train_length-1,-test_length))
    return [dict(block_id=i+1,train_start_index=t-train_length,train_end_index=t-1,test_start_index=t,test_end_index=t+test_length-1) for i,t in enumerate(starts)]


@dataclass
class Run:
    gross: np.ndarray
    net: np.ndarray
    exposure: np.ndarray
    trades: pd.DataFrame


def run_signal(symbol, signals, rate):
    row,trades,equity,_,_=run_comparison(symbol,signals)
    gross=equity.equity.to_numpy(dtype=float);net=apply_costs(gross,equity.date,trades,rate)
    expected=INITIAL_EQUITY*float(np.prod((1+trades.return_pct.to_numpy(dtype=float)/100)*(1-rate)**2))
    if not np.isclose(net[-1],expected,rtol=1e-10,atol=1e-7):raise ValueError('Net trade/equity reconciliation failed')
    return Run(gross,net,equity.position_state.isin(['보유','청산']).to_numpy(dtype=float),trades)


def capital_mix(runs, model):
    weights=model['components']
    if not np.isclose(sum(weights.values()),1) or any(v<=0 for v in weights.values()):raise ValueError('Capital weights must be positive and sum to one')
    trades=[]
    for sid,weight in weights.items():
        t=runs[sid].trades.copy();t['sleeve_id']=sid;t['capital_weight']=weight
        if not t.empty:trades.append(t)
    combined=pd.concat(trades,ignore_index=True) if trades else t.iloc[:0].copy()
    return Run(sum(runs[s].gross*w for s,w in weights.items()),sum(runs[s].net*w for s,w in weights.items()),sum(runs[s].exposure*w for s,w in weights.items()),combined)


def run_metrics(run, rate):
    trades=run.trades;net_trades=(1+trades.return_pct.astype(float)/100)*(1-rate)**2-1
    return dict(gross_return_pct=float((run.gross[-1]/INITIAL_EQUITY-1)*100),net_return_pct=float((run.net[-1]/INITIAL_EQUITY-1)*100),gross_mdd_pct=mdd(run.gross),net_mdd_pct=mdd(run.net),trade_count=len(trades),forced_exit_count=int(trades.exit_reason.isin(['final_close','sell_signal_final_close']).sum()),exposure_pct=float(run.exposure.mean()*100),win_rate_net_pct=float((net_trades>0).mean()*100) if len(trades) else None)


def aggregate_results(frame, groups):
    rows=[]
    for keys,f in frame.groupby(groups,sort=False):
        if not isinstance(keys,tuple):keys=(keys,)
        row=dict(zip(groups,keys,strict=True));r=f.net_return_pct
        row.update(windows=len(f),median_net_return_pct=float(r.median()),q25_net_return_pct=float(r.quantile(.25)),q75_net_return_pct=float(r.quantile(.75)),min_net_return_pct=float(r.min()),max_net_return_pct=float(r.max()),positive_window_pct=float(r.gt(0).mean()*100),bh_outperform_window_pct=float((r>f.bh_net_return_pct+1e-8).mean()*100),etf_outperform_window_pct=float((r>f.etf_net_return_pct+1e-8).mean()*100),median_net_mdd_pct=float(f.net_mdd_pct.median()),worst_net_mdd_pct=float(f.net_mdd_pct.max()),mean_trade_count=float(f.trade_count.mean()),mean_exposure_pct=float(f['mean_exposure_pct' if 'mean_exposure_pct'in f else 'exposure_pct'].mean()))
        rows.append(row)
    return rows


def json_default(value):
    if hasattr(value,'item'):return value.item()
    if isinstance(value,Path):return str(value)
    raise TypeError(type(value).__name__)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=Path('data/rolling-backtests/2026-10-13'))
    parser.add_argument('--weekly-input',type=Path,default=Path('data/weekly-trend/2026-10-13'))
    parser.add_argument('--history-input',type=Path,default=Path('data/history/2026-10-13'))
    parser.add_argument('--benchmark-input',type=Path,default=Path('data/rolling-inputs/2026-10-13/069500_prices.csv'))
    parser.add_argument('--cost-rate',type=float,default=.001)
    parser.add_argument('--validate-inputs-only',action='store_true')
    args=parser.parse_args(); out=args.output;out.mkdir(parents=True,exist_ok=True)
    if not 0<=args.cost_rate<1:parser.error('invalid cost rate')
    rate=args.cost_rate;models=candidate_models(); (out/'models.json').write_text(json.dumps(models,ensure_ascii=False,indent=2))
    inputs={};ready=[];sources=[]
    for symbol in REPORT_SYMBOLS:
        source=args.weekly_input/f'{symbol}_indicators.csv';f=pd.read_csv(source,parse_dates=['date'])
        history=args.history_input/f'{symbol}_investor.csv';latest=args.weekly_input/f'{symbol}_investor.csv'
        inv=merge_investor_history(pd.read_csv(history),pd.read_csv(latest))
        require_unique_trading_dates(f,source=str(source))
        if len(f)!=486 or not f.date.equals(inv.date):raise ValueError(f'{symbol}: expected 486 aligned dates')
        ready.append(f.dropna(subset=['ma_5','ma_20','ma_60','rsi_14','momentum_20']).iloc[0].date)
        inputs[symbol]=(f,inv)
        for p in [source,history,latest]:sources.append(dict(symbol=symbol,path=str(p),sha256=hashlib.sha256(p.read_bytes()).hexdigest()))
    start=max(ready);dates=next(iter(inputs.values()))[0].date[lambda d:d>=start].reset_index(drop=True)
    if len(dates)!=427:raise ValueError('Expected 427 common-ready observations')
    etf_path=args.benchmark_input;etf=pd.read_csv(etf_path);etf['date']=pd.to_datetime(etf.stck_bsop_date.astype(str),format='%Y%m%d');etf=etf[etf.date>=start].reset_index(drop=True)
    if not etf.date.equals(dates):raise ValueError('ETF/stock benchmark calendars differ')
    if args.validate_inputs_only:
        print(json.dumps(dict(stock_sources=len(inputs),raw_rows=486,eligible_rows=len(dates),benchmark_input=str(etf_path),output=str(out)),ensure_ascii=False))
        return
    if etf_path.resolve()!=(out/'069500_prices.csv').resolve():
        shutil.copyfile(etf_path,out/'069500_prices.csv')
    manifest_source=etf_path.parent/'benchmark_manifest.json'
    if manifest_source.exists() and manifest_source.resolve()!=(out/'benchmark_manifest.json').resolve():
        shutil.copyfile(manifest_source,out/'benchmark_manifest.json')
    elif not (out/'benchmark_manifest.json').exists():
        (out/'benchmark_manifest.json').write_text(json.dumps(dict(symbol='069500',name='KODEX 200',source=str(etf_path),sha256=hashlib.sha256(etf_path.read_bytes()).hexdigest()),ensure_ascii=False))
    name_rows=json.loads((args.weekly_input/'collection_manifest.json').read_text())['results'];names={r['symbol']:r['name'] for r in name_rows}
    signal_models={};prices={}
    signal_dir=out/'signals';signal_dir.mkdir(exist_ok=True)
    for symbol,(f,inv) in inputs.items():
        frames=build_signal_models(f,inv,models)
        signal_models[symbol]={k:v[v.date>=start].reset_index(drop=True) for k,v in frames.items()}
        prices[symbol]=f[f.date>=start].reset_index(drop=True)
        if not prices[symbol].date.equals(dates):raise ValueError('Different constituent calendars')
        for mid,v in frames.items():v.to_csv(signal_dir/f'{symbol}_{mid}.csv',index=False)
    sources.append(dict(symbol='069500',path=str(etf_path),sha256=hashlib.sha256(etf_path.read_bytes()).hexdigest()))
    snapshot_dir=out/'inputs';snapshot_dir.mkdir(exist_ok=True)
    for i,source in enumerate(sources):
        p=Path(source['path']);target=snapshot_dir/f'{i:02d}_{p.parent.name}_{p.name}'
        shutil.copyfile(p,target);source['snapshot_file']=str(target.relative_to(out))
    (out/'inputs_manifest.json').write_text(json.dumps(sources,ensure_ascii=False,indent=2))
    windows=rolling_windows(dates)
    for wid,kind,a,b in [('full','full',0,len(dates)-1),('recent-5','recent',len(dates)-5,len(dates)-1)]:
        windows.append(dict(id=wid,kind=kind,length=b-a+1,start_index=a,end_index=b,start_date=str(dates[a].date()),end_date=str(dates[b].date())))
    selected={w['id'] for w in windows if w['end_index']==len(dates)-1}
    stock_rows=[];portfolio_rows=[];curves={};run_count=0
    trade_header=['window_id','model_id','symbol','sleeve_id','capital_weight','entry_signal_date','entry_date','entry_price','exit_signal_date','exit_date','exit_price','gross_return_pct','net_return_pct','holding_days','exit_reason']
    with (out/'trade_log.csv').open('w',newline='') as tf,gzip.open(out/'stock_equity_selected.csv.gz','wt',newline='') as ef:
        trade_writer=csv.DictWriter(tf,fieldnames=trade_header);trade_writer.writeheader()
        eq_writer=csv.writer(ef);eq_writer.writerow(['window_id','model_id','symbol','date','gross_equity','net_equity','invested_fraction'])
        for wi,w in enumerate(windows):
            a=w['start_index'];b=w['end_index']+1;wd=dates[a:b].reset_index(drop=True)
            eg,en=benchmark_curves(etf.iloc[a:b].stck_clpr,rate); etf_ret=float((eg[-1]/INITIAL_EQUITY-1)*100)
            w['etf_gross_return_pct']=etf_ret;w['regime']='상승' if etf_ret>=3 else '하락' if etf_ret<=-3 else '횡보'
            bhg=[];bhn=[];model_runs={m['id']:[] for m in models};sub_rows=[]
            for symbol in REPORT_SYMBOLS:
                bg,bn=benchmark_curves(prices[symbol].iloc[a:b].close,rate);bhg.append(bg);bhn.append(bn)
                common=dict(window_id=w['id'],kind=w['kind'],length=w['length'],start_date=w['start_date'],end_date=w['end_date'],symbol=symbol,symbol_name=names[symbol],regime=w['regime'],bh_gross_return_pct=float((bg[-1]/INITIAL_EQUITY-1)*100),bh_net_return_pct=float((bn[-1]/INITIAL_EQUITY-1)*100),bh_net_mdd_pct=mdd(bn),etf_gross_return_pct=etf_ret,etf_net_return_pct=float((en[-1]/INITIAL_EQUITY-1)*100),etf_net_mdd_pct=mdd(en))
                runs={}
                for model in models:
                    mid=model['id']
                    run=capital_mix(runs,model) if model['type']=='capital_mix' else run_signal(symbol,signal_models[symbol][mid].iloc[a:b].reset_index(drop=True),rate)
                    if model['type']!='capital_mix':run_count+=1
                    runs[mid]=run;model_runs[mid].append(run)
                    row={**common,'model_id':mid,**run_metrics(run,rate)};stock_rows.append(row);sub_rows.append(row)
                    for _,t in run.trades.iterrows():
                        trade_writer.writerow(dict(window_id=w['id'],model_id=mid,symbol=symbol,sleeve_id=t.get('sleeve_id',mid),capital_weight=t.get('capital_weight',1),entry_signal_date=str(t.entry_signal_date.date()),entry_date=str(t.entry_date.date()),entry_price=t.entry_price,exit_signal_date=str(t.exit_signal_date.date()),exit_date=str(t.exit_date.date()),exit_price=t.exit_price,gross_return_pct=t.return_pct,net_return_pct=((1+float(t.return_pct)/100)*(1-rate)**2-1)*100,holding_days=t.holding_days,exit_reason=t.exit_reason))
                    if w['id']in selected:
                        eq_writer.writerows((w['id'],mid,symbol,str(d.date()),float(g),float(n),float(e)) for d,g,n,e in zip(wd,run.gross,run.net,run.exposure,strict=True))
            pooled_bg=np.mean(bhg,axis=0);pooled_bn=np.mean(bhn,axis=0)
            window_curves=dict(dates=wd.dt.strftime('%Y-%m-%d').tolist(),models={},buy_hold=dict(gross=pooled_bg.tolist(),net=pooled_bn.tolist()),etf=dict(gross=eg.tolist(),net=en.tolist()))
            for model in models:
                mid=model['id'];rr=model_runs[mid];g=np.mean([r.gross for r in rr],axis=0);n=np.mean([r.net for r in rr],axis=0)
                subset=[r for r in sub_rows if r['model_id']==mid]
                portfolio_rows.append(dict(window_id=w['id'],kind=w['kind'],length=w['length'],start_date=w['start_date'],end_date=w['end_date'],model_id=mid,regime=w['regime'],gross_return_pct=float((g[-1]/INITIAL_EQUITY-1)*100),net_return_pct=float((n[-1]/INITIAL_EQUITY-1)*100),gross_mdd_pct=mdd(g),net_mdd_pct=mdd(n),bh_gross_return_pct=float((pooled_bg[-1]/INITIAL_EQUITY-1)*100),bh_net_return_pct=float((pooled_bn[-1]/INITIAL_EQUITY-1)*100),bh_net_mdd_pct=mdd(pooled_bn),etf_gross_return_pct=etf_ret,etf_net_return_pct=float((en[-1]/INITIAL_EQUITY-1)*100),etf_net_mdd_pct=mdd(en),trade_count=sum(r['trade_count'] for r in subset),forced_exit_count=sum(r['forced_exit_count'] for r in subset),no_trade_constituents=sum(r['trade_count']==0 for r in subset),mean_exposure_pct=float(np.mean([r['exposure_pct'] for r in subset])),profitable_constituents=sum(r['net_return_pct']>0 for r in subset)))
                window_curves['models'][mid]=dict(gross=g.tolist(),net=n.tolist())
            curves[w['id']]=window_curves
            print(json.dumps(dict(window=wi+1,total=len(windows),id=w['id'],length=w['length'],end_date=w['end_date']),ensure_ascii=False),flush=True)
    pf=pd.DataFrame(portfolio_rows);sf=pd.DataFrame(stock_rows);rolling_pf=pf[pf.kind=='rolling'];rolling_sf=sf[sf.kind=='rolling']
    ag=aggregate_results(rolling_pf,['length','model_id']);sag=aggregate_results(rolling_sf,['symbol','symbol_name','length','model_id']);rag=aggregate_results(rolling_pf,['length','regime','model_id'])
    lookup={(r['window_id'],r['model_id']):r for r in portfolio_rows};wfblocks=[];policies=['max_return','return_minus_mdd'];policy_paths={p:[] for p in policies};policy_levels={p:INITIAL_EQUITY for p in policies};fixed_paths={m['id']:[] for m in models};fixed_levels={m['id']:INITIAL_EQUITY for m in models};wfdates=[];wf_bh=[];wf_etf=[];bh_level=etf_level=INITIAL_EQUITY
    for block in walk_blocks(dates):
        train_id=f"roll-120-{block['train_end_index']}";test_id=f"roll-20-{block['test_end_index']}";train=pf[pf.window_id==train_id].to_dict('records');tc=curves[test_id]
        block.update(train_window_id=train_id,test_window_id=test_id,train_start=str(dates[block['train_start_index']].date()),train_end=str(dates[block['train_end_index']].date()),test_start=str(dates[block['test_start_index']].date()),test_end=str(dates[block['test_end_index']].date()),selections=[])
        for policy in policies:
            chosen=select_model(train,policy);test=lookup[(test_id,chosen['model_id'])]
            block['selections'].append(dict(policy=policy,model_id=chosen['model_id'],train_net_return_pct=chosen['net_return_pct'],train_net_mdd_pct=chosen['net_mdd_pct'],test_net_return_pct=test['net_return_pct'],test_net_mdd_pct=test['net_mdd_pct'],test_bh_net_return_pct=test['bh_net_return_pct'],test_etf_net_return_pct=test['etf_net_return_pct']))
            path=np.asarray(tc['models'][chosen['model_id']]['net'])/INITIAL_EQUITY*policy_levels[policy];policy_paths[policy].extend(path.tolist());policy_levels[policy]=float(path[-1])
        for model in models:
            mid=model['id'];path=np.asarray(tc['models'][mid]['net'])/INITIAL_EQUITY*fixed_levels[mid];fixed_paths[mid].extend(path.tolist());fixed_levels[mid]=float(path[-1])
        bpath=np.asarray(tc['buy_hold']['net'])/INITIAL_EQUITY*bh_level;epath=np.asarray(tc['etf']['net'])/INITIAL_EQUITY*etf_level
        wf_bh.extend(bpath.tolist());wf_etf.extend(epath.tolist());bh_level=float(bpath[-1]);etf_level=float(epath[-1]);wfdates.extend(tc['dates']);wfblocks.append(block)
    wf=dict(train_length=120,test_length=20,blocks=wfblocks,policy_summaries=[dict(policy=p,net_return_pct=(policy_levels[p]/INITIAL_EQUITY-1)*100,net_mdd_pct=mdd(policy_paths[p]),bh_net_return_pct=(bh_level/INITIAL_EQUITY-1)*100,etf_net_return_pct=(etf_level/INITIAL_EQUITY-1)*100) for p in policies],fixed_summaries=[dict(model_id=m['id'],net_return_pct=(fixed_levels[m['id']]/INITIAL_EQUITY-1)*100,net_mdd_pct=mdd(fixed_paths[m['id']])) for m in models],curves=dict(dates=wfdates,policies=policy_paths,buy_hold=wf_bh,etf=wf_etf))
    metadata=dict(as_of=str(dates.iloc[-1].date()),raw_start=str(next(iter(inputs.values()))[0].date.iloc[0].date()),raw_rows=486,eligible_start=str(start.date()),eligible_rows=len(dates),step=20,lengths=[20,60,120,240],cost_rate=rate,generated_at=str(datetime.now(ZoneInfo('Asia/Seoul'))),runner_calls=run_count,stock_model_evaluations=len(stock_rows),rolling_window_count=len(windows)-2)
    payload=dict(metadata=metadata,models=models,windows=windows,portfolio_results=portfolio_rows,stock_results=stock_rows,aggregates=ag,stock_aggregates=sag,regime_aggregates=rag,curves=curves,walk_forward=wf)
    for name,frame in [('window_results',sf),('portfolio_results',pf),('aggregates',pd.DataFrame(ag)),('stock_aggregates',pd.DataFrame(sag)),('regime_aggregates',pd.DataFrame(rag)),('windows',pd.DataFrame(windows)),('walk_forward_selections',pd.DataFrame([{**{k:v for k,v in b.items() if k!='selections'},**s} for b in wfblocks for s in b['selections']]))]:frame.to_csv(out/f'{name}.csv',index=False)
    (out/'results.json').write_text(json.dumps(payload,ensure_ascii=False,default=json_default,allow_nan=False))
    print('FINAL_JSON '+json.dumps(metadata,ensure_ascii=False),flush=True)


if __name__=='__main__':main()
