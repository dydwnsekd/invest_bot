"""Render source-backed earnings context, US sensitivity and overlay experiments."""
from __future__ import annotations
import argparse
import json
import sys
from collections import defaultdict
from html import escape
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.render_rolling_backtest_report import CSS, JS, html_table, performance, mdd, price_revision_notice

DATE = '2026-10-19'
PRICE_DATE = '2026-10-13'
FACTORS = {'SP500':'S&P500', 'NASDAQCOM':'나스닥', 'NASDAQSOX':'SOX 반도체', 'VIXCLS':'VIX', 'DGS10':'미국10년금리'}
MODES = {'base':'기존', 'us':'미국 보류', 'earnings':'실적 발표 보류', 'combined':'둘 다 보류'}
EXTRA_CSS = '''
.heat{font-variant-numeric:tabular-nums;text-align:right}.metric-note{max-width:70ch}.source-link{font-size:12px}.keyline{font-size:19px;font-weight:700;line-height:1.65}.metric-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px}.metric-grid>*{min-width:0}.issuer-note{white-space:normal;max-width:360px;min-width:200px}.search-box{font:inherit;padding:9px 12px;border:1px solid #bcc8d8;border-radius:7px;max-width:100%}.source-list li{overflow-wrap:anywhere}.intro-date{font-weight:700;color:#9b4e00}.table-wrap:focus-visible{outline:2px solid #2563eb}.scatter{width:100%;max-width:650px}.scenario{border-left:3px solid #2563eb;padding-left:14px}.fine{font-size:12px;color:#617087}
@media(max-width:600px){.metric-grid{grid-template-columns:1fr}#overlay-explorer .stats{grid-template-columns:repeat(2,minmax(0,1fr))}.hero h1{font-size:26px}}
'''

EXPLORER_JS = r'''
(() => {
 const packet=document.getElementById('overlay-explorer-data'); if(!packet)return;
 const data=JSON.parse(packet.textContent), family=document.getElementById('overlay-family'), window=document.getElementById('overlay-window'), model=document.getElementById('overlay-model'), search=document.getElementById('overlay-search'), table=document.getElementById('overlay-stock-table');
 const groups=new Map();data.rows.forEach(row=>{const key=`${row[0]}:${row[1]}:${row[2]}`;groups.set(key,row);});
 const option=(select,value,label)=>{const el=document.createElement('option');el.value=value;el.textContent=label;select.append(el);};
 const key=w=>w.kind==='rolling'?`rolling:${w.length}`:w.kind;
 const familyKeys=[...new Set(data.windows.map(key))];
 const fullWindow=data.windows.find(w=>w.kind==='full');
 familyKeys.sort((a,b)=>{const order=v=>v==='recent'?-1:v.startsWith('rolling:')?Number(v.split(':')[1]):Number.MAX_SAFE_INTEGER;return order(a)-order(b);});
 familyKeys.forEach(v=>option(family,v,v==='recent'?'최근 구간':v==='full'?`전체 ${fullWindow?.length??''}거래일`.trim():`슬라이딩 ${v.split(':')[1]}거래일`));
 data.models.forEach((m,i)=>option(model,String(i),m.name));
 const fmt=(v,pp=false)=>v==null?'—':`${v>=0?'+':''}${v.toLocaleString('ko-KR',{minimumFractionDigits:2,maximumFractionDigits:2})}${pp?'%p':'%'}`;
 const draw=()=>{
   const wi=Number(window.value),mi=Number(model.value),w=data.windows[wi];if(!w)return;
   const q=search.value.trim().toLocaleLowerCase('ko-KR');let count=0,better=0;
   table.tBodies[0].replaceChildren();
   data.stocks.forEach((stock,si)=>{
     if(!`${stock.name} ${stock.symbol}`.toLocaleLowerCase('ko-KR').includes(q))return;
     const r=groups.get(`${wi}:${mi}:${si}`);if(!r)return;
     const tr=document.createElement('tr');tr.dataset.originalOrder=String(si+1);
     const a=document.createElement('a');a.href=`#stock-${stock.symbol}`;a.dataset.stockDetail=stock.symbol;a.textContent=stock.name;tr.insertCell().append(a);tr.insertCell().textContent=stock.symbol;
     const values=[r[3][0],r[4][0],r[5][0],r[6][0],r[6][0]-r[3][0],Math.abs(r[3][1]),Math.abs(r[6][1]),r[3][2],r[6][2],r[7]];
     values.forEach((value,i)=>{const td=tr.insertCell();td.dataset.sortValue=String(value);td.textContent=(i===7||i===8)?`${value}회`:fmt(value,i===4).replace(i===5||i===6?/^\+/:/$^/,'');td.className='num';if(i<5)td.classList.add(value>=0?'positive':'negative');});
     table.tBodies[0].append(tr);count++;if(r[6][0]>r[3][0]+1e-8)better++;
   });
   table.dispatchEvent(new Event('report:rows-changed'));
   document.getElementById('overlay-caption').textContent=`${w.start_date} ~ ${w.end_date} · ${data.models[mi].name} · ${count}종목 표시 · 결합 보류의 수익률 개선 ${better}종목`;
   document.getElementById('overlay-empty').hidden=count>0;table.hidden=count===0;
 };
 const windows=()=>{window.replaceChildren();data.windows.map((w,i)=>({w,i})).filter(({w})=>key(w)===family.value).sort((a,b)=>b.w.end_date.localeCompare(a.w.end_date)).forEach(({w,i})=>option(window,String(i),`${w.start_date} ~ ${w.end_date}`));draw();};
 family.value=familyKeys.includes('rolling:20')?'rolling:20':familyKeys[0];const momentum=data.models.findIndex(m=>m.id==='momentum');model.value=String(momentum>=0?momentum:0);
 family.addEventListener('change',windows);window.addEventListener('change',draw);model.addEventListener('change',draw);search.addEventListener('input',draw);windows();
 const factorPacket=JSON.parse(document.getElementById('factor-period-data').textContent),periodSelect=document.getElementById('factor-period');
 const factorLookup=new Map(factorPacket.rows.map(r=>[`${r.window_id}:${r.symbol}:${r.factor}`,r]));
 const periodLabels=new Map(factorPacket.rows.map(r=>[r.window_id,`${r.length}거래일 · ${r.start_date} ~ ${r.end_date}`]));
 periodLabels.forEach((label,id)=>option(periodSelect,id,label));periodSelect.value=periodLabels.has('common-history')?'common-history':periodLabels.keys().next().value;
 const factorNumber=v=>v==null?'—':v.toFixed(2);
 periodSelect.addEventListener('change',()=>{
   const factors=['SP500','NASDAQCOM','NASDAQSOX','VIXCLS','DGS10'];
   document.querySelectorAll('#us-table tbody tr').forEach(row=>{
     const symbol=row.dataset.symbol;let count=0;
     factors.forEach((factor,i)=>{const r=factorLookup.get(`${periodSelect.value}:${symbol}:${factor}`),value=r?.correlation;count=r?.n??0;const cell=row.cells[i+1];cell.textContent=factorNumber(value);cell.dataset.sortValue=value==null?'':String(value);cell.style.background=`rgba(${value>=0?'37,99,235':'190,62,89'},${value==null?0:.06+Math.abs(value)*.5})`;});
     const partial=factorLookup.get(`${periodSelect.value}:${symbol}:NASDAQSOX`)?.partial_correlation;
     row.cells[6].textContent=factorNumber(partial);row.cells[6].dataset.sortValue=partial==null?'':String(partial);row.cells[7].textContent=String(count);
   });document.getElementById('us-table').dispatchEvent(new Event('report:rows-changed'));
 });
 document.querySelectorAll('[data-stock-search]').forEach(input=>input.addEventListener('input',()=>{const target=document.getElementById(input.dataset.stockSearch);target.querySelectorAll('[data-search]').forEach(row=>{row.hidden=!row.dataset.search.toLowerCase().includes(input.value.trim().toLowerCase());});}));
})();
'''


