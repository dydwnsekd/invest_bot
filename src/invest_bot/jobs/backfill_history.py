"""Explicit historical backfill; does not change the regular scheduler."""
from __future__ import annotations

import argparse
import json
import time
from math import isfinite
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import pandas as pd
import requests

from invest_bot.clients.kis_client import KISClient
from invest_bot.config.settings import AppSettings
from invest_bot.db.frame_storage import DbFrameStorage
from invest_bot.db.write_path import SqlAlchemyMarketDataWriter
from invest_bot.jobs.analyze_daily_prices import generate_indicators_for_symbol
from invest_bot.jobs.run_golden_cross_signals import generate_golden_cross_signals_for_symbol
from invest_bot.jobs.run_market_report import generate_market_report_for_symbol


class HistoryCollectionError(ValueError):
    pass


@dataclass
class HistoryResult:
    frame: pd.DataFrame
    latest_summary: pd.DataFrame
    pages: int
    termination: str


class HistoryFetcher:
    """Move the query end backwards; retain only the requested date window."""

    def __init__(self, client, *, interval: float = 1.1, max_pages: int = 100):
        self.client = client
        self.interval = interval
        self.max_pages = max_pages
        self.last_request_at = float('-inf')

    def _request(self, path, tr_id, params):
        for attempt in range(3):
            delay = self.interval - (time.monotonic() - self.last_request_at)
            if delay > 0:
                time.sleep(delay)
            self.last_request_at = time.monotonic()
            try:
                payload = self.client.get_json(path, tr_id, params)
                if str(payload.get('rt_cd')) != '0':
                    raise HistoryCollectionError(f"KIS response error: {payload.get('msg_cd', 'missing_status')}")
                return payload
            except (requests.RequestException, HistoryCollectionError):
                if attempt == 2:
                    raise
                time.sleep(2 ** attempt)
        raise AssertionError('unreachable')

    def collect(self, kind: str, symbol: str, start: date, end: date) -> HistoryResult:
        if start > end:
            raise ValueError('start must be on or before end')
        if kind not in {'price', 'investor'}:
            raise ValueError('kind must be price or investor')
        cursor = end
        chunks = []
        first_summary = pd.DataFrame()
        termination = ''
        for page_number in range(1, self.max_pages + 1):
            params = {'FID_COND_MRKT_DIV_CODE': 'J', 'FID_INPUT_ISCD': symbol}
            if kind == 'price':
                path = '/uapi/domestic-stock/v1/quotations/inquire-daily-itemchartprice'
                tr_id = 'FHKST03010100'
                params.update(FID_INPUT_DATE_1=start.strftime('%Y%m%d'), FID_INPUT_DATE_2=cursor.strftime('%Y%m%d'), FID_PERIOD_DIV_CODE='D', FID_ORG_ADJ_PRC='0')
            else:
                path = '/uapi/domestic-stock/v1/quotations/investor-trade-by-stock-daily'
                tr_id = 'FHPTJ04160001'
                params.update(FID_INPUT_DATE_1=cursor.strftime('%Y%m%d'), FID_ORG_ADJ_PRC='', FID_ETC_CLS_CODE='')
            payload = self._request(path, tr_id, params)
            if page_number == 1:
                summary = payload.get('output1') or []
                first_summary = pd.DataFrame(summary if isinstance(summary, list) else [summary])
            rows = payload.get('output2') or []
            frame = pd.DataFrame(rows if isinstance(rows, list) else [rows])
            if frame.empty:
                termination = 'empty_page'
                break
            if 'stck_bsop_date' not in frame:
                raise HistoryCollectionError('Missing observation date column')
            frame = frame[frame['stck_bsop_date'].astype(str).str.strip().ne('')].copy()
            if frame.empty:
                termination = 'empty_page'
                break
            dates = pd.to_datetime(frame['stck_bsop_date'].astype(str), format='%Y%m%d', errors='coerce')
            if dates.isna().any():
                raise HistoryCollectionError('Invalid observation date')
            if dates.max().date() > cursor:
                raise HistoryCollectionError('Response exceeded query end; pagination made no progress')
            earliest = dates.min().date()
            frame = frame[(dates.dt.date >= start) & (dates.dt.date <= end)]
            if not frame.empty:
                chunks.append(frame)
            if earliest <= start:
                termination = 'start_reached'
                break
            cursor = earliest - timedelta(days=1)
            if cursor < start:
                termination = 'start_reached'
                break
        else:
            raise HistoryCollectionError('Maximum historical pages reached before exhaustion')
        if not chunks:
            raise HistoryCollectionError('No observations in requested window')
        merged = pd.concat(chunks, ignore_index=True)
        core = ['stck_clpr', 'stck_oprc', 'stck_hgpr', 'stck_lwpr', 'acml_vol'] if kind == 'price' else ['frgn_ntby_qty', 'orgn_ntby_qty', 'prsn_ntby_qty']
        numeric = {}
        for col in core:
            if col not in merged or pd.to_numeric(merged[col], errors='coerce').isna().any():
                raise HistoryCollectionError(f'Missing or invalid values: {col}')
            numeric[col] = pd.to_numeric(merged[col])
            if not numeric[col].map(isfinite).all():
                raise HistoryCollectionError(f'Nonfinite value: {col}')
        if kind == 'price':
            if (numeric['stck_clpr'] <= 0).any() or any((numeric[col] < 0).any() for col in core):
                raise HistoryCollectionError('Nonpositive close or negative price/volume')
            active = numeric['acml_vol'] > 0
            high = numeric['stck_hgpr']; low = numeric['stck_lwpr']
            if any(((values <= 0) & active).any() for key,values in numeric.items() if key != 'acml_vol'):
                raise HistoryCollectionError('Invalid active-trading price')
            if any(((values > high) & active).any() or ((values < low) & active).any() for key,values in numeric.items() if key != 'acml_vol'):
                raise HistoryCollectionError('Invalid OHLC relationship')
        for _, group in merged[merged.duplicated('stck_bsop_date', keep=False)].groupby('stck_bsop_date'):
            if any(pd.to_numeric(group[c]).nunique(dropna=False) != 1 for c in core):
                raise HistoryCollectionError('Conflicting duplicate observations')
        merged = merged.drop_duplicates('stck_bsop_date').sort_values('stck_bsop_date').reset_index(drop=True)
        return HistoryResult(merged, first_summary, page_number, termination)


