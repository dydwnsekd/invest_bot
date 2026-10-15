"""Render the fixed-snapshot comparison exports as a self-contained HTML report."""
from __future__ import annotations

import argparse
import csv
import json
from html import escape
from pathlib import Path

NAMES = {
    'golden-cross': '골든크로스', 'rsi': 'RSI', 'trend-filter': '추세 필터',
    'mean-reversion': '평균회귀', 'disparity': '이격도', 'momentum': '모멘텀',
    'investor-flow-custom': '수급 결합', 'benchmark': '매수 후 보유',
}
COLORS = ['#3267c9', '#a443ad', '#058675', '#e58c19', '#8d663a', '#e64462', '#38a5bc', '#17243b']
CSS = '''
*{box-sizing:border-box}body{margin:0;background:#f3f5f9;color:#17243b;font:15px/1.8 -apple-system,BlinkMacSystemFont,"Apple SD Gothic Neo","Malgun Gothic",sans-serif}
main{max-width:1260px;margin:auto;padding:30px 24px}a{color:#235fd0;text-underline-offset:4px}nav{display:flex;gap:20px;flex-wrap:wrap}.hero{padding:30px;border-radius:18px;background:#17243b;color:white;margin:24px 0}.hero h1{font-size:32px;margin:0}.hero p{color:#cad7eb}
.panel{background:white;border:1px solid #dce3ec;border-radius:16px;padding:28px;margin:22px 0}h2{margin:0 0 12px;font-size:23px}h3{font-size:19px;margin:25px 0 12px}p{margin:12px 0}.muted{font-size:13px;color:#58667b}.stats{display:grid;grid-template-columns:repeat(4,1fr);gap:12px}.stat{background:#eef3fb;border-radius:10px;padding:18px}.stat strong{font-size:25px;display:block}.table-wrap{overflow:auto;margin:18px 0;border:1px solid #dce3ec;border-radius:10px}table{border-collapse:collapse;width:100%;font-size:14px}th,td{padding:10px 12px;text-align:left;border-bottom:1px solid #dce3ec;white-space:nowrap}th{background:#eef2f8}tr:last-child td{border-bottom:0}tbody tr:nth-child(even){background:#fafbfd}.num{text-align:right;font-variant-numeric:tabular-nums}.positive{color:#06715d}.negative{color:#b43d4d}details{border-top:1px solid #dce3ec;margin-top:12px}summary{padding:15px 0;cursor:pointer;font-weight:650}svg{width:100%;height:auto;display:block}.legend{display:flex;flex-wrap:wrap;gap:12px;font-size:13px}.legend span:before{content:'━';color:var(--color);margin-right:5px}footer{color:#58667b;font-size:13px}
@media(max-width:700px){main{padding:16px 12px}.panel,.hero{padding:20px}.hero h1{font-size:26px}.stats{grid-template-columns:repeat(2,1fr)}}
@media print{body{background:white}main{padding:0}.panel{border:0}.hero{background:white;color:#17243b}.hero p{color:#58667b}nav{display:none}thead{display:table-header-group}tr{break-inside:avoid}}
'''


def number(value, suffix='%'):
    return f'{float(value):+,.2f}{suffix}'


def table(headers, rows):
    return '<div class="table-wrap"><table><thead><tr>' + ''.join(f'<th scope="col">{escape(h)}</th>' for h in headers) + '</tr></thead><tbody>' + ''.join('<tr>' + ''.join(f'<td>{c}</td>' for c in row) + '</tr>' for row in rows) + '</tbody></table></div>'


def performance(value, suffix='%'):
    return f'<span class="{"positive" if float(value)>=0 else "negative"}">{number(value,suffix)}</span>'


