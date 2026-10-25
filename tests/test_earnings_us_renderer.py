import importlib.util
import json
from pathlib import Path

SPEC=importlib.util.spec_from_file_location('earnings_us_renderer',Path(__file__).resolve().parents[1]/'scripts/render_earnings_us_report.py')
renderer=importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(renderer)


def test_offline_explorer_retains_all_four_policies_and_stock_identities():
    records=[]
    for symbol,name in [('005930','삼성전자'),('005385','현대차우')]:
        for w in ['old','new']:
            for i,mode in enumerate(renderer.MODES):
                records.append(dict(symbol=symbol,symbol_name=name,window_id=w,base_model='momentum',overlay=mode,net_return_pct=i+.123456,net_mdd_pct=10+i,trade_count=i,bh_net_return_pct=4.5))
    data=dict(stock_results=records,models=[{'id':'momentum','name':'모멘텀'}],windows=[{'id':'old'},{'id':'new'}])
    payload=renderer.explorer_payload(data)
    assert len(payload['rows'])==4
    for row in payload['rows']:
        assert [r[0] for r in row[3:7]]==[.123456,1.123456,2.123456,3.123456]
        assert row[7]==4.5
        assert payload['stocks'][row[2]]['symbol'] in ('005930','005385')
    text=renderer.safe_json({'name':'</script><script>bad()</script>&'})
    assert '</script>' not in text
    assert json.loads(text)['name']=='</script><script>bad()</script>&'


def test_linking_context_is_idempotent_and_preserves_existing_results(tmp_path):
    report=tmp_path/'report.html'
    report.write_text('<html><header>Original title</header><section id="stock-explorer"></section><p>+83.76%</p><details id="stock-005930"><summary>삼성전자</summary><div>Existing results</div></details><script id="stock-explorer-data" type="application/json">{}</script></html>')
    renderer.link_rolling(report,'context.html')
    first=report.read_text()
    renderer.link_rolling(report,'context.html')
    second=report.read_text()
    assert first==second
    assert second.count('id="earnings-us-context"')==1
    assert second.count('data-context-stock="005930"')==1
    assert 'data-context-stock="explorer"' not in second
    assert 'data-context-stock="explorer-data"' not in second
    assert second.startswith('<html>')
    assert '+83.76%' in second and 'Existing results' in second
    assert renderer.financial(1000)=='1.0000조원'
    assert renderer.financial(None)=='미확인'


def test_report_context_and_facts_follow_refreshed_metadata():
    data={
        'metadata':{'as_of':'2026-10-24','price_as_of':'2026-10-23','verified_event_count':999},
        'events':[{'date':str(i)} for i in range(52)],
        'factors':[{'window_id':'common-history','start_date':'2025-01-08','end_date':'2026-10-23','n':434}],
        'portfolio_results':[{'kind':'full','length':435}],
        'aggregates':[{'length':20},{'length':60},{'length':20}],
    }
    assert renderer.report_context(data)==('2026-10-24','2026-10-23','../earnings-us/2026-10-24')
    assert renderer.report_context(data,'2026-10-25','../custom')==('2026-10-25','2026-10-23','../custom')
    assert renderer.report_facts(data)=={
        'event_count':52,'common_start':'2025-01-08','common_end':'2026-10-23',
        'common_n':434,'full_length':435,'rolling_lengths':[20,60],
    }


def test_linking_context_accepts_refreshed_dates_and_counts(tmp_path):
    report=tmp_path/'report.html'
    report.write_text('<html><header>Title</header><details id="stock-207940"><summary>삼성바이오로직스</summary><div>Body</div></details></html>')
    renderer.link_rolling(report,'fresh.html',report_date='2026-10-24',price_as_of='2026-10-23',issuer_count=15,symbol_count=16)
    text=report.read_text()
    assert '조사일은 2026-10-24' in text
    assert '기준일은 2026-10-23' in text
    assert '15기업·16종목' in text
    assert 'fresh.html#stock-207940' in text