def num(value, digits=2):
    return '—' if value is None else f'{value:,.{digits}f}'


def perf(value, points=False):
    return '—' if value is None else performance(value, points=points)


def financial(value):
    return '미확인' if value is None else f'{value / 1000:,.4f}조원'


def source_links(row):
    return ' · '.join(f'<a class="source-link" href="{escape(s["url"],quote=True)}" target="_blank" rel="noopener">{escape(s["title"])}</a>' for s in row.get('sources', []))


def safe_json(value):
    return json.dumps(value, ensure_ascii=False, separators=(',', ':'), allow_nan=False).replace('&','\\u0026').replace('<','\\u003c').replace('>','\\u003e').replace('\u2028','\\u2028').replace('\u2029','\\u2029')


def report_context(data, report_date=None, data_href=None):
    meta=data.get('metadata',{})
    resolved_date=str(report_date or meta.get('as_of') or DATE)
    price_as_of=str(meta.get('price_as_of') or PRICE_DATE)
    return resolved_date,price_as_of,data_href or f'../earnings-us/{resolved_date}'


def report_facts(data):
    meta=data.get('metadata',{});common=[r for r in data.get('factors',[]) if r.get('window_id')=='common-history']
    return {
        'event_count':len(data.get('events',[])) or int(meta.get('verified_event_count') or 0),
        'common_start':min((str(r.get('start_date','')) for r in common if r.get('start_date')),default=str(meta.get('eligible_start',''))),
        'common_end':max((str(r.get('end_date','')) for r in common if r.get('end_date')),default=str(meta.get('price_as_of',''))),
        'common_n':max((int(r.get('n') or 0) for r in common),default=0),
        'full_length':max((int(r.get('length') or 0) for r in data.get('portfolio_results',[]) if r.get('kind')=='full'),default=0),
        'rolling_lengths':sorted({int(r['length']) for r in data.get('aggregates',[]) if r.get('length')}),
    }


