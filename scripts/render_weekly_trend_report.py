"""Render a reusable, date-aware weekly trend report from collected CSVs."""
from __future__ import annotations

import argparse
import json
import math
from collections import Counter
from html import escape
from pathlib import Path

import numpy as np
import pandas as pd

try:
    from scripts.render_rolling_backtest_report import CSS, JS, html_table
except ModuleNotFoundError:  # Direct `python scripts/...` execution.
    from render_rolling_backtest_report import CSS, JS, html_table


SECTORS = {
    '005930':'반도체','000660':'반도체','005380':'자동차','005385':'자동차','000270':'자동차',
    '373220':'배터리','006400':'배터리','207940':'바이오','068270':'바이오',
    '035420':'인터넷','035720':'인터넷','105560':'금융','055550':'금융','005490':'소재',
    '329180':'조선','012450':'방산',
}


def _number(value):
    if value is None or pd.isna(value):
        return None
    result = float(value)
    return result if math.isfinite(result) else None


def _return(close, baseline):
    return None if close is None or baseline is None else (close / baseline - 1) * 100


def calendar_weeks(latest_date):
    latest = pd.Timestamp(latest_date).normalize()
    current_start = latest - pd.Timedelta(days=latest.weekday())
    previous_start = current_start - pd.Timedelta(days=7)
    return {
        'latest_date': latest,
        'current_start': current_start,
        'current_end': current_start + pd.Timedelta(days=4),
        'previous_start': previous_start,
        'previous_end': previous_start + pd.Timedelta(days=4),
    }


def period_metrics(frame, start, end):
    period = frame[frame.date.between(start, end)]
    prior = frame[frame.date.lt(start)]
    baseline = None if prior.empty else prior.iloc[-1]
    latest = None if period.empty else period.iloc[-1]
    return {
        'start': str(pd.Timestamp(start).date()), 'end': str(pd.Timestamp(end).date()),
        'trading_days': len(period),
        'dates': period.date.dt.strftime('%Y-%m-%d').tolist(),
        'baseline_date': None if baseline is None else str(baseline.date.date()),
        'baseline_close': None if baseline is None else float(baseline.close),
        'last_date': None if latest is None else str(latest.date.date()),
        'last_close': None if latest is None else float(latest.close),
        'return_pct': _return(None if latest is None else float(latest.close), None if baseline is None else float(baseline.close)),
        'mean_volume': None if period.empty else float(period.volume.mean()),
    }


def weekly_flow(investor, expected_dates):
    expected = pd.DatetimeIndex(pd.to_datetime(expected_dates))
    if len(expected) == 0:
        return {'available': False, 'foreign_net_qty': None, 'institution_net_qty': None,
                'missing_dates': [], 'observed_days': 0}
    indexed = investor.set_index('date')
    missing = expected.difference(indexed.index)
    if len(missing):
        return {'available': False, 'foreign_net_qty': None, 'institution_net_qty': None,
                'missing_dates': missing.strftime('%Y-%m-%d').tolist(),
                'observed_days': len(expected) - len(missing)}
    rows = indexed.loc[expected]
    return {'available': True, 'foreign_net_qty': int(rows.frgn_ntby_qty.sum()),
            'institution_net_qty': int(rows.orgn_ntby_qty.sum()),
            'missing_dates': [], 'observed_days': len(rows)}


def trend_label(row):
    close, ma20, rsi, change = row['close'], row['ma_20'], row['rsi_14'], row['current_week']['return_pct']
    if ma20 is None:
        return '20일선 산출 불가'
    position = '20일선 위' if close >= ma20 else '20일선 아래'
    direction = '주간 상승' if change is not None and change > 0 else '주간 하락' if change is not None and change < 0 else '주간 보합'
    if rsi is not None and rsi >= 70:
        return f'{direction} · {position} · RSI≥70'
    if rsi is not None and rsi <= 30:
        return f'{direction} · {position} · RSI≤30'
    return f'{direction} · {position}'


