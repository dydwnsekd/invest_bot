import json
from pathlib import Path

import numpy as np
import pandas as pd

from scripts.render_weekly_trend_report import build_summary, render


def write_inputs(folder: Path, *, missing_flow=False, revisions=False):
    folder.mkdir()
    dates=pd.to_datetime(['2026-10-09','2026-10-12','2026-10-13','2026-10-15','2026-10-19','2026-10-20','2026-10-23'])
    manifest={'collected_at':'2026-10-23T18:00:00+09:00','results':[]}
    for symbol,name,scale in [('005930','삼성전자',1),('000660','SK하이닉스',2),('069500','KODEX 200',.5)]:
        frame=pd.DataFrame({'date':dates,'close':np.array([100,102,101,103,104,106,105])*scale,
                            'volume':[1000,1100,1200,1300,1400,1500,1600],
                            'ma_5':100*scale,'ma_20':101*scale,'ma_60':99*scale,'rsi_14':55.})
        frame.to_csv(folder/f'{symbol}_indicators.csv',index=False)
        manifest['results'].append({'symbol':symbol,'name':name,'status':'success'})
        if symbol!='069500':
            inv_dates=dates[1:]
            if missing_flow and symbol=='005930':inv_dates=inv_dates[inv_dates!=pd.Timestamp('2026-10-20')]
            pd.DataFrame({'stck_bsop_date':inv_dates.strftime('%Y%m%d'),'frgn_ntby_qty':10,'orgn_ntby_qty':-2}).to_csv(folder/f'{symbol}_investor.csv',index=False)
    (folder/'collection_manifest.json').write_text(json.dumps(manifest,ensure_ascii=False))
    if revisions:
        pd.DataFrame([
            {'symbol':'005930','name':'삼성전자','date':'2026-10-13','field':'close','previous_value':99,'refreshed_value':101},
            {'symbol':'005930','name':'삼성전자','date':'2026-10-13','field':'volume','previous_value':900,'refreshed_value':1200},
            {'symbol':'000660','name':'SK하이닉스','date':'2026-10-15','field':'close','previous_value':201,'refreshed_value':206},
        ]).to_csv(folder/'price_revisions.csv',index=False)


def test_calendar_week_baselines_and_holiday_day_counts(tmp_path):
    source=tmp_path/'weekly';write_inputs(source)
    data=build_summary(source)
    samsung=next(row for row in data['rows'] if row['symbol']=='005930')
    assert data['report_date']=='2026-10-23'
    assert samsung['previous_week']['baseline_date']=='2026-10-09'
    assert samsung['previous_week']['trading_days']==3
    assert samsung['previous_week']['return_pct']==(103/100-1)*100
    assert samsung['current_week']['baseline_date']=='2026-10-15'
    assert samsung['current_week']['trading_days']==3
    assert samsung['current_week']['return_pct']==(105/103-1)*100
    assert data['benchmark']['current_week']['trading_days']==3


def test_missing_weekly_flow_remains_missing_instead_of_zero(tmp_path):
    source=tmp_path/'weekly';write_inputs(source,missing_flow=True)
    data=build_summary(source)
    samsung=next(row for row in data['rows'] if row['symbol']=='005930')
    assert samsung['current_flow']['available'] is False
    assert samsung['current_flow']['foreign_net_qty'] is None
    assert samsung['current_flow']['missing_dates']==['2026-10-20']
    hynix=next(row for row in data['rows'] if row['symbol']=='000660')
    assert hynix['current_flow']['available'] is True
    assert hynix['current_flow']['foreign_net_qty']==30


def test_report_contains_search_sort_payload_sources_and_actual_cutoff(tmp_path):
    source=tmp_path/'weekly';write_inputs(source,missing_flow=True,revisions=True)
    data=build_summary(source)
    html=render(data,source,'2026-10-24')
    assert 'data-filter-table="weekly-comparison"' in html
    assert 'class="sort-button"' in html and '종목명 또는 코드' in html
    assert 'id="weekly-report-data"' in html
    assert '실제 최신 거래일 2026-10-23 기준' in html
    assert 'rolling-mixed-backtest-2026-10-24.html' in html
    assert '../weekly-trend/2026-10-24/005930_indicators.csv' in html
    assert '2026-10-20' in html and '수급 누락일' in html
    assert data['price_revisions']=={'changed_cells':3,'security_count':2,'dates':['2026-10-13','2026-10-15'],'fields':['close','volume']}
    assert '이전 저장본과 중복 날짜의 가격·거래량이 달라 최신 API 조회값으로 다시 계산했습니다.' in html
    assert '../weekly-trend/2026-10-24/price_revisions.csv' in html
    payload=html.split('id="weekly-report-data">',1)[1].split('</script>',1)[0]
    parsed=json.loads(payload)
    assert parsed['report_date']=='2026-10-23' and len(parsed['rows'])==2


def test_price_revision_disclosure_is_optional(tmp_path):
    source=tmp_path/'weekly';write_inputs(source)
    data=build_summary(source)
    assert data['price_revisions'] is None
    assert '재조회 차이 기록' not in render(data,source,'2026-10-24')