def explorer_payload(data):
    models=data['models'];windows=data['windows'];stocks=sorted({(r['symbol'],r['symbol_name']) for r in data['stock_results']})
    wi={w['id']:i for i,w in enumerate(windows)};mi={m['id']:i for i,m in enumerate(models)};si={s:i for i,(s,_) in enumerate(stocks)}
    grouped=defaultdict(dict)
    for row in data['stock_results']:grouped[(row['window_id'],row['base_model'],row['symbol'])][row['overlay']]=row
    rows=[]
    for (window,model,symbol),policies in grouped.items():
        base=policies['base'];values=[[policies[mode]['net_return_pct'],policies[mode]['net_mdd_pct'],policies[mode]['trade_count']] for mode in MODES]
        rows.append([wi[window],mi[model],si[symbol],*values,base['bh_net_return_pct']])
    return dict(windows=windows,models=models,stocks=[dict(symbol=s,name=n) for s,n in stocks],rows=rows)


def render(data, report_date=None, data_href=None):
    meta=data['metadata'];model_names={m['id']:m['name'] for m in data['models']}
    report_date,price_as_of,data_href=report_context(data,report_date,data_href)
    facts=report_facts(data)
    common=[r for r in data['factors'] if r['window_id']=='common-history']
    names={r['symbol']:r['symbol_name'] for r in data['stock_results']};issuers={r['issuer_symbol']:r for r in data['issuers']}
    correlations={(r['symbol'],r['factor']):r for r in common}
    event_count=facts['event_count'];common_start=facts['common_start'];common_end=facts['common_end'];common_n=facts['common_n']
    full_length=facts['full_length'];rolling_lengths=facts['rolling_lengths']
    cost_pct=float(meta.get('cost_rate') or 0)*100
    us_last=max((str(r.get('last_date','')) for r in meta.get('us_coverage',[]) if r.get('last_date')),default='미확인')
    top=max((r for r in common if r['factor'] in ('SP500','NASDAQCOM','NASDAQSOX') and r['correlation'] is not None),key=lambda r:abs(r['correlation']))
    full=[r for r in data['portfolio_results'] if r['kind']=='full']
    and_base=next(r for r in full if r['base_model']=='mix-mt-and' and r['overlay']=='base')
    and_combined=next(r for r in full if r['base_model']=='mix-mt-and' and r['overlay']=='combined')
    body=f'''<section class="panel" id="summary"><h2>실적과 미국 시장을 함께 읽은 결과</h2>
<p class="keyline">미국 반도체 지수와의 동행성은 확인되지만, 미국·실적 보류 조건이 전략 수익을 일관되게 높이지는 않았습니다.</p>
<div class="stats"><div class="stat"><span>대상</span><strong>{len(names)}종목 · {len(issuers)}기업</strong></div><div class="stat"><span>실적 발표일 표본</span><strong>{event_count}건</strong></div><div class="stat"><span>미국 요인</span><strong>{len(FACTORS)}개 · {common_start}~{common_end}</strong></div><div class="stat"><span>재검증</span><strong>{len(model_names)}전략 × {len(MODES)}조건</strong></div></div>
<p><strong>확인된 동행성:</strong> 공통 분석 기간에서 {escape(top['symbol_name'])}와 {FACTORS[top['factor']]}의 시차 상관은 {num(top['correlation'])}, 같은 날 KODEX200을 통제한 잔여 상관은 {num(top['partial_correlation'])}입니다. 상관은 원인이나 다음날 예측 정확도를 뜻하지 않습니다.</p>
<p><strong>조건 추가의 실제 결과:</strong> 모멘텀·추세 AND는 전체 기간 비용 후 수익률이 {perf(and_base["net_return_pct"])} → {perf(and_combined["net_return_pct"])}로 바뀌었고, MDD는 {mdd(and_base["net_mdd_pct"])} → {mdd(and_combined["net_mdd_pct"])}였습니다. 정보를 더 넣는 것과 수익 개선은 별도로 검증해야 합니다.</p>
<p><strong>실적 해석:</strong> 발표한 분기 실적·잠정 여부·발표 날짜를 종목별로 붙였습니다. 전년 대비 증익은 예상 대비 서프라이즈와 다릅니다. 당시 컨센서스가 없어 beat/miss 점수는 계산하지 않았습니다.</p>
<div class="callout warning"><strong>날짜를 구분하세요.</strong> 조사 기준일 {escape(report_date)}, 국내 가격·전략 비교 종료일 {escape(price_as_of)}. 미국 원자료는 시리즈별 최대 {escape(us_last)}까지 확보했지만 과거 검증은 한국 장이 열리기 전에 알려진 관측만 사용합니다. {escape(price_as_of)} 이후 국내 주가 반응은 이 보고서에 포함하지 않습니다.</div>
{price_revision_notice(meta)}
<p class="muted">수익률은 {len(names)}종목 동일 초기배분·매수/매도 편도{cost_pct:.2f}% 비용·다음 종가 체결 기준입니다. 후보 규칙을 본 과거 자료에서 확인한 탐색 실험이며 미래 독립 검증은 아닙니다.</p></section>'''
    # Main causal map distinguishes supported earnings facts from transmission hypotheses.
    channels=[['반도체 · 삼성전자/SK하이닉스','SOX·AI 투자 → 제품 수요/기대','메모리·HBM 수요와 매출/영업이익','SOX 상관과 실적 성장 모두 확인하되 국내시장 공통 움직임도 비교'],['자동차 · 현대차/기아','미국 수요·할인율 → 판매·믹스','북미 판매·HEV·원가·수익성','매출 증가와 영업이익 감소를 구분, 원화 환율은 이번 모형에 미포함'],['배터리 · LGES/삼성SDI','미국 EV/ESS 투자 → 가동률·지원금','영업이익·북미 세액공제·제품 믹스','세액공제 포함 이익과 본업 수익을 분리해 후속 확인'],['플랫폼 · NAVER/카카오','미국 기술주 기대·할인율 → 밸류에이션','광고·커머스·클라우드/톡비즈 성장','나스닥 동행과 자체 실적의 괴리 확인'],['금융 · KB/신한','금리·위험선호 → 할인율/신용비용','분기 그룹 순이익·대손비용·자본','산업주 매출/영업이익과 순위 비교하지 않음'],['소재·조선·방산·바이오','글로벌 위험선호 + 고유 수주/수요','POSCO·HD현대중공업·한화·바이오의 고유 실적','광범위 미국 지수 상관만으로 산업별 수주·정책·제품 효과를 설명하지 않음']]
    body+='<section class="panel" id="channels"><h2>미국 시장에서 종목 실적으로 이어지는 경로</h2><p class="muted">아래 전달 경로는 분석 가설입니다. 수요·매출·이익에 대한 사실은 뒤의 발행사 자료로 확인하고, 가격 동행성은 별도 통계로 측정했습니다.</p>'+html_table(['종목군','전달 가설','먼저 볼 지표','해석과 확인점'],[[escape(v) for v in row] for row in channels])+'</section>'
    rows=[];attrs=[]
    for symbol,name in names.items():
        row=issuers.get('005380' if symbol=='005385' else symbol,{})
        bank=symbol in ('105560','055550')
        latest='그룹 분기 순이익 '+financial(row.get('net_profit_krw_billion')) if bank else '영업이익 '+financial(row.get('operating_profit_krw_billion'))
        note='은행 그룹 분기 순이익; 지배주주 귀속 여부 별도 확인' if bank else '잠정 발표' if row.get('status')=='preliminary' else '발표자료 기준'
        rows.append([f'<a href="#stock-{symbol}" data-stock-detail="{symbol}">{escape(name)}</a>',symbol,escape(row.get('period','미확인')),escape(row.get('release_date','미확인')),financial(row.get('revenue_krw_billion')),latest,perf(row.get('revenue_yoy_pct')),perf(row.get('operating_profit_yoy_pct')),escape(note),source_links(row)])
        attrs.append(f' data-search="{escape(name)} {symbol}"')
    body+=f'<section class="panel" id="earnings"><h2>{len(names)}종목의 최신 실적 발표</h2><p>연결 분기값, 금액은 조원입니다. 같은 발행사의 보통주·우선주는 기업 실적을 공유하며 주가 반응은 각각 계산합니다. 금융주는 그룹 분기 순이익을 따로 표시합니다. 자료가 없는 값은 미확인으로 남깁니다.</p><label>종목 검색 <input class="search-box" data-stock-search="earnings-table" placeholder="종목명 또는 코드"></label>'+html_table(['종목','코드','실적 분기','발표일','분기 매출','분기 이익','매출 YoY','영업이익 YoY','자료 상태','출처'],rows,table_id='earnings-table',row_attrs=attrs)+'<p class="muted">은행의 그룹 순이익 귀속 범위·당시 컨센서스·전체 EPS 일회성 조정 및 전체 컨퍼런스콜 녹취는 검증하지 못했습니다. 종목별 자료 정의와 원문 링크를 함께 확인하세요.</p></section>'
    refresh_notes=meta.get('refresh_notes') or []
    if refresh_notes:
        refresh_rows=[]
        for note in refresh_notes:
            source=f'<a href="{escape(str(note.get("source_url","")),quote=True)}" target="_blank" rel="noopener">원문</a>' if note.get('source_url') else '—'
            refresh_rows.append([escape(str(note.get('name') or note.get('issuer_symbol') or '')),escape(str(note.get('date') or '')),escape(str(note.get('kind') or '')),escape(str(note.get('note') or '')),source])
        checked_at=escape(str(meta.get('earnings_checked_at') or report_date))
        checked_count=int(meta.get('refresh_check_count') or len(issuers))
        body+='<section class="panel" id="source-refresh"><h2>최신 발표자료 재확인</h2>'+f'<p>{checked_at} 기준으로 {checked_count}개 발행사의 공식 발표 경로를 다시 확인했습니다. 아래 항목은 직전 보고서 이후 새로 확인했거나 분기 실적과 구분해 기록할 필요가 있는 자료입니다.</p>'+html_table(['기업','날짜','구분','반영 메모','출처'],refresh_rows)+'<p class="muted">영업 업데이트·수주 공시는 분기 손익 발표와 구분합니다. 실적 표에는 검증된 분기 실적만 반영합니다.</p></section>'
    heat=[];attrs=[]
    for symbol,name in names.items():
        cells=[f'<a href="#stock-{symbol}" data-stock-detail="{symbol}">{escape(name)}</a>']
        for factor in FACTORS:
            r=correlations[(symbol,factor)];c=r['correlation'];opacity=.06+abs(c or 0)*.5;color='37,99,235' if (c or 0)>=0 else '190,62,89'
            cells.append(f'<span class="heat" style="background:rgba({color},{opacity:.3f});padding:5px 10px;border-radius:5px">{num(c)}</span>')
        cells.extend([num(correlations[(symbol,'NASDAQSOX')]['partial_correlation']),str(correlations[(symbol,'SP500')]['n'])]);heat.append(cells);attrs.append(f' data-search="{escape(name)} {symbol}" data-symbol="{symbol}"')
    body+=f'<section class="panel" id="us-map"><h2>미국 시장 민감도 · 시차 상관</h2><p>기본 화면은 {escape(common_start)}~{escape(common_end)} 공통 준비 기간의 첫 종가 이후 {common_n:,}개 수익률 관측입니다. 기간을 바꾸면 해당 창의 첫 종가 이후 수익률을 비교하며, 유효 관측10개 미만은 상관을 표시하지 않습니다. 미국 변동은 직전 한국 개장부터 이번 개장 전까지 누적하며 한국 휴장 중 미국 거래도 포함합니다. 미국 휴장으로 새 종가가 없으면 구간 변화는0입니다.</p><label>상관 비교 기간 <select class="search-box" id="factor-period"></select></label> <label>종목 검색 <input class="search-box" data-stock-search="us-table" placeholder="삼성전자 또는 005930"></label>'+html_table(['종목',*FACTORS.values(),'국내시장 통제 후 SOX','관측 수'],heat,table_id='us-table',row_attrs=attrs)+'<p class="muted">색은 상관의 부호/크기만 표시합니다. 통제 후 값은 같은 날 KODEX200 수익률을 제거한 잔여 상관이며 미국 영향이 없다는 뜻은 아닙니다. 미국 요인끼리도 겹칩니다. 다중 비교·유의성 검정을 하지 않았고 인과효과·예측 성능으로 해석하지 않습니다.</p></section>'
    event_rows=[];attrs=[]
    for r in data['event_reactions']:
        event_rows.append([escape(r['symbol_name']),r['symbol'],r['date'],escape(r.get('period','')),perf(r['event_day_return_pct']),perf(r['post_1_return_pct']),perf(r['post_3_return_pct']),perf(r['post_5_return_pct']),perf(r['post_3_etf_diff_pp'],True),f'<a href="{escape(r["source_url"],quote=True)}" rel="noopener" target="_blank">발표 근거</a>'])
        attrs.append(f' data-search="{escape(r["symbol_name"])} {r["symbol"]} {r["date"]}"')
    body+=f'<section class="panel" id="events"><h2>실적 발표 전후 주가 반응</h2><p>확인된 발표일 표본만 사용했습니다. 발표 당일 열은 정확히 그 날짜에 거래한 경우의 종가 수익률이며 최초 공개 시각이 없어 발표 이전 움직임도 섞일 수 있습니다. 발표 다음1·3·5일은 발표 날짜가 완전히 지난 뒤 첫 국내 거래일부터 누적합니다. 미래 가격이 부족하면 —입니다.</p><label>종목·발표일 검색 <input class="search-box" data-stock-search="event-table" placeholder="종목명, 코드 또는 {escape(report_date[:7])}"></label>'+html_table(['종목','코드','발표일','분기','당일(설명용)','이후1일','이후3일','이후5일','이후3일 ETF 대비','근거'],event_rows,table_id='event-table',row_attrs=attrs)+f'<div class="callout warning">발표일 표본 {event_count}건은 {len(issuers)}기업의 과거 전체 실적 캘린더가 아닙니다. 동시 미국·국내 뉴스, 공시 정정·누출·실적 예상치의 영향을 분리하지 않았으므로 발표의 인과효과로 해석하지 않습니다. 휴장일 발표의 당일 수익률은 표시하지 않습니다.</div></section>'
    overview=[]
    by={(r['base_model'],r['overlay']):r for r in full}
    for mid in model_names:
        base=by[(mid,'base')]
        for mode in MODES:
            row=by[(mid,mode)]
            overview.append([escape(model_names[mid]),MODES[mode],perf(row['net_return_pct']),perf(row['net_return_pct']-base['net_return_pct'],True),mdd(row['net_mdd_pct']),str(row['trade_count']),num(row['mean_exposure_pct'])+'%'])
    aggregate=[]
    for length in rolling_lengths:
        for mid in model_names:
            group={r['model_id'].split(':')[-1]:r for r in data['aggregates'] if r['length']==length and r['model_id'].startswith(mid+':')}
            aggregate.append([f'{length}일',escape(model_names[mid]),* [perf(group[mode]['median_net_return_pct']) for mode in MODES],perf(group['combined']['median_net_return_pct']-group['base']['median_net_return_pct'],True),mdd(group['base']['median_net_mdd_pct']),mdd(group['combined']['median_net_mdd_pct'])])
    body+=f'<section class="panel" id="overlays"><h2>전략에 반영하면 성과가 좋아졌는가</h2><p>기존 {len(model_names)}개 전략에 두 가지 보류 규칙을 각각/함께 적용했습니다. 미국 조건은 한국 개장 사이 S&amp;P500 누적 변화가−1% 이하이거나 자료가 없을 때 해당일의 매수신호를 관망으로 바꿉니다. 실적 조건은 확인된 발표 날짜 다음3개 국내 거래일의 매수신호를 보류합니다. 매도는 유지합니다.</p><div class="callout warning"><strong>신호일과 체결일:</strong> 당일 보류한 신호는 다음 거래일 종가 체결에 영향을 줍니다. 전일에 이미 결정된 다음 종가 주문을 취소하는 규칙은 아닙니다. 실적 성장률·서프라이즈 점수를 매매 신호로 사용하지 않았고,−1%/3일 기준은 이 자료를 보고 만든 탐색 후보입니다.</div><h3>전체 {full_length:,}거래일 · 같은 초기 현금 시작</h3>'+html_table(['원전략','추가 조건','비용 후','기존 대비','MDD','거래 수','평균 투자 비중'],overview)+'<h3>슬라이딩 창별 중앙값</h3>'+html_table(['창','원전략','기존','미국 보류','실적 보류','결합 보류','결합−기존','기존 중앙MDD','결합 중앙MDD'],aggregate)+f'<p class="muted">각 창은 현금에서 새로 시작하며 중복 창의 수익률을 연결하지 않습니다. 동일 {len(names)}종목 초기배분, 매수·매도 각각 {cost_pct:.2f}%, 다음 종가 체결과 종료 청산을 유지했습니다. 새 규칙의 워크포워드/별도 미래 검증은 아직 없으며, 발표 목록이 불완전한 부분은 조건에 반영되지 않습니다.</p></section>'
    headers=['종목','코드','기존','미국 보류','실적 보류','결합 보류','결합−기존','기존MDD','결합MDD','기존 거래','결합 거래','매수 후 보유']
    body+='<section class="panel" id="overlay-explorer"><h2>기간·종목별 반영 전후 비교</h2><div class="filters"><label>기간 길이<select id="overlay-family"></select></label><label>평가 기간<select id="overlay-window"></select></label><label>원전략<select id="overlay-model"></select></label><label>종목 검색<input type="search" id="overlay-search" placeholder="종목명 또는 코드"></label></div><p id="overlay-caption" role="status"></p>'+html_table(headers,[],table_id='overlay-stock-table')+'<p id="overlay-empty" class="empty-state" hidden>일치하는 종목이 없습니다.</p><p class="muted">표 제목을 누르면 열 정렬이 가능합니다. 기간/전략을 바꿔도 정렬을 유지합니다. 종목명을 누르면 해당 기업 실적과 미국 민감도 상세가 펼쳐집니다.</p><noscript>기간 선택과 검색에는 JavaScript가 필요합니다. 위 표와 CSV로도 비교할 수 있습니다.</noscript><script type="application/json" id="overlay-explorer-data">'+safe_json(explorer_payload(data))+'</script></section>'
    body+='<section class="panel" id="stock-notes"><h2>종목별 함께 확인할 내용</h2>'
    for symbol,name in names.items():
        issuer=issuers.get('005380' if symbol=='005385' else symbol,{})
        rows=[]
        for factor in FACTORS:
            r=correlations[(symbol,factor)];unit='금리1bp' if factor=='DGS10' else '미국요인1%'
            rows.append([FACTORS[factor],num(r['correlation']),num(r['partial_correlation']),num(r['beta']),unit, num((r['r_squared'] or 0)*100)+'%' if r['r_squared'] is not None else '—'])
        body+=f'<details id="stock-{symbol}"><summary>{escape(name)} ({symbol})</summary><div><p><strong>{escape(issuer.get("period",""))} · 발표 {escape(issuer.get("release_date",""))}</strong> · 매출 {financial(issuer.get("revenue_krw_billion"))} · 영업이익 {financial(issuer.get("operating_profit_krw_billion"))}</p>'
        if symbol in ('105560','055550'):body+=f'<p>금융업 비교 지표: 그룹 분기 순이익 {financial(issuer.get("net_profit_krw_billion"))}. 산업주 영업이익과 직접 순위 비교하지 않습니다.</p>'
        if issuer.get('drivers'):body+='<p>발표자료의 주요 설명: '+escape(' / '.join(d.get('text','') if isinstance(d,dict) else d for d in issuer['drivers']))+'</p>'
        if issuer.get('net_profit_krw_billion') is not None and issuer.get('operating_profit_krw_billion') is not None and issuer['net_profit_krw_billion'] > issuer['operating_profit_krw_billion']:
            body+='<p>순이익이 영업이익을 초과합니다. 비영업·평가·세금 등 조정 내역을 대조하지 않아 순이익을 반복 가능한 본업 수익으로 사용하지 않았습니다.</p>'
        body+='<p class="fine">자료 정의: '+escape(issuer.get('metric_note',''))+'</p><p>'+source_links(issuer)+'</p>'+html_table(['미국 요인','원상관','KODEX 통제 후','단순 β','β당 기준 변화','단순 R²'],rows)+'<p class="muted">β는 과거 표본에서 미국 요인1단위 변화와 연결된 국내 수익률 %p입니다. 미래 예상수익이 아닙니다. 금리 이외 요인은 변화율%, 금리는 변화bp입니다. 기업별 컨센서스·밸류에이션·환율·개별 미국 고객/경쟁사 주가는 이번 모형에 넣지 않았습니다.</p></div></details>'
    body+='</section>'
    body+='<script type="application/json" id="factor-period-data">'+safe_json({'rows':data['factors']})+'</script>'
    coverage=[[FACTORS[r['series']],r['first_date'],r['last_date'],str(r.get('effective_observation_date_at_price_cutoff','미확인')),str(r.get('effective_assumed_available_at','미확인')),f'<a href="https://fred.stlouisfed.org/series/{r["series"]}">FRED 시리즈</a>'] for r in meta['us_coverage']]
    body+='<section class="panel" id="method"><h2>자료 날짜·계산 규칙·한계</h2>'+html_table(['미국 자료','원자료 시작','원자료 종료',f'{escape(price_as_of)} 한국장에 사용된 관측','사용 가능 시각 가정(KST)','출처'],coverage)+'''<ol>
<li>미국 관측일의 뉴욕17:00을 종가 확인 가능 시각으로 가정하고 Asia/Seoul 시간대로 바꿉니다. 한국09:00 이전 값만 사용하며 DST에 따라06:00/07:00 KST가 됩니다. FRED의 과거 실제 게시 시각이나 당시 정정 전 vintage를 확인한 것은 아닙니다.</li>
<li>한국 개장 사이 미국 종가 변화는 한국 휴장 중 여러 미국 거래를 누적합니다. 미국 자료가4일 이상 오래되면 미확인으로 처리합니다. 빈 값을0으로 바꾸지 않습니다.</li>
<li>상관·β·R²는 같은 표본의 설명 통계입니다. 부분상관은 당일 KODEX200 한 변수만 통제합니다. 상관이 낮아졌다고 미국의 영향이 없다고 결론 내리지 않습니다. 통제 변수 자체가 미국 충격을 전달할 수 있습니다.</li>
<li>실적은 발행사 발표일 기준입니다. 날짜만 확인한 자료는 그 날짜가 완전히 지난 뒤부터 조건에 반영합니다. 향후 공시·미래 미국 종가는 과거 신호에 넣지 않습니다.</li>
<li>발표일 목록은 불완전한 표본입니다. 실제 최초 발표와 후속 자료/정정의 차이, 사전 예상치와 공시 전 누출, 배당·현금이자·체결 충격, 모든 거시·산업 요인을 반영하지 못했습니다.</li>
<li>기존'''+str(len(model_names))+'''개 전략의 모든 종목/기간 결과를 원본과 수익률·낙폭·거래 수·투자 비중으로 대조했습니다. 추가 조건은 운용 전략의 확정 변경이나 미래 유효성 검증을 뜻하지 않습니다.</li></ol></section>'''
    monitor_lengths='/'.join(str(length) for length in rolling_lengths[-2:]) or '복수'
    body+=f'''<section class="panel" id="monitor"><h2>다음 판단을 바꿀 확인점</h2><div class="cards"><div class="card"><h3>미국 주도 변동 지속</h3><p>SOX·나스닥 동행이 최신 {escape(monitor_lengths)}일에도 유지되는지, 국내시장 통제 후에도 남는지 확인합니다. 관련성이 사라지면 미국 조건을 종목 고유 위험의 대용으로 사용하지 않습니다.</p></div><div class="card"><h3>실적과 주가의 괴리</h3><p>증익인데 주가가 하락하면 당시 컨센서스, 가이던스, 일회성·지원금과 국내/미국 시장 움직임을 추가 확인합니다. 전년 대비 증가율만으로 저평가·서프라이즈를 판정하지 않습니다.</p></div><div class="card"><h3>보류 규칙의 재현성</h3><p>원전략 대비 낙폭 감소와 상승장 기회비용을 함께 봅니다. 발표 목록을 완성하고 다음 미사용 기간에서 검증하기 전에는 관찰 후보로 둡니다.</p></div></div></section>'''
    sources=''.join('<li><strong>'+escape(r['name'])+'</strong> · '+escape(r['release_date'])+' · '+source_links(r)+'</li>' for r in data['issuers'])
    body+='<section class="panel" id="sources"><h2>발표 원문과 출처</h2><ul class="source-list">'+sources+'</ul><p class="muted">출처는 조사일에 확인한 발표자료이며 감사·정정 여부를 모두 재검증한 것은 아닙니다. 영업이익/순이익·분기/누적·잠정/후속자료의 차이는 종목별 정의에 표시했습니다.</p></section>'
    files=[('analysis.json','전체 분석 결과'),('earnings.json','발표 실적·출처·발표일 표본'),('us_aligned.csv','한국 개장 시점에 맞춘 미국 변수'),('factor_statistics.csv','기간·종목·요인별 상관/β'),('conditional_returns.csv','미국 상승/하락 구간 국내 반응'),('event_reactions.csv','실적 발표 전후 반응'),('overlay_stock_results.csv','조건 반영 전후 종목 결과'),('overlay_portfolio_results.csv','조건 반영 전후 포트폴리오'),('overlay_aggregates.csv','슬라이딩 분포 비교')]
    if data.get('_verification'):
        files += [('independent_trade_ledger.csv','독립 검산 거래 원장'),('verification.json','수치 검증 결과')]
    body+='<section class="panel" id="downloads"><h2>근거 파일과 공유</h2><div class="downloads">'+''.join(f'<a href="{escape(data_href)}/{name}" download>{label}</a>' for name,label in files)+f'<a href="earnings-us-impact-{escape(report_date)}.zip" download>보고서·기존 연구·근거 데이터 ZIP</a></div><p>HTML 탐색은 서버 없이 작동합니다. 근거파일도 함께 보려면 ZIP을 압축 해제하고 reports/ 폴더의 HTML을 여세요.</p></section>'
    nav_items=[('summary','핵심 판단'),('earnings','기업 실적')]
    if refresh_notes:nav_items.append(('source-refresh','자료 갱신'))
    nav_items += [('us-map','미국 민감도'),('events','발표 전후'),('overlays','전략 반영'),('overlay-explorer','기간·종목 비교'),('method','계산 기준'),('sources','원문'),('downloads','공유')]
    nav=''.join(f'<a href="#{anchor}">{title}</a>' for anchor,title in nav_items)
    return '<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>실적·미국 시장 영향 분석</title><style>'+CSS+EXTRA_CSS+'</style></head><body><main><nav>'+nav+'</nav><header class="hero"><span class="eyebrow">Earnings &amp; US market context</span><h1>실적·미국 시장 영향 분석</h1><p>'+f'{len(issuers)}기업·{len(names)}종목 · 조사 {escape(report_date)} · 국내 가격/백테스트 {escape(price_as_of)}까지'+'</p></header>'+body+'<footer>실적: 발행사 공식 IR·뉴스룸·공시자료. 미국시장: 지수 제공기관/미 재무부/CBOE 자료를 FRED에서 수집. 국내가격·전략: 기존 KIS 수집 및 프로젝트 백테스트. 과거 동행/실험 결과를 미래 수익이나 인과관계로 해석하지 않습니다.</footer></main><script>'+JS+EXPLORER_JS+'</script></body></html>'


