from __future__ import annotations

from datetime import date, timedelta
from typing import Sequence

from invest_bot.jobs.collect_market_data import DEFAULT_COLLECTION_LOOKBACK_DAYS, MIN_REQUIRED_TRADING_DAYS

MAX_COLLECTION_LOOKBACK_DAYS = 3650


def default_collection_period(*, today: date | None = None) -> tuple[date, date]:
    end_date = today or date.today()
    return (end_date - timedelta(days=DEFAULT_COLLECTION_LOOKBACK_DAYS), end_date)


def normalize_collection_period(value: object, *, today: date | None = None) -> tuple[date, date]:
    fallback = default_collection_period(today=today)
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)) or len(value) != 2:
        return fallback
    start_date, end_date = value
    if not isinstance(start_date, date) or not isinstance(end_date, date):
        return fallback
    if start_date > end_date:
        return (end_date, start_date)
    return (start_date, end_date)


def collection_days_from_period(period: tuple[date, date]) -> int:
    start_date, end_date = period
    return max(MIN_REQUIRED_TRADING_DAYS, min((end_date - start_date).days, MAX_COLLECTION_LOOKBACK_DAYS))


def collection_period_bounds(*, today: date | None = None) -> tuple[date, date]:
    end_date = today or date.today()
    return (end_date - timedelta(days=MAX_COLLECTION_LOOKBACK_DAYS), end_date)
