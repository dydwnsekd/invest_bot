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
    report.write_text('<html><header>Original title</header><p>+83.76%</p><details id="stock-005930"><summary>삼성전자</summary><div>Existing results</div></details></html>')
    renderer.link_rolling(report,'context.html')
    first=report.read_text()
    renderer.link_rolling(report,'context.html')
    second=report.read_text()
    assert first==second
    assert second.count('id="earnings-us-context"')==1
    assert second.count('data-context-stock="005930"')==1
    assert '+83.76%' in second and 'Existing results' in second
    assert renderer.financial(1000)=='1.0000조원'
    assert renderer.financial(None)=='미확인'
