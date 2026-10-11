"""Calendar-date uniqueness for per-symbol daily backtest inputs."""

from __future__ import annotations

from datetime import date, datetime

import pandas as pd


def duplicate_trading_date_reason(
    frame: pd.DataFrame,
    column: str = "date",
    *,
    source: str,
) -> str | None:
    """Report repeated valid dates without selecting rows or changing input.

    Preserve already-parsed local dates before vectorized parsing of other
    values: pandas can coerce valid mixed-offset Timestamps to NaT. No UTC
    conversion is used. Invalid/NaT values are not dates; existing consumers
    retain their own handling of those rows.
    """
    if column not in frame.columns or frame.empty:
        return None
    values = frame[column]
    already_parsed = values.map(lambda value: isinstance(value, date))
    dates = values[already_parsed].dropna().map(lambda value: value.date() if isinstance(value, datetime) else value)
    parsed = pd.to_datetime(values[~already_parsed], errors="coerce", format="mixed")
    dates = pd.concat([dates, parsed.dropna().map(lambda value: value.date())], ignore_index=True)
    duplicates = sorted(set(dates[dates.duplicated()]))
    if not duplicates:
        return None
    sample = ", ".join(value.isoformat() for value in duplicates[:3])
    suffix = "" if len(duplicates) <= 3 else f" (+{len(duplicates) - 3} more)"
    return (
        f"{source} has duplicate trading dates: {sample}{suffix}; "
        "daily backtests require one row per trading date"
    )


def require_unique_trading_dates(frame: pd.DataFrame, column: str = "date", *, source: str) -> None:
    reason = duplicate_trading_date_reason(frame, column, source=source)
    if reason:
        raise ValueError(reason)