def build_summary(input_dir: Path) -> dict:
    manifest = json.loads((input_dir / 'collection_manifest.json').read_text())
    records = [row for row in manifest.get('results', []) if row.get('status') == 'success']
    names = {str(row['symbol']).zfill(6): row.get('name', row['symbol']) for row in records}
    if '069500' not in names:
        raise ValueError('collection_manifest.json must include 069500 benchmark')
    symbols = sorted(symbol for symbol in names if symbol != '069500')
    frames = {}
    for symbol in [*symbols, '069500']:
        frame = pd.read_csv(input_dir / f'{symbol}_indicators.csv', parse_dates=['date']).sort_values('date').reset_index(drop=True)
        required = {'date','close','volume','ma_5','ma_20','ma_60','rsi_14'}
        if required - set(frame) or frame.empty or frame.date.isna().any() or not frame.date.is_unique:
            raise ValueError(f'{symbol}: invalid indicators')
        if not frame.date.is_monotonic_increasing or not np.isfinite(frame.close).all() or frame.close.le(0).any():
            raise ValueError(f'{symbol}: invalid price calendar/data')
        frames[symbol] = frame
    latest = min(frame.date.iloc[-1] for frame in frames.values())
    if any(frame.date.iloc[-1] != latest for frame in frames.values()):
        raise ValueError('Indicator files have different latest dates')
    weeks = calendar_weeks(latest)

    rows = []
    for symbol in [*symbols, '069500']:
        frame = frames[symbol]
        previous = period_metrics(frame, weeks['previous_start'], weeks['previous_end'])
        current = period_metrics(frame, weeks['current_start'], weeks['current_end'])
        two_week = period_metrics(frame, weeks['previous_start'], weeks['current_end'])
        last = frame.iloc[-1]
        row = {
            'symbol': symbol, 'name': names[symbol], 'sector': SECTORS.get(symbol, 'ETF 비교 기준'),
            'date': str(last.date.date()), 'close': float(last.close),
            'ma_5': _number(last.ma_5), 'ma_20': _number(last.ma_20), 'ma_60': _number(last.ma_60),
            'rsi_14': _number(last.rsi_14), 'previous_week': previous,
            'current_week': current, 'two_week': two_week,
            'recent_21': frame.tail(21)[['date','close','volume','ma_20','rsi_14']].assign(
                date=lambda value:value.date.dt.strftime('%Y-%m-%d')).replace({np.nan:None}).to_dict('records'),
        }
        if symbol != '069500':
            investor_path = input_dir / f'{symbol}_investor.csv'
            if investor_path.exists():
                investor = pd.read_csv(investor_path)
                required = {'stck_bsop_date','frgn_ntby_qty','orgn_ntby_qty'}
                if required - set(investor):
                    raise ValueError(f'{symbol}: invalid investor data')
                investor['date'] = pd.to_datetime(investor.stck_bsop_date.astype(str), format='%Y%m%d', errors='raise')
                if not investor.date.is_unique:
                    raise ValueError(f'{symbol}: duplicate investor dates')
            else:
                investor = pd.DataFrame(columns=['date','frgn_ntby_qty','orgn_ntby_qty'])
            row['previous_flow'] = weekly_flow(investor, previous['dates'])
            row['current_flow'] = weekly_flow(investor, current['dates'])
            flow_map = investor.set_index('date')[['frgn_ntby_qty','orgn_ntby_qty']].to_dict('index')
            for daily in row['recent_21']:
                flow = flow_map.get(pd.Timestamp(daily['date']))
                daily['foreign_net_qty'] = None if flow is None else int(flow['frgn_ntby_qty'])
                daily['institution_net_qty'] = None if flow is None else int(flow['orgn_ntby_qty'])
        row['ma20_distance_pct'] = _return(row['close'], row['ma_20'])
        row['trend'] = trend_label(row)
        rows.append(row)

    benchmark = next(row for row in rows if row['symbol'] == '069500')
    stocks = [row for row in rows if row['symbol'] != '069500']
    for row in stocks:
        value, base = row['current_week']['return_pct'], benchmark['current_week']['return_pct']
        row['benchmark_difference_pp'] = None if value is None or base is None else value - base
    sectors = []
    for sector in dict.fromkeys(SECTORS.values()):
        members = [row for row in stocks if row['sector'] == sector]
        if not members:
            continue
        values = [row['current_week']['return_pct'] for row in members if row['current_week']['return_pct'] is not None]
        sectors.append({'name':sector,'count':len(members),'symbols':[row['symbol'] for row in members],
                        'current_week_mean_pct':None if not values else float(np.mean(values))})
    revisions_path = input_dir / 'price_revisions.csv'
    revisions = None
    if revisions_path.exists():
        revision_frame = pd.read_csv(revisions_path, dtype={'symbol': str})
        required = {'symbol','date','field','previous_value','refreshed_value'}
        if required - set(revision_frame):
            raise ValueError('price_revisions.csv is missing required columns')
        revision_dates = pd.to_datetime(revision_frame.date, errors='raise')
        revisions = {
            'changed_cells': len(revision_frame),
            'security_count': int(revision_frame.symbol.astype(str).str.zfill(6).nunique()),
            'dates': sorted(revision_dates.dt.strftime('%Y-%m-%d').unique().tolist()),
            'fields': sorted(revision_frame.field.astype(str).unique().tolist()),
        }
    return {
        'report_date': str(latest.date()), 'collected_at': manifest.get('collected_at'),
        'periods': {key:(str(value.date()) if isinstance(value,pd.Timestamp) else value) for key,value in weeks.items()},
        'summary': {
            'stock_count': len(stocks),
            'up': sum((row['current_week']['return_pct'] or 0) > 0 for row in stocks),
            'down': sum((row['current_week']['return_pct'] or 0) < 0 for row in stocks),
            'above_ma20': sum(row['ma_20'] is not None and row['close'] >= row['ma_20'] for row in stocks),
            'missing_current_flow': sum(not row['current_flow']['available'] for row in stocks),
            'trends': dict(Counter(row['trend'] for row in stocks)),
        },
        'benchmark': benchmark, 'rows': stocks, 'sectors': sectors,
        'price_revisions': revisions,
    }


