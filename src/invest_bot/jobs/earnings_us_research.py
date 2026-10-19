"""Point-in-time US market alignment and verified earnings-event research.

Standalone CSV research; does not change live strategies or write to the DB.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import requests

from invest_bot.backtest.dates import require_unique_trading_dates
from invest_bot.jobs.rolling_backtest_research import (
    REPORT_SYMBOLS, INITIAL_EQUITY, aggregate_results, json_default, mdd,
    run_metrics, run_signal,
)

SERIES = {
    'SP500': 'S&P 500', 'NASDAQCOM': '나스닥 종합',
    'NASDAQSOX': '미국 반도체 SOX', 'VIXCLS': 'VIX', 'DGS10': '미국 10년물 금리',
}
BASE_MODELS = ('momentum', 'trend-filter', 'mix-mt-and', 'mix-mtf-exit-any')
OVERLAYS = {'base': '기존 전략', 'us': '미국 급락 확인일 매수신호 보류',
            'earnings': '확인된 실적 발표 후 3일 매수신호 보류', 'combined': '미국·실적 신호 보류 결합'}


def collect_us(output: Path, start: str, end: str) -> list[dict]:
    """Download public, dated FRED observations and retain the exact bytes."""
    output.mkdir(parents=True, exist_ok=True)
    records = []
    for series in SERIES:
        url = f'https://fred.stlouisfed.org/graph/fredgraph.csv?id={series}&cosd={start}&coed={end}'
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        frame = pd.read_csv(io.StringIO(response.text))
        normalize_us(frame, series)
        path = output / f'{series}.csv'
        path.write_bytes(response.content)
        records.append(dict(series=series, url=url, path=str(path),
                            retrieved_at=datetime.now(ZoneInfo('Asia/Seoul')).isoformat(),
                            sha256=hashlib.sha256(response.content).hexdigest()))
    (output / 'manifest.json').write_text(json.dumps(records, ensure_ascii=False, indent=2))
    return records


def normalize_us(frame: pd.DataFrame, series: str) -> pd.DataFrame:
    if series not in SERIES or not {'observation_date', series} <= set(frame):
        raise ValueError(f'Invalid US series: {series}')
    result = pd.DataFrame({'date': pd.to_datetime(frame.observation_date, errors='raise'),
                           'value': pd.to_numeric(frame[series], errors='coerce')})
    require_unique_trading_dates(result, source=f'FRED {series}')
    result = result.sort_values('date').reset_index(drop=True)
    raw = frame[series].astype(str).str.strip()
    unexpected = pd.to_numeric(frame[series], errors='coerce').isna() & ~raw.isin(['', '.', 'nan'])
    if unexpected.any():
        raise ValueError(f'{series}: malformed observations')
    result = result.dropna(subset=['value']).reset_index(drop=True)
    if result.empty or not np.isfinite(result.value).all() or (series != 'DGS10' and (result.value <= 0).any()):
        raise ValueError(f'{series}: empty/nonpositive/nonfinite observations')
    # US cash markets normally close by 16:00 ET. Use 17:00 ET conservatively.
    # This is a market-observability assumption, not FRED's historical posting time.
    result['available_at'] = (result.date + pd.Timedelta(hours=17)).dt.tz_localize('America/New_York').dt.tz_convert('Asia/Seoul')
    result['daily_change'] = result.value.diff() * 100 if series == 'DGS10' else result.value.pct_change(fill_method=None) * 100
    return result


def align_us_features(dates, series_frames: dict[str, pd.DataFrame]) -> pd.DataFrame:
    dates = pd.Series(pd.to_datetime(dates)).reset_index(drop=True)
    calendar = pd.DataFrame({'date': dates})
    require_unique_trading_dates(calendar, source='Korean calendar')
    if not calendar.date.is_monotonic_increasing:
        raise ValueError('Korean calendar must be increasing')
    opens = (dates + pd.Timedelta(hours=9)).dt.tz_localize('Asia/Seoul')
    result = calendar.copy()
    for series, source in series_frames.items():
        us = normalize_us(source, series)
        right = us[['date', 'value', 'daily_change', 'available_at']].rename(columns={'date': 'us_date'})
        joined = pd.merge_asof(pd.DataFrame({'kr_open': opens}), right, left_on='kr_open', right_on='available_at', direction='backward', allow_exact_matches=False)
        age = (joined.kr_open - joined.available_at).dt.total_seconds() / 86400
        valid = age.le(4) & joined.value.notna()
        result[f'{series}_date'] = joined.us_date
        result[f'{series}_available_at'] = joined.available_at
        result[f'{series}_age_days'] = age
        result[f'{series}_level'] = joined.value.where(valid)
        result[f'{series}_daily_change'] = joined.daily_change.where(valid)
        # Difference between successive Korean opens accumulates US sessions
        # over Korean holidays, and gives zero when no new US close exists.
        change = joined.value.diff() * 100 if series == 'DGS10' else joined.value.pct_change(fill_method=None) * 100
        result[f'{series}_interval_change'] = change.where(valid & valid.shift(fill_value=False))
        result[f'{series}_new_close'] = joined.us_date.ne(joined.us_date.shift()) & joined.us_date.notna()
        if (joined.available_at.dropna().reset_index(drop=True) >= joined.kr_open[joined.available_at.notna()].reset_index(drop=True)).any():
            raise ValueError('Future US observation leaked into Korean session')
    return result


def factor_statistics(stock_returns, us_returns, benchmark_returns) -> dict:
    frame = pd.DataFrame({'stock': stock_returns, 'us': us_returns, 'kr': benchmark_returns}).replace([np.inf, -np.inf], np.nan).dropna()
    n = len(frame)
    empty = dict(n=n, correlation=None, beta=None, r_squared=None, partial_correlation=None)
    if n < 10 or frame.us.std(ddof=0) < 1e-12 or frame.stock.std(ddof=0) < 1e-12:
        return empty
    correlation = float(frame.stock.corr(frame.us))
    beta = float(np.cov(frame.stock, frame.us, ddof=0)[0, 1] / np.var(frame.us))
    partial = None
    if frame.kr.std(ddof=0) > 1e-12:
        design = np.column_stack([np.ones(n), frame.kr])
        sy = frame.stock - design @ np.linalg.lstsq(design, frame.stock, rcond=None)[0]
        ux = frame.us - design @ np.linalg.lstsq(design, frame.us, rcond=None)[0]
        if sy.std(ddof=0) > 1e-12 and ux.std(ddof=0) > 1e-12:
            partial = float(sy.corr(ux))
    return dict(n=n, correlation=correlation, beta=beta, r_squared=correlation ** 2, partial_correlation=partial)


def earnings_cooldown(dates, events: list[dict], issuer: str, sessions: int = 3) -> np.ndarray:
    dates = pd.DatetimeIndex(pd.to_datetime(dates))
    blocked = np.zeros(len(dates), dtype=bool)
    for event in events:
        if event['issuer_symbol'] != issuer:
            continue
        # Only the source's verified actual publication day is used. Unknown
        # times are treated as unavailable until that whole Korean day ends.
        publication = pd.Timestamp(event['date']).normalize()
        start = int(dates.searchsorted(publication, side='right'))
        blocked[start:start + sessions] = True
    return blocked


def gate_entries(signals: pd.DataFrame, blocked) -> pd.DataFrame:
    blocked = np.asarray(blocked, dtype=bool)
    if len(signals) != len(blocked):
        raise ValueError('Gate/calendar length mismatch')
    result = signals.copy()
    result.loc[blocked & result.signal.eq('buy'), 'signal'] = 'hold'
    return result


def event_reactions(prices: pd.DataFrame, benchmark: pd.DataFrame, events: list[dict], issuer: str) -> list[dict]:
    if not prices.date.equals(benchmark.date):
        raise ValueError('Event/benchmark calendars differ')
    dates = pd.DatetimeIndex(prices.date)
    rows = []
    for event in events:
        if event['issuer_symbol'] != issuer:
            continue
        day = pd.Timestamp(event['date'])
        i = int(dates.searchsorted(day, side='left'))
        if day < dates[0] or day > dates[-1]:
            continue
        exact = i < len(dates) and dates[i] == day and i > 0
        first_post = int(dates.searchsorted(day, side='right'))
        row = dict(event, trading_date=str(dates[i].date()) if exact else None,
                   first_post_date=str(dates[first_post].date()) if first_post < len(dates) else None)
        row['event_day_return_pct'] = float((prices.close.iloc[i] / prices.close.iloc[i - 1] - 1) * 100) if exact else None
        row['event_day_etf_diff_pp'] = row['event_day_return_pct'] - float((benchmark.close.iloc[i] / benchmark.close.iloc[i - 1] - 1) * 100) if exact else None
        for horizon in (1, 3, 5):
            end = first_post + horizon - 1
            value = float((prices.close.iloc[end] / prices.close.iloc[first_post - 1] - 1) * 100) if first_post > 0 and end < len(dates) else None
            excess = value - float((benchmark.close.iloc[end] / benchmark.close.iloc[first_post - 1] - 1) * 100) if value is not None else None
            row[f'post_{horizon}_return_pct'] = value
            row[f'post_{horizon}_etf_diff_pp'] = excess
        rows.append(row)
    return rows


def validated_earnings(packet: dict, as_of: str) -> tuple[list[dict], list[dict]]:
    issuers = packet.get('issuers', [])
    seen = set()
    events = []
    for issuer in issuers:
        key = issuer['issuer_symbol']
        if key in seen or key not in REPORT_SYMBOLS or key == '005385':
            raise ValueError('Duplicate/unknown issuer in earnings packet')
        seen.add(key)
        if issuer.get('release_date') and pd.Timestamp(issuer['release_date']) > pd.Timestamp(as_of):
            raise ValueError('Future earnings release')
        for event in issuer.get('event_dates', []):
            if pd.Timestamp(event['date']) > pd.Timestamp(as_of):
                raise ValueError('Future earnings event')
            if not event.get('source_url', '').startswith('https://'):
                raise ValueError('Earnings events require HTTPS source URLs')
            events.append(dict(event, issuer_symbol=key))
    # Avoid double counting a release listed as both headline and calendar row.
    unique = {}
    for event in events:
        key = (event['issuer_symbol'], event['date'])
        if key in unique and unique[key] != event:
            raise ValueError('Conflicting earnings events for the same issuer/date')
        unique[key] = event
    return issuers, sorted(unique.values(), key=lambda e: (e['date'], e['issuer_symbol']))


def analyze(args) -> dict:
    out = args.output
    out.mkdir(parents=True, exist_ok=True)
    legacy_path = args.rolling_input / 'results.json'
    legacy = json.loads(legacy_path.read_text())
    if not 0 <= args.cost_rate < 1 or not np.isclose(args.cost_rate, legacy['metadata']['cost_rate']):
        raise ValueError('Use the same cost rate as the legacy comparison')
    prices = {s: pd.read_csv(args.weekly_input / f'{s}_indicators.csv', parse_dates=['date']) for s in REPORT_SYMBOLS}
    dates = prices[REPORT_SYMBOLS[0]].date.reset_index(drop=True)
    for symbol, frame in prices.items():
        require_unique_trading_dates(frame, source=symbol)
        if not frame.date.equals(dates) or not np.isfinite(frame.close).all() or frame.close.le(0).any():
            raise ValueError(f'{symbol}: invalid prices/calendar')
    benchmark = pd.read_csv(args.rolling_input / '069500_prices.csv')
    benchmark['date'] = pd.to_datetime(benchmark.stck_bsop_date.astype(str), format='%Y%m%d')
    benchmark = benchmark.set_index('date').reindex(dates).reset_index()
    benchmark = benchmark.rename(columns={'stck_clpr': 'close'})
    if not benchmark.date.equals(dates) or benchmark.close.isna().any():
        raise ValueError('Missing benchmark dates')
    features = align_us_features(dates, {s: pd.read_csv(args.us_input / f'{s}.csv') for s in SERIES})
    features.to_csv(out / 'us_aligned.csv', index=False)
    packet = json.loads(args.earnings_file.read_text())
    issuers, events = validated_earnings(packet, args.as_of)
    names = {r['symbol']: r['symbol_name'] for r in legacy['stock_results']}
    stats, reactions, conditions = [], [], []
    window_defs = [dict(id='common-history', length=427, start_date=legacy['metadata']['eligible_start'], end_date=legacy['metadata']['as_of'])]
    window_defs += [w for w in legacy['windows'] if w['end_date'] == legacy['metadata']['as_of'] and w['kind'] != 'full']
    benchmark_return = benchmark.close.pct_change(fill_method=None) * 100
    for symbol, price in prices.items():
        stock_return = price.close.pct_change(fill_method=None) * 100
        for window in window_defs:
            select = dates.gt(pd.Timestamp(window['start_date'])) & dates.le(pd.Timestamp(window['end_date']))
            for series in SERIES:
                row = factor_statistics(stock_return[select], features.loc[select, f'{series}_interval_change'], benchmark_return[select])
                stats.append(dict(symbol=symbol, symbol_name=names[symbol], window_id=window['id'], length=window['length'], start_date=window['start_date'], end_date=window['end_date'], factor=series, factor_unit='bp' if series=='DGS10' else '%', beta_unit='KR return percentage points per factor unit', **row))
        select = dates.gt(pd.Timestamp(legacy['metadata']['eligible_start']))
        for series in ('SP500', 'NASDAQCOM', 'NASDAQSOX'):
            x = features[f'{series}_interval_change']
            for state, mask in [('down', x.le(-1)), ('up', x.ge(1)), ('neutral', x.gt(-1) & x.lt(1))]:
                y = stock_return[select & mask].dropna()
                conditions.append(dict(symbol=symbol, factor=series, state=state, n=len(y), mean_return_pct=float(y.mean()) if len(y) else None, median_return_pct=float(y.median()) if len(y) else None, down_pct=float(y.lt(0).mean()*100) if len(y) else None))
        issuer = '005380' if symbol == '005385' else symbol
        reactions.extend(dict(r, symbol=symbol, symbol_name=names[symbol]) for r in event_reactions(price, benchmark, events, issuer))
    overlays, portfolio = [], []
    eligible = dates.ge(pd.Timestamp(legacy['metadata']['eligible_start']))
    us_blocked = (features.SP500_interval_change.le(-1) | features.SP500_interval_change.isna()).to_numpy()
    counts = {}
    # A sparse release packet is an explicit event sample, not a complete
    # historical earnings calendar. Missing releases are never invented.
    inputs = []
    signal_paths = {(symbol, mid): args.rolling_input / 'signals' / f'{symbol}_{mid}.csv' for symbol in REPORT_SYMBOLS for mid in BASE_MODELS}
    signals = {key: pd.read_csv(path, parse_dates=['date']) for key, path in signal_paths.items()}
    masks_by_symbol = {}
    for symbol in REPORT_SYMBOLS:
        issuer = '005380' if symbol == '005385' else symbol
        earning_blocked = earnings_cooldown(dates, events, issuer)
        masks_by_symbol[symbol] = {'base': np.zeros(len(dates), bool), 'us': us_blocked, 'earnings': earning_blocked, 'combined': us_blocked | earning_blocked}
        for mid in BASE_MODELS:
            signal = signals[(symbol, mid)]
            if not signal.date.equals(dates) or not signal.close.equals(prices[symbol].close):
                raise ValueError(f'{symbol}/{mid}: signal input differs')
    for path in [legacy_path, args.earnings_file, args.rolling_input / '069500_prices.csv',
                 *(args.us_input / f'{s}.csv' for s in SERIES),
                 *(args.weekly_input / f'{s}_indicators.csv' for s in REPORT_SYMBOLS), *signal_paths.values()]:
        inputs.append(dict(path=str(path), sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
    legacy_stock = {(r['window_id'], r['symbol'], r['model_id']): r for r in legacy['stock_results']}
    for window in legacy['windows']:
        a, b = window['start_index'], window['end_index'] + 1
        runs_by_policy = {(mid, mode): [] for mid in BASE_MODELS for mode in OVERLAYS}
        for symbol in REPORT_SYMBOLS:
            masks = masks_by_symbol[symbol]
            for mid in BASE_MODELS:
                signal = signals[(symbol, mid)]
                for mode, mask in masks.items():
                    gated = gate_entries(signal, mask)[eligible].reset_index(drop=True).iloc[a:b].reset_index(drop=True)
                    run = run_signal(symbol, gated, args.cost_rate)
                    metrics = run_metrics(run, args.cost_rate)
                    reference = legacy_stock[(window['id'], symbol, mid)]
                    row = dict(window_id=window['id'], kind=window['kind'], length=window['length'], start_date=window['start_date'], end_date=window['end_date'], symbol=symbol, symbol_name=names[symbol], base_model=mid, overlay=mode, model_id=f'{mid}:{mode}', bh_net_return_pct=reference['bh_net_return_pct'], etf_net_return_pct=reference['etf_net_return_pct'], **metrics)
                    if mode == 'base' and any(not np.isclose(row[field], reference[field], atol=1e-8) for field in ('net_return_pct', 'net_mdd_pct', 'trade_count', 'exposure_pct')):
                        raise ValueError('Stock baseline differs from original backtest')
                    overlays.append(row)
                    runs_by_policy[(mid, mode)].append(run)
                    if window['kind'] == 'full':
                        counts[f'{symbol}:{mid}:{mode}'] = int((signal.signal.eq('buy').to_numpy() & mask & eligible.to_numpy()).sum())
        for (mid, mode), runs in runs_by_policy.items():
            equity = np.mean([r.net for r in runs], axis=0)
            ref = next(r for r in legacy['portfolio_results'] if r['window_id']==window['id'] and r['model_id']==mid)
            row = dict(window_id=window['id'], kind=window['kind'], length=window['length'], start_date=window['start_date'], end_date=window['end_date'], base_model=mid, overlay=mode, model_id=f'{mid}:{mode}', net_return_pct=float((equity[-1]/INITIAL_EQUITY-1)*100), net_mdd_pct=mdd(equity), trade_count=sum(len(r.trades) for r in runs), mean_exposure_pct=float(np.mean([r.exposure.mean() for r in runs])*100), bh_net_return_pct=ref['bh_net_return_pct'], etf_net_return_pct=ref['etf_net_return_pct'])
            if mode == 'base' and any(not np.isclose(row[field], ref[field], atol=1e-8) for field in ('net_return_pct', 'net_mdd_pct', 'trade_count', 'mean_exposure_pct')):
                raise ValueError('Baseline no longer matches original backtest')
            portfolio.append(row)
        print(f"window {window['id']} done", flush=True)
    aggregate = aggregate_results(pd.DataFrame([r for r in portfolio if r['kind']=='rolling']), ['length', 'model_id'])
    for filename, rows in [('factor_statistics.csv',stats),('event_reactions.csv',reactions),('conditional_returns.csv',conditions),('overlay_stock_results.csv',overlays),('overlay_portfolio_results.csv',portfolio),('overlay_aggregates.csv',aggregate)]:
        pd.DataFrame(rows).to_csv(out / filename, index=False)
    coverage = [dict(series=s, first_date=str(normalize_us(pd.read_csv(args.us_input / f'{s}.csv'), s).date.min().date()), last_date=str(normalize_us(pd.read_csv(args.us_input / f'{s}.csv'), s).date.max().date())) for s in SERIES]
    payload = dict(metadata=dict(as_of=args.as_of, price_as_of=legacy['metadata']['as_of'], us_effective_kr_cutoff=str(features.date.max().date()), eligible_start=legacy['metadata']['eligible_start'], generated_at=datetime.now(ZoneInfo('Asia/Seoul')).isoformat(), cost_rate=args.cost_rate, us_assumed_available='17:00 America/New_York; observable market close assumption, not FRED posting time', overlay_rule='SP500 move accumulated between successive KR opens <= -1% or missing => suppress buy signal; verified earnings publication followed by3 KR trading days => suppress buy signal; sells unchanged; existing next-close execution; already pending orders are not canceled', source_files=inputs, us_coverage=coverage, verified_event_count=len(events), calendar_complete=False, verified_events_by_issuer={r['issuer_symbol']: sum(e['issuer_symbol']==r['issuer_symbol'] for e in events) for r in issuers}, analyzable_event_count=len({(r['issuer_symbol'],r['date']) for r in reactions}), baseline_reproduced=True), issuers=issuers, events=events, factors=stats, conditional_returns=conditions, event_reactions=reactions, portfolio_results=portfolio, stock_results=overlays, aggregates=aggregate, suppressed_buy_signals=counts, models=[m for m in legacy['models'] if m['id'] in BASE_MODELS], windows=legacy['windows'])
    enrich_source_metadata(payload, features, args.us_input)
    (out / 'analysis.json').write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=json_default, allow_nan=False))
    return payload


def enrich_source_metadata(payload: dict, features: pd.DataFrame, us_input: Path) -> None:
    """Attach source freshness and interpretation without changing any returns."""
    meta = payload['metadata']
    manifest_path = us_input / 'manifest.json'
    manifest = {row['series']: row for row in json.loads(manifest_path.read_text())} if manifest_path.exists() else {}
    for row in meta['us_coverage']:
        series = row['series']
        date = features[f'{series}_date'].iloc[-1]
        availability = features[f'{series}_available_at'].iloc[-1]
        row.update(effective_observation_date_at_price_cutoff=None if pd.isna(date) else str(pd.Timestamp(date).date()),
                   effective_assumed_available_at=None if pd.isna(availability) else str(availability),
                   saved_at=manifest.get(series, {}).get('retrieved_at') or manifest.get(series, {}).get('saved_at'),
                   source_url=f'https://fred.stlouisfed.org/series/{series}')
    expected = set(REPORT_SYMBOLS) - {'005385'}
    covered = {row['issuer_symbol'] for row in payload['issuers']}
    meta.update(issuer_count=len(covered), missing_issuers=sorted(expected-covered), calendar_complete=False,
                source_assurance='Curated issuer/regulator/company-authored source packet; URL syntax is not source verification',
                verified_events_by_issuer={key: sum(e['issuer_symbol']==key for e in payload['events']) for key in covered},
                analyzable_event_count=len({(r['issuer_symbol'], r['date']) for r in payload['event_reactions']}))
    for row in payload['factors']:
        row.update(factor_unit='bp' if row['factor']=='DGS10' else '%', beta_unit='KR return percentage points per factor unit')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=Path('data/earnings-us/2026-10-19'))
    parser.add_argument('--us-input', type=Path, default=Path('data/earnings-us/2026-10-19/us'))
    parser.add_argument('--weekly-input', type=Path, default=Path('data/weekly-trend/2026-10-13'))
    parser.add_argument('--rolling-input', type=Path, default=Path('data/rolling-backtests/2026-10-13'))
    parser.add_argument('--earnings-file', type=Path, default=Path('data/earnings-us/2026-10-19/earnings.json'))
    parser.add_argument('--as-of', default='2026-10-19')
    parser.add_argument('--cost-rate', type=float, default=.001)
    parser.add_argument('--collect-us', action='store_true')
    args = parser.parse_args()
    if args.collect_us:
        collect_us(args.us_input, '2024-10-01', str(pd.Timestamp(args.as_of).date()))
    analyze(args)


if __name__ == '__main__':
    main()