def link_rolling(path: Path, href: str, report_date=None, price_as_of=None, issuer_count=15, symbol_count=16):
    if not path.exists():return
    text=path.read_text()
    import re
    text=re.sub(r'<section class="panel" id="earnings-us-context">.*?</section>', '', text, flags=re.S)
    report_date=str(report_date or DATE);price_as_of=str(price_as_of or PRICE_DATE)
    banner=f'<section class="panel" id="earnings-us-context"><h2>추가 분석 · 기업 실적과 미국 시장</h2><p>{issuer_count}기업·{symbol_count}종목의 발표 실적, 미국 지수와의 시차 상관, 발표 전후 반응, 매수신호 보류 규칙의 반영 전후 결과를 확인하세요. 조사일은 {escape(report_date)}이며 아래 기존 가격·전략 결과의 기준일은 {escape(price_as_of)}입니다.</p><a href="{escape(href)}">실적·미국 시장 영향 보고서 열기</a></section>'
    text=text.replace('</header>','</header>'+banner,1)
    for symbol in dict.fromkeys(re.findall(r'<details\b[^>]*\bid="stock-(\d{6})"', text)):
        target=f'id="stock-{symbol}"';start=text.find(target)
        if start<0:continue
        marker=f' data-context-stock="{symbol}"'
        link=f'<p{marker}><a href="{escape(href)}#stock-{symbol}">이 종목의 실적·미국 시장 민감도 함께 보기</a></p>'
        text=re.sub(r'<p'+marker+r'>.*?</p>','',text)
        # Recompute after removing a previous link so reruns stay idempotent.
        closing=text.find('</details>',text.find(target))
        opening=text.find('</summary><div>',text.find(target))
        if opening<0 or closing<0 or opening>closing:continue
        pos=opening+len('</summary><div>')
        text=text[:pos]+link+text[pos:]
    path.write_text(text,encoding='utf-8')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input',type=Path,default=Path(f'data/earnings-us/{DATE}/analysis.json'))
    parser.add_argument('--output',type=Path)
    parser.add_argument('--link-rolling',type=Path)
    parser.add_argument('--report-date',help='보고서/공유 파일 날짜. 생략하면 metadata.as_of를 사용합니다.')
    parser.add_argument('--data-href',help='근거 파일 상대 경로. 생략하면 보고서 날짜로 계산합니다.')
    args=parser.parse_args();data=json.loads(args.input.read_text(encoding='utf-8'))
    verification=args.input.parent/'verification.json'
    if verification.exists():data['_verification']=json.loads(verification.read_text())
    report_date=str(args.report_date or data.get('metadata',{}).get('as_of') or DATE)
    price_as_of=str(data.get('metadata',{}).get('price_as_of') or PRICE_DATE)
    output=args.output or Path(f'data/reports/earnings-us-impact-{report_date}.html')
    rolling=args.link_rolling or Path(f'data/reports/rolling-mixed-backtest-{price_as_of}.html')
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(render(data,report_date=report_date,data_href=args.data_href),encoding='utf-8')
    names={r['symbol'] for r in data.get('stock_results',[])}
    link_rolling(rolling,output.name,report_date=report_date,price_as_of=price_as_of,issuer_count=len(data.get('issuers',[])),symbol_count=len(names))
    print(output.resolve())


if __name__=='__main__':main()
