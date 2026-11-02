"""Bounded regular price collection and explicit coverage evidence."""
from __future__ import annotations

import re
import time
from datetime import date, datetime, timedelta
from math import ceil, isfinite

import pandas as pd


class HistoryCollectionError(ValueError):
    pass


def normalize_history_frame(merged: pd.DataFrame, kind: str) -> pd.DataFrame:
    """Keep the explicit backfill's numeric/OHLC/duplicate validation contract."""
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
    return merged.drop_duplicates('stck_bsop_date').sort_values('stck_bsop_date').reset_index(drop=True)


def assess_price_coverage(prices, start, end, *, listing_date=None, expected_dates=None, request_complete=False):
    """Do not infer holidays, listing or halts from missing observations."""
    observed = {datetime.strptime(value, '%Y%m%d').date() for value in prices.get('stck_bsop_date', [])}
    first, last = (min(observed), max(observed)) if observed else (None, None)
    result = dict(status='unknown', reason='unverified_boundaries', requested_start=start.isoformat(),
                  requested_end=end.isoformat(), effective_start=start.isoformat(),
                  observed_start=first.isoformat() if first else '', observed_end=last.isoformat() if last else '',
                  rows=len(observed), requests=0, termination='windows_exhausted', window_count=0,
                  listing_date='', expected_sessions=None, request_complete=request_complete,
                  trading_days_verified=False, range_reason='unverified_boundaries')
    if not request_complete:
        result.update(reason='requests_not_completed', range_reason='requests_not_completed')
        return result
    if observed:
        result.update(status='complete', reason='bounded_windows_exhausted')
    effective_start = start
    invalid_listing = False
    if listing_date is not None:
        if not isinstance(listing_date, date) or isinstance(listing_date, datetime) or listing_date > date.today() or listing_date > end:
            result['range_reason'] = 'invalid_or_future_listing_date'
            invalid_listing = True
        else:
            result['listing_date'] = listing_date.isoformat()
            effective_start = max(start, listing_date)
            result['effective_start'] = effective_start.isoformat()
            if first is not None and first < listing_date:
                result.update(status='incomplete', reason='listing_observation_conflict', range_reason='listing_observation_conflict')
                return result
    if expected_dates is not None:
        expected_dates = list(expected_dates)
        if any(not isinstance(d, date) or isinstance(d, datetime) or d < start or d > end for d in expected_dates):
            result.update(status='unknown', reason='invalid_calendar_evidence', range_reason='invalid_calendar_evidence')
            return result
        expected = {d for d in expected_dates if d >= effective_start}
        result['expected_sessions'] = len(expected)
        if observed != expected:
            result.update(status='incomplete', reason='calendar_observation_mismatch', range_reason='calendar_observation_mismatch')
        else:
            why = 'calendar_observations_match' if expected else 'calendar_no_sessions'
            result.update(status='complete', reason=why, range_reason=why, trading_days_verified=True)
        return result
    if not observed:
        result.update(reason='no_observations_without_calendar', range_reason='no_observations_without_calendar')
    elif invalid_listing:
        return result
    elif first == effective_start and last == end:
        result['range_reason'] = 'verified_listing_date' if effective_start > start else 'observed_boundaries'
    elif last != end:
        result['range_reason'] = 'unverified_end_boundary'
    else:
        result['range_reason'] = 'unverified_start_boundary'
    return result


def listing_date_evidence(stock_info, symbol):
    if stock_info.empty:
        return None, 'listing_metadata_unavailable'
    row = stock_info.iloc[0]
    if str(row.get('pdno', '')).strip().zfill(6) != str(symbol).strip().zfill(6):
        return None, 'listing_symbol_mismatch'
    raw = [row.get(key) for key in ('scts_mket_lstg_dt', 'kosdaq_mket_lstg_dt')]
    values = [str(value).strip() for value in raw if pd.api.types.is_scalar(value) and value is not None and not pd.isna(value)]
    values = [v for v in values if v not in {'', '00000000'}]
    if not values:
        return None, 'listing_metadata_unavailable'
    if len(values) != 1:
        return None, 'ambiguous_listing_dates'
    try:
        if not re.fullmatch(r'[0-9]{8}', values[0]):
            raise ValueError
        return datetime.strptime(values[0], '%Y%m%d').date(), ''
    except ValueError:
        return None, 'invalid_listing_date'


class PriceHistoryError(HistoryCollectionError):
    def __init__(self, reason, coverage):
        self.coverage = dict(coverage, status='incomplete', reason=reason, termination=reason, request_complete=False)
        super().__init__(f'Daily price history: {reason}')