def chart(series, title):
    """Use every observed day with the ending return in each SVG line title."""
    values = [v for points in series.values() for _, v in points] + [0]
    low, high = min(values), max(values)
    pad = max((high-low)*.06, 1); low-=pad; high+=pad
    w,h,left,right,top,bottom = 1100,360,70,22,20,45
    y = lambda v: top+(high-v)/(high-low)*(h-top-bottom)
    n=len(next(iter(series.values())))
    x = lambda i: left+i/max(n-1,1)*(w-left-right)
    svg=f'<svg role="img" aria-label="{escape(title)}" viewBox="0 0 {w} {h}"><title>{escape(title)}</title>'
    for i in range(5):
        value=low+(high-low)*i/4
        svg+=f'<line x1="{left}" x2="{w-right}" y1="{y(value):.2f}" y2="{y(value):.2f}" stroke="#e2e7ef"/><text x="{left-8}" y="{y(value)+4:.2f}" text-anchor="end" font-size="12" fill="#58667b">{value:.0f}%</text>'
    svg+=f'<line x1="{left}" x2="{w-right}" y1="{y(0):.2f}" y2="{y(0):.2f}" stroke="#94a3b8"/>'
    legend='<div class="legend">'
    for sid,points in series.items():
        color=COLORS[list(NAMES).index(sid)]
        path=' '.join(f'{x(i):.2f},{y(value):.2f}' for i,(_,value) in enumerate(points))
        dash=' stroke-dasharray="7 5"' if sid=='benchmark' else ''
        svg+=f'<polyline fill="none" stroke="{color}" stroke-width="2" points="{path}"{dash}><title>{NAMES[sid]} · {number(points[-1][1])}</title></polyline>'
        legend+=f'<span style="--color:{color}">{NAMES[sid]} {number(points[-1][1])}</span>'
    dates=next(iter(series.values()))
    for i in [0,(n-1)//2,n-1]:
        svg+=f'<text x="{x(i):.2f}" y="{h-15}" text-anchor="middle" font-size="12" fill="#58667b">{escape(dates[i][0])}</text>'
    return svg+'</svg>'+legend+'</div>'


def strategy_table(rows, data_href, period, symbol):
    result=[]
    for r in rows:
        prefix=f'{data_href}/{symbol}_{r["strategy_id"]}_{period}'
        links=' · '.join(f'<a href="{prefix}_{key}.csv" download>{label}</a>' for key,label in [('summary','요약'),('trades','거래'),('equity','평가금액'),('signals','신호')])
        win=f'{float(r["win_rate_pct"]):.1f}%' if r['trade_count'] else '—'
        result.append([NAMES[r['strategy_id']],performance(r['total_return_pct']),performance(r['excess_return_pp'],'%p'),f'{r["max_drawdown_pct"]:.2f}%',str(r['trade_count']),win,f'{r["invested_observation_pct"]:.1f}%',links])
    return table(['전략','수익률','보유 대비 차이','최대낙폭','거래 수','승률','투자 관측일 비중','CSV 근거'],result)


def render(data, folder, data_href):
    summaries=data['summaries']; portfolios=data['portfolio_summaries']
    full=[r for r in portfolios if r['evaluation_period']=='full']
    best=max(full,key=lambda r:r['total_return_pct']); benchmark=full[0]['benchmark_return_pct']
    body=f'<section class="panel"><div class="stats"><div class="stat">전체 기간<strong>{data["full_rows"]}거래일</strong></div><div class="stat">실행 수<strong>{len(summaries)}회</strong></div><div class="stat">최고 전략 · {NAMES[best["strategy_id"]]}<strong>{number(best["total_return_pct"])}</strong></div><div class="stat">매수 후 보유<strong>{number(benchmark)}</strong></div></div>'
    body+=f'<p>16종목에 같은 초기금액을 배분한 포트폴리오에서는 모든 전략이 매수 후 보유 수익률에 못 미쳤습니다. 최고 수익률 전략은 {NAMES[best["strategy_id"]]}이며 보유 대비 차이는 {number(best["excess_return_pp"],"%p")}입니다. 반면 모든 전략의 최대낙폭은 매수 후 보유보다 작았습니다.</p><p>모멘텀은 전체 기간 16종목 중11종목에서 보유 수익률을 넘었으나 지표 준비 이후에는9종목으로 줄었습니다. 수익과 손실폭을 함께 비교해야 합니다.</p>'
    body+='<p class="muted">실제 수익률 비교 기준은 수집된 KIS 수정종가의 가격 변화입니다. 계좌 체결 수익률·배당 포함 총수익률과는 구별됩니다. 7종 기본 설정 중 평균회귀와 이격도는 동일 규칙·동일 결과입니다.</p></section>'
    body+='<section class="panel"><h2>성과 차이를 어떻게 읽을까</h2><p>모멘텀은 삼성전자에서 +369.72%로 보유 +312.01%를 넘었지만, SK하이닉스에서는 +580.81%로 보유 +756.00%에 못 미쳤습니다. 종목별 보유 초과 건수가 많아도 큰 상승 종목의 수익 차이가 합산 성과에 영향을 줍니다.</p><p>삼성SDI의 추세 필터는 +185.41%로 보유 +59.61%보다 높았고, LG에너지솔루션 RSI는 +50.01%로 보유 −1.97%를 넘었습니다. 삼성바이오로직스는 사후 최고 전략인 평균회귀/이격도도 −10.26%여서 보유 −20.62%보다 손실이 작았을 뿐 수익을 낸 것은 아닙니다.</p><p>전략별 승률은 전체 수익률과 함께 봐야 합니다. 삼성전자 RSI의 승률은100%지만 수익률은 +33.50%로 보유 수익률보다 낮았습니다. 높은 승률·낮은 낙폭·많은 보유 초과 종목은 각각 다른 특성을 나타냅니다.</p></section>'
    body+=f'''<section class="panel" id="method"><h2>계산 기준과 해석</h2>
<p>전체 기간은 {data['full_start']}~{data['end_date']}({data['full_rows']}거래일), 공통 준비 이후 기간은 {data['common_start']}~{data['end_date']}({data['common_rows']}거래일)입니다. 10/13 수집 당시 장중 가격은 제외했습니다. 전략 지표는 전체 데이터로 계산하고, 준비 이후 비교는 해당 시작일에 현금으로 새로 실행했습니다. 이전 기간 포지션은 이어받지 않습니다.</p>
<ul><li>전략별 초기자금100만원, 매수 시 전액 투자·소수점 주식 허용, 매도 후 현금 보유, 매도 신호는 공매도 없이 보유분 청산에만 사용합니다.</li>
<li>당일 신호는 다음 거래일 종가에 체결합니다. 마지막 날 남은 포지션과 마지막 날 매도 신호는 종료 종가로 청산합니다. 비교 기준은 시작일 종가 매수→종료일 종가 매도입니다.</li>
<li>수수료·거래세·슬리피지·배당·현금 이자는0입니다. 수익률은 거래별 수익률을 복리로 연결하고, 최대낙폭은 보유 중 평가금액을 포함한 일별 곡선에서 계산합니다.</li>
<li>포트폴리오는16종목 동일 초기 배분, 종목 간 재배분 없음입니다. 포트폴리오 최대낙폭은 합산 평가금액 곡선으로 계산했습니다. 승률은 수익 거래/청산 거래이며, 투자 관측일 비중은 종가 평가 때 보유 또는 청산 상태인 날의 비중입니다.</li>
<li>지표 준비 이후에도 삼성바이오로직스 RSI가4일 결측입니다. 앱의 단순14일 평균 RSI가 평균 하락폭0을 결측으로 처리하며 해당일에는 RSI 신호가 관망입니다. 기존 전략 계산을 그대로 사용했습니다.</li>
<li>수급 전략은 관측일로 가격과 결합했습니다. 과거 시점의 공개 시각·정정 전 수급값은 확인하지 못했으므로 당시 실시간으로 실행 가능했던 성과로 단정할 수 없습니다.</li>
<li>현재 선택된16종목과 한 기간의 사후 비교입니다. 생존 편향·표본 선택 및 기간 민감도가 있으며, 최고 전략의 사후 선택은 미래 성과의 검증이 아닙니다. 별도 구간 검증·비용 반영·파라미터 탐색은 수행하지 않았습니다.</li></ul>
<p class="muted">기본 설정: 골든크로스5/20일선; RSI≤30 매수·≥70 매도; 추세 필터60일선과 직전 종가; 평균회귀 종가/20일선≤0.97 매수·≥1.03 매도; 이격도≤97/≥103; 모멘텀20일 수익률≥10%/≤−10%; 수급 결합 외국인·기관 순매수 방향과20일선.</p></section>'''
    for period,title,start in [('full','전체 기간',data['full_start']),('common_ready','지표 준비 이후',data['common_start'])]:
        rows=[r for r in portfolios if r['evaluation_period']==period]
        body+=f'<section class="panel" id="{period}"><h2>{title} · 포트폴리오 비교</h2><p>{start}~{data["end_date"]} · 보유 수익률 {number(rows[0]["benchmark_return_pct"])} · 보유 최대낙폭 {rows[0]["benchmark_mdd_pct"]:.2f}%</p>'
        body+=table(['전략','수익률','보유 대비 차이','최대낙폭','보유 초과 종목','수익 종목','거래 합계'],[[NAMES[r['strategy_id']],performance(r['total_return_pct']),performance(r['excess_return_pp'],'%p'),f'{r["max_drawdown_pct"]:.2f}%',f'{r["outperform_count"]}/16',f'{r["profitable_count"]}/16',str(r['trade_count'])] for r in rows])
        series={r['strategy_id']:[[d,(v/data['initial_equity']-1)*100] for d,v,_ in r['history']] for r in rows}
        series['benchmark']=[[d,(v/data['initial_equity']-1)*100] for d,_,v in rows[0]['history']]
        body+=chart(series,title+' 포트폴리오 누적 수익률')+'</section>'
    body+='<section class="panel"><h2>종목별 전체 기간 · 사후 최고 성과</h2><p class="muted">7개 전략 중 최고 수익률을 사후 선택한 표입니다. 최고 결과가 같으면 평균회귀/이격도의 동일성을 포함해 함께 표시했습니다.</p>'
    top=[]
    symbols=list(dict.fromkeys(r['symbol'] for r in summaries))
    for symbol in symbols:
        rows=[r for r in summaries if r['symbol']==symbol and r['evaluation_period']=='full']; b=max(rows,key=lambda r:r['total_return_pct'])
        winners=' / '.join(NAMES[r['strategy_id']] for r in rows if abs(r['total_return_pct']-b['total_return_pct'])<1e-8)
        top.append([f'<a href="#stock-{symbol}">{escape(b["symbol_name"])} ({symbol})</a>',performance(b['benchmark_return_pct']),winners,performance(b['total_return_pct']),performance(b['excess_return_pp'],'%p'),f'{b["max_drawdown_pct"]:.2f}%',str(b['trade_count'])])
    body+=table(['종목','매수 후 보유','사후 최고 전략','전략 수익률','보유 대비 차이','최대낙폭','거래 수'],top)+'</section>'
    body+='<section class="panel"><h2>종목별 7개 전략 상세와 거래 근거</h2><p>종목을 펼쳐 수익률·낙폭·승률·실제 백테스트 거래를 확인하세요. 곡선은 모든 거래일을 포함하며 평균회귀/이격도는 겹칩니다. 준비 이후 결과도 별도로 펼칠 수 있습니다.</p>'
    for symbol in symbols:
        rows=[r for r in summaries if r['symbol']==symbol and r['evaluation_period']=='full']
        body+=f'<details id="stock-{symbol}"><summary>{escape(rows[0]["symbol_name"])} ({symbol}) · 보유 {number(rows[0]["benchmark_return_pct"])}</summary>'
        for period,title in [('full','전체 기간'),('common_ready','지표 준비 이후')]:
            if period=='common_ready': body+='<details><summary>지표 준비 이후 재실행 결과 · 426거래일</summary>'
            rset=[r for r in summaries if r['symbol']==symbol and r['evaluation_period']==period]
            bundle=next(b for b in data['bundles'] if b['symbol']==symbol and b['evaluation_period']==period)
            body+=f'<h3>{title}</h3><p>매수 후 보유 {number(rset[0]["benchmark_return_pct"])} · 최대낙폭 {rset[0]["benchmark_mdd_pct"]:.2f}%</p>'
            body+=strategy_table(rset,data_href,period,symbol)+chart({**bundle['curves'],'benchmark':bundle['benchmark_curve']},rows[0]['symbol_name']+' '+title+' 누적 수익률')
            if period=='common_ready': body+='</details>'
        body+='<details><summary>전체 기간 전략별 최근 청산 거래3건</summary>'
        trade_rows=[]
        for sid in list(NAMES)[:-1]:
            with (folder/f'{symbol}_{sid}_full_trades.csv').open() as f: trades=list(csv.DictReader(f))
            for t in trades[-3:]:
                trade_rows.append([NAMES[sid],escape(t['entry_signal_date'])[:10],escape(t['entry_date'])[:10],f'{float(t["entry_price"]):,.0f}',escape(t['exit_date'])[:10],f'{float(t["exit_price"]):,.0f}',performance(t['return_pct']),'종료일 청산' if t['exit_reason'] in ('final_close','sell_signal_final_close') else '매도 신호'])
        body+=table(['전략','진입 신호일','진입일','진입가격','청산일','청산가격','거래 수익률','청산 사유'],trade_rows)+'</details></details>'
    body+='</section>'
    body+=f'<section class="panel"><h2>전체 결과 다운로드</h2><p><a href="{data_href}/comparison_summary.csv" download>224회 요약 CSV</a> · <a href="{data_href}/portfolio_summary.csv" download>포트폴리오 비교 CSV</a> · <a href="{data_href}/comparison.json" download>전체 곡선·설정 JSON</a> · <a href="backtest-comparison-2026-10-13.zip" download>HTML·가격·수급·거래 근거 ZIP</a></p><p class="muted">종목별 표의 CSV에는 전체 거래·신호·일별 평가금액과 같은 기간의 비교 기준 평가금액이 포함됩니다. 요약 및 거래 결과는 배포 DB의 backtest_summaries / backtest_trades에도 저장했습니다. 검증: 224회 거래 복리·평가곡선·요약 수익률 및 MDD 일치.</p></section>'
    return '<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>16종목 전략 백테스트와 실제 가격 수익률 비교</title><style>'+CSS+'</style></head><body><main><nav><a href="index.html">리포트 목록</a><a href="two-year-history-2026-10-13.html">2년 데이터 분석</a><a href="#method">계산 기준</a><a href="#full">전체 기간</a><a href="#common_ready">지표 준비 이후</a></nav><header class="hero"><h1>전략 백테스트와 실제 가격 수익률 비교</h1><p>16종목 × 7전략 × 2기간 · 기준일2026.10.12 · 작성일2026.10.13</p></header>'+body+'<footer>출처: 수집된 KIS 수정주가·투자자별 일별 수급 및 invest_bot의 기존7종 전략·백테스트 엔진. 결과는 해당 저장 snapshot과 기본 설정에 대한 시뮬레이션입니다.</footer></main></body></html>'


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input',type=Path,default=Path('data/backtests/2026-10-13'))
    parser.add_argument('--output',type=Path,default=Path('data/reports/backtest-comparison-2026-10-13.html'))
    parser.add_argument('--data-href',default='../backtests/2026-10-13')
    args=parser.parse_args()
    data=json.loads((args.input/'comparison.json').read_text())
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(render(data,args.input,args.data_href),encoding='utf-8')
    print(args.output.resolve())


if __name__=='__main__':
    main()