def verify_first_window(fetcher, kind, symbol, start, end, result):
    """An empty tail alone does not prove a long requested period was reached."""
    if (end - start).days <= 31:
        return
    first = fetcher.collect(kind, symbol, start, start + timedelta(days=31))
    first_dates = set(first.frame['stck_bsop_date'])
    result_dates = set(result.frame['stck_bsop_date'])
    if not first_dates.issubset(result_dates) or min(first_dates) != min(result_dates):
        raise HistoryCollectionError('Requested-period beginning missing from collected history')


def backfill_symbol(symbol, start, end, fetcher, storage, writer=None):
    price = fetcher.collect('price', symbol, start, end)
    today = datetime.now(ZoneInfo('Asia/Seoul')).date()
    investor_end = end - timedelta(days=1) if end >= today else end
    investor = fetcher.collect('investor', symbol, start, investor_end)
    verify_first_window(fetcher, 'price', symbol, start, end, price)
    verify_first_window(fetcher, 'investor', symbol, start, investor_end, investor)
    price_dates = set(price.frame['stck_bsop_date'])
    investor_dates = set(investor.frame['stck_bsop_date'])
    missing_investor = sorted(d for d in price_dates - investor_dates if d <= investor_end.strftime('%Y%m%d'))
    suffix = f'{symbol}_{start:%Y%m%d}_{end:%Y%m%d}_history.csv'
    investor_suffix = f'{symbol}_{start:%Y%m%d}_{investor_end:%Y%m%d}_history.csv'
    # New snapshot names preserve the previously collected short snapshots.
    storage.save('daily_prices_summary', suffix, price.latest_summary)
    storage.save('daily_prices', suffix, price.frame)
    storage.save('investor_daily', investor_suffix, investor.latest_summary)
    storage.save('investor_daily_summary', investor_suffix, investor.frame)
    if writer is not None:
        writer.save_daily_prices(symbol, start, end, price.latest_summary, price.frame)
        writer.save_investor_daily(symbol, investor_end, investor.latest_summary, investor.frame)
    return {
        'symbol': symbol, 'requested_start': str(start), 'requested_end': str(end),
        'price_rows': len(price.frame), 'price_start': price.frame.iloc[0]['stck_bsop_date'], 'price_end': price.frame.iloc[-1]['stck_bsop_date'],
        'investor_rows': len(investor.frame), 'investor_start': investor.frame.iloc[0]['stck_bsop_date'], 'investor_end': investor.frame.iloc[-1]['stck_bsop_date'],
        'price_pages': price.pages, 'investor_pages': investor.pages,
        'price_termination': price.termination, 'investor_termination': investor.termination,
        'missing_investor_dates': missing_investor, 'beginning_verified': True,
        'price_filename': suffix, 'investor_filename': investor_suffix,
    }


def main():
    parser = argparse.ArgumentParser(description='Backfill price and investor history in date windows; no Discord delivery.')
    parser.add_argument('symbols', nargs='*', help='Defaults to symbols with saved market reports.')
    parser.add_argument('--start', type=date.fromisoformat, required=True)
    parser.add_argument('--end', type=date.fromisoformat, required=True)
    args = parser.parse_args()
    if args.start > args.end:
        parser.error('--start must be on or before --end')
    settings = AppSettings.from_file()
    storage = DbFrameStorage.from_settings(settings)
    symbols = list(dict.fromkeys(args.symbols or [r.symbol for r in storage.repository.list_latest(['market_reports']) if r.symbol]))
    if not symbols:
        parser.error('No symbols selected')
    writer = SqlAlchemyMarketDataWriter(settings.database_url, default_market=settings.market) if settings.enable_db_write else None
    fetcher = HistoryFetcher(KISClient(settings))
    results = []
    for symbol in symbols:
        try:
            result = backfill_symbol(symbol, args.start, args.end, fetcher, storage, writer)
            generate_indicators_for_symbol(symbol)
            generate_golden_cross_signals_for_symbol(symbol)
            result['report'] = generate_market_report_for_symbol(symbol, delivery_target='none')
            result['status'] = 'success'
        except Exception as error:
            result = {'symbol': symbol, 'status': 'failed', 'error': str(error)}
        results.append(result)
        print(json.dumps(result, ensure_ascii=False, default=str), flush=True)
    print('FINAL_JSON ' + json.dumps({'results': results, 'success_count': sum(r['status']=='success' for r in results), 'failed_count': sum(r['status']=='failed' for r in results)}, ensure_ascii=False, default=str), flush=True)
    if any(r['status']=='failed' for r in results):
        raise SystemExit(1)


if __name__ == '__main__':
    main()