class DailyPriceHistoryFetcher:
    """At most 100 calendar dates per call: no trading-day count assumptions."""
    PAGE_LIMIT = 100  # Official KIS inquire-daily-itemchartprice maximum rows.

    def __init__(self, client, *, interval=1.1, max_pages=100, clock=None, sleep=None, calendar=None):
        if isinstance(interval, bool) or not isfinite(interval) or interval < 0:
            raise ValueError('interval must be finite and nonnegative')
        if isinstance(max_pages, bool) or not isinstance(max_pages, int) or max_pages < 1:
            raise ValueError('max_pages must be a positive integer')
        self.client, self.interval, self.max_pages = client, interval, max_pages
        self.clock, self.sleep = clock or time.monotonic, sleep or time.sleep
        self.calendar = calendar
        self.last_request_at = float('-inf')

    def collect(self, request):
        start, end = request.start_date, request.end_date
        coverage = assess_price_coverage(pd.DataFrame(), start, end)
        if start > end:
            raise PriceHistoryError('invalid_range', coverage)
        coverage['window_count'] = ceil(((end - start).days + 1) / self.PAGE_LIMIT)
        if coverage['window_count'] > self.max_pages:
            raise PriceHistoryError('page_limit', coverage)
        cursor, chunks, summary = end, [], pd.DataFrame()
        while cursor >= start:
            lower = cursor - timedelta(days=min(self.PAGE_LIMIT - 1, (cursor - start).days))
            delay = self.interval - (self.clock() - self.last_request_at)
            if delay > 0:
                self.sleep(delay)
            self.last_request_at = self.clock()
            coverage['requests'] += 1
            try:
                payload = self.client.get_json(
                    '/uapi/domestic-stock/v1/quotations/inquire-daily-itemchartprice', 'FHKST03010100',
                    dict(FID_COND_MRKT_DIV_CODE=request.market_code, FID_INPUT_ISCD=request.symbol,
                         FID_INPUT_DATE_1=lower.strftime('%Y%m%d'), FID_INPUT_DATE_2=cursor.strftime('%Y%m%d'),
                         FID_PERIOD_DIV_CODE=request.period_code, FID_ORG_ADJ_PRC='0' if request.adjusted_price else '1'))
            except Exception:
                raise PriceHistoryError('request_error', coverage) from None
            if not isinstance(payload, dict) or str(payload.get('rt_cd')) != '0':
                raise PriceHistoryError('api_error', coverage)
            rows = payload.get('output2')
            if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
                raise PriceHistoryError('invalid_response', coverage)
            if len(rows) > self.PAGE_LIMIT:
                raise PriceHistoryError('response_limit_exceeded', coverage)
            if coverage['requests'] == 1:
                raw_summary = payload.get('output1') or {}
                if not isinstance(raw_summary, (dict, list)) or (isinstance(raw_summary, list) and any(not isinstance(r, dict) for r in raw_summary)):
                    raise PriceHistoryError('invalid_summary', coverage)
                summary = pd.DataFrame(raw_summary if isinstance(raw_summary, list) else [raw_summary])
            frame = pd.DataFrame(rows)
            if not frame.empty:
                if 'stck_bsop_date' not in frame:
                    raise PriceHistoryError('invalid_date', coverage)
                text = frame['stck_bsop_date'].astype(str).str.strip()
                parsed = pd.to_datetime(text, format='%Y%m%d', errors='coerce')
                if not text.str.fullmatch(r'[0-9]{8}').all() or parsed.isna().any():
                    raise PriceHistoryError('invalid_date', coverage)
                if ((parsed.dt.date < lower) | (parsed.dt.date > cursor)).any():
                    raise PriceHistoryError('out_of_window_no_progress', coverage)
                frame['stck_bsop_date'] = text
                core = ['stck_oprc', 'stck_hgpr', 'stck_lwpr', 'stck_clpr', 'acml_vol']
                try:
                    if any(c not in frame for c in core) or any(
                        not pd.api.types.is_scalar(v) or isinstance(v, bool) for c in core for v in frame[c]
                    ):
                        raise HistoryCollectionError('Invalid numeric cells')
                    frame = normalize_history_frame(frame, 'price')
                    volume = pd.to_numeric(frame['acml_vol'])
                    if (volume % 1 != 0).any():
                        raise HistoryCollectionError('Noninteger volume')
                except (HistoryCollectionError, TypeError, ValueError, OverflowError):
                    raise PriceHistoryError('invalid_or_conflicting_observations', coverage) from None
                if len(rows) == self.PAGE_LIMIT and len(frame) < len(rows):
                    raise PriceHistoryError('saturated_duplicate_page', coverage)
                chunks.append(frame)
                coverage['rows'] += len(frame)
                first, last = parsed.min().date().isoformat(), parsed.max().date().isoformat()
                coverage['observed_start'] = min(coverage['observed_start'] or first, first)
                coverage['observed_end'] = max(coverage['observed_end'] or last, last)
            if lower == start:
                break
            cursor = lower - timedelta(days=1)
        merged = pd.concat(chunks, ignore_index=True).sort_values('stck_bsop_date').reset_index(drop=True) if chunks else pd.DataFrame()
        try:
            expected = self.calendar(start, end) if self.calendar is not None else None
            if expected is not None:
                expected = list(expected)
        except Exception:
            raise PriceHistoryError('calendar_error', coverage) from None
        assessed = assess_price_coverage(merged, start, end, expected_dates=expected, request_complete=True)
        assessed.update(requests=coverage['requests'], window_count=coverage['window_count'])
        merged.attrs['price_coverage'] = assessed
        return summary, merged