def pct(value, points=False):
    if value is None:
        return '—'
    suffix = '%p' if points else '%'
    return f'<span class="{"positive" if value >= 0 else "negative"}">{value:+.2f}{suffix}</span>'


def integer(value):
    return '—' if value is None else f'{value:+,}'


def sparkline(row):
    observations = row['recent_21']
    values = [float(item['close']) for item in observations]
    if len(values) < 2:
        return '<p class="muted">차트를 만들 관측치가 부족합니다.</p>'
    base = values[0]
    returns = [(value/base-1)*100 for value in values]
    low, high = min(returns), max(returns)
    pad = max((high-low)*.1, 1)
    low -= pad; high += pad
    width,height,left,right,top,bottom = 940,250,60,20,18,38
    x=lambda i:left+i/max(len(values)-1,1)*(width-left-right)
    y=lambda value:top+(high-value)/max(high-low,1e-9)*(height-top-bottom)
    points=' '.join(f'{x(i):.1f},{y(value):.1f}' for i,value in enumerate(returns))
    labels=(observations[0]['date'],observations[len(observations)//2]['date'],observations[-1]['date'])
    return (f'<div class="chart"><svg viewBox="0 0 {width} {height}" role="img" aria-label="{escape(row["name"])} 최근 21거래일 종가 변화">'
            f'<line x1="{left}" x2="{width-right}" y1="{y(0):.1f}" y2="{y(0):.1f}" stroke="#9aa8bb"/>'
            f'<polyline points="{points}" fill="none" stroke="#2563eb" stroke-width="3"/>'
            f'<text x="{left}" y="{height-10}" font-size="12">{labels[0]}</text>'
            f'<text x="{width/2}" y="{height-10}" text-anchor="middle" font-size="12">{labels[1]}</text>'
            f'<text x="{width-right}" y="{height-10}" text-anchor="end" font-size="12">{labels[2]}</text>'
            '</svg></div>')


def safe_json(data):
    return json.dumps(data, ensure_ascii=False, allow_nan=False, separators=(',',':')).replace('<','\\u003c').replace('>','\\u003e').replace('&','\\u0026').replace('\u2028','\\u2028').replace('\u2029','\\u2029')


def render(data: dict, input_dir: Path, report_date: str | None = None) -> str:
    report_date = report_date or data['report_date']
    rows = data['rows']; benchmark = data['benchmark']; summary = data['summary']
    period = data['periods']; href = f'../weekly-trend/{report_date}'
    nav = (f'<nav><a href="rolling-mixed-backtest-{report_date}.html">슬라이딩 백테스트</a>'
           f'<a href="earnings-us-impact-{report_date}.html">실적·미국시장 영향</a><a href="#comparison">종목 비교</a><a href="#stocks">종목별 상세</a></nav>')
    body = [f'<main>{nav}<header class="hero"><span class="eyebrow">Weekly trend · {escape(report_date)}</span>'
            f'<h1>주요 종목 주간 추세</h1><p>실제 최신 거래일 {escape(data["report_date"])} 기준. '
            f'이번 주 {escape(period["current_start"])}~{escape(period["current_end"])}, 직전 주 {escape(period["previous_start"])}~{escape(period["previous_end"])}를 비교합니다.</p></header>']
    stats = [('분석 종목',f'{summary["stock_count"]}종목'),('이번 주 상승 / 하락',f'{summary["up"]} / {summary["down"]}'),
             ('20일선 위',f'{summary["above_ma20"]}종목'),('이번 주 수급 누락',f'{summary["missing_current_flow"]}종목')]
    body.append('<section class="panel"><h2>관측 요약</h2><div class="stats">'+''.join(f'<div class="stat"><span>{label}</span><strong>{value}</strong></div>' for label,value in stats)+'</div>')
    body.append(f'<p>비교 ETF의 이번 주 가격 변화는 {pct(benchmark["current_week"]["return_pct"])}입니다. 수익률은 각 달력 주 시작 전 마지막 관측 종가를 기준으로 계산합니다. 휴장일은 거래일 수에서 제외되며, 수급 CSV에 해당 거래일이 빠지면 0으로 보정하지 않고 누락으로 표시합니다.</p>')
    revisions = data.get('price_revisions')
    if revisions:
        dates = ', '.join(revisions['dates'])
        body.append(
            '<p class="callout warning"><strong>재조회 차이 기록</strong> · '
            f'{revisions["security_count"]}개 증권, {revisions["changed_cells"]}개 셀, 영향 날짜 {escape(dates)}. '
            '이전 저장본과 중복 날짜의 가격·거래량이 달라 최신 API 조회값으로 다시 계산했습니다. '
            '차이에는 기간 연장과 원자료 재조회 변경이 함께 포함됩니다. '
            f'<a href="{href}/price_revisions.csv">변경 내역 CSV</a></p>'
        )
    body.append('<p class="callout warning">20일 이동평균과 RSI는 관측 위치를 설명하는 지표입니다. 자동 매매 판단, 목표수익률 또는 가격 움직임의 원인 분석으로 사용하지 않습니다.</p></section>')
    body.append('<section class="panel" id="comparison"><h2>16종목 비교</h2>')
    body.append(f'<div class="filters" data-filter-table="weekly-comparison"><label>검색<input type="search" data-filter="text" placeholder="종목명 또는 코드"></label><label>업종<select data-filter="sector"><option value="all">전체</option>{"".join(f"<option value=\"{escape(s)}\">{escape(s)}</option>" for s in dict.fromkeys(SECTORS.values()))}</select></label><span class="filter-count" data-filter-count></span></div>')
    table_rows=[];attrs=[]
    for row in sorted(rows,key=lambda item:item['current_week']['return_pct'] if item['current_week']['return_pct'] is not None else -math.inf,reverse=True):
        current_flow=row['current_flow']
        table_rows.append([f'<a href="#stock-{row["symbol"]}">{escape(row["name"])}<small> {row["symbol"]}</small></a>',escape(row['sector']),
            f'{row["close"]:,.0f}',str(row['previous_week']['trading_days']),pct(row['previous_week']['return_pct']),str(row['current_week']['trading_days']),pct(row['current_week']['return_pct']),pct(row['two_week']['return_pct']),
            pct(row['benchmark_difference_pp'],True),pct(row['ma20_distance_pct']),('—' if row['rsi_14'] is None else f'{row["rsi_14"]:.1f}'),
            integer(current_flow['foreign_net_qty']),integer(current_flow['institution_net_qty']),escape(row['trend'])])
        attrs.append(f' data-sector="{escape(row["sector"])}"')
    body.append(html_table(['종목','업종','종가','직전 주 일수','직전 주','이번 주 일수','이번 주','2주','ETF 대비','20일선 이격','RSI14','외국인','기관','관측 상태'],table_rows,table_id='weekly-comparison',row_attrs=attrs))
    body.append('<p class="muted">ETF 대비는 동일 기간 가격 변화율의 단순 차이입니다. 배당·거래비용·위험 조정을 포함하지 않습니다.</p></section>')
    body.append('<section class="panel"><h2>업종 묶음 단순평균</h2><p class="muted">수동 분류이며 공식 섹터지수나 시가총액 가중 성과가 아닙니다. 1종목 업종은 해당 종목만 나타냅니다.</p>')
    body.append(html_table(['업종','표본 수','이번 주 단순평균'],[[escape(row['name']),str(row['count']),pct(row['current_week_mean_pct'])] for row in sorted(data['sectors'],key=lambda item:item['current_week_mean_pct'] if item['current_week_mean_pct'] is not None else -math.inf,reverse=True)]))
    body.append('</section><section class="panel" id="stocks"><h2>종목별 최근 21거래일</h2><label class="detail-search">종목명·코드 검색<input id="stock-detail-search" type="search"></label><p id="stock-detail-empty" class="empty-state" hidden>일치하는 종목이 없습니다.</p>')
    for row in rows:
        flow=row['current_flow'];missing=', '.join(flow['missing_dates']) or '없음'
        detail_rows=[]
        for daily in row['recent_21']:
            detail_rows.append([daily['date'],f'{float(daily["close"]):,.0f}',f'{int(daily["volume"]):,}',
                                '—' if daily['ma_20'] is None else f'{float(daily["ma_20"]):,.0f}',
                                '—' if daily['rsi_14'] is None else f'{float(daily["rsi_14"]):.1f}',
                                integer(daily['foreign_net_qty']),integer(daily['institution_net_qty'])])
        body.append(f'<details id="stock-{row["symbol"]}"><summary>{escape(row["name"])} · {row["symbol"]} · {escape(row["trend"])}</summary><div>')
        body.append(sparkline(row))
        body.append(f'<p>이번 주 {row["current_week"]["trading_days"]}거래일 {pct(row["current_week"]["return_pct"])}, 직전 주 {row["previous_week"]["trading_days"]}거래일 {pct(row["previous_week"]["return_pct"])}. 이번 주 수급 누락일: {escape(missing)}.</p>')
        body.append(html_table(['날짜','종가','거래량','20일선','RSI14','외국인 순매수','기관 순매수'],detail_rows))
        body.append(f'<p class="downloads"><a href="{href}/{row["symbol"]}_indicators.csv">가격·지표 CSV</a><a href="{href}/{row["symbol"]}_investor.csv">수급 CSV</a></p></div></details>')
    body.append('</section><section class="panel" id="sources"><h2>데이터와 산식</h2><ul>')
    body.append(f'<li>가격·지표: <a href="{href}/collection_manifest.json">수집 매니페스트</a>, <a href="{href}/069500_indicators.csv">KODEX 200 CSV</a></li>')
    body.append('<li>주간 수익률: 해당 월요일 이전 마지막 종가 대비 그 주 마지막 관측 종가. 거래일이 없는 주는 수익률을 표시하지 않습니다.</li><li>수급: 해당 주 가격 거래일이 모두 수급 CSV에 있을 때만 합산합니다.</li><li>최근 21거래일 차트는 첫 종가를 기준으로 정규화한 가격 궤적입니다.</li></ul></section>')
    body.append(f'<footer>보고서 생성 기준 {escape(report_date)} · 실제 가격 기준 {escape(data["report_date"])} · 원천 파일 {escape(str(input_dir))}</footer>')
    body.append(f'<script type="application/json" id="weekly-report-data">{safe_json(data)}</script><script>{JS}</script></main>')
    title=f'주요 종목 주간 추세 · {report_date}'
    return f'<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{escape(title)}</title><style>{CSS}</style></head><body>{"".join(body)}</body></html>'


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input-dir',type=Path,default=Path('data/weekly-trend/2026-10-24'))
    parser.add_argument('--output',type=Path,default=Path('data/reports/weekly-trend-2026-10-24.html'))
    parser.add_argument('--report-date')
    parser.add_argument('--summary-output',type=Path)
    args=parser.parse_args()
    data=build_summary(args.input_dir)
    report_date=args.report_date or data['report_date']
    data['report_date_label']=report_date
    summary_path=args.summary_output or args.input_dir/'summary.json'
    summary_path.parent.mkdir(parents=True,exist_ok=True)
    summary_path.write_text(json.dumps(data,ensure_ascii=False,indent=2,allow_nan=False))
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(render(data,args.input_dir,report_date))
    print(json.dumps({'output':str(args.output),'summary':str(summary_path),'price_as_of':data['report_date'],'stocks':len(data['rows'])},ensure_ascii=False))


if __name__=='__main__':
    main()
