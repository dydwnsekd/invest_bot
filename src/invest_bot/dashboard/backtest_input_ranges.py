"""Read-only descriptions of final backtest signal rows and preparation options."""

from __future__ import annotations

import math
from collections.abc import Mapping
from datetime import date, datetime

import pandas as pd

from invest_bot.backtest.dates import local_trading_dates


def unavailable_input_range(reason: str) -> dict[str, object]:
    return {
        "input_range_status": "unavailable", "input_range_reason": reason,
        "input_start_date": None, "input_end_date": None,
        "input_row_count": None, "input_excluded_rows": None,
    }


def signal_input_range(signal_rows: pd.DataFrame) -> dict[str, object]:
    """Describe valid unique daily bars without filtering the runner's input."""
    if not {"date", "close"}.issubset(signal_rows.columns):
        return unavailable_input_range("최종 입력의 날짜·종가 컬럼이 없습니다.")
    dates = local_trading_dates(signal_rows["date"])
    if dates.dropna().duplicated().any():
        return unavailable_input_range("중복 거래일이 있어 고유 일봉 범위를 확인할 수 없습니다.")
    raw_close = signal_rows["close"].reset_index(drop=True)
    unsupported = raw_close.map(lambda value: isinstance(value, (bool, complex, date)))
    close = pd.to_numeric(raw_close.mask(unsupported), errors="coerce")
    valid = dates.notna() & close.notna() & close.gt(0) & close.lt(float("inf"))
    valid_dates = dates[valid]
    return {
        "input_range_status": "known" if not valid_dates.empty else "empty",
        "input_range_reason": "" if not valid_dates.empty else "유효한 날짜·종가의 입력 일봉이 없습니다.",
        "input_start_date": valid_dates.min().isoformat() if not valid_dates.empty else None,
        "input_end_date": valid_dates.max().isoformat() if not valid_dates.empty else None,
        "input_row_count": int(len(valid_dates)),
        "input_excluded_rows": int(len(signal_rows) - len(valid_dates)),
    }


def preparation_selection(
    period: tuple[date, date] | None, *, lookback_days: int | None,
) -> dict[str, object]:
    """Record selected options, never evidence that collection actually ran."""
    return {
        "prepare_selection_start_date": _stored_date(period[0]) if period is not None else None,
        "prepare_selection_end_date": _stored_date(period[1]) if period is not None else None,
        "prepare_lookback_days": lookback_days,
    }


def _stored_date(value: object) -> str | None:
    if value is None or pd.isna(value):
        return None
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    try:
        return date.fromisoformat(str(value)).isoformat()
    except ValueError:
        return None


def _stored_count(value: object) -> int | None:
    if isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return int(number) if math.isfinite(number) and number >= 0 and number.is_integer() else None


def format_input_range(row: Mapping[str, object] | pd.Series) -> str:
    status = row.get("input_range_status")
    if status is None or pd.isna(status):
        return "기록 없음 (실행 당시 입력 범위 미기록)"
    count = _stored_count(row.get("input_row_count"))
    start, end = _stored_date(row.get("input_start_date")), _stored_date(row.get("input_end_date"))
    if status == "known" and start and end and start <= end and count:
        text = f"{start} ~ {end} · 유효 고유 일봉 {count}개"
        excluded = _stored_count(row.get("input_excluded_rows"))
        return text + (f" · 날짜·종가 무효 {excluded}행 제외" if excluded else "")
    if status == "empty" and count == 0:
        return "확인 불가 (유효한 입력 일봉 0개)"
    reason = row.get("input_range_reason")
    return f"확인 불가 ({reason})" if isinstance(reason, str) and reason else "확인 불가 (입력 범위 기록 불완전)"


def format_preparation_selection(row: Mapping[str, object] | pd.Series) -> str:
    start = _stored_date(row.get("prepare_selection_start_date"))
    end = _stored_date(row.get("prepare_selection_end_date"))
    days = _stored_count(row.get("prepare_lookback_days"))
    if not start or not end or start > end or not days:
        return "기록 없음 (실행 당시 준비용 선택 범위 미기록)"
    return f"{start} ~ {end} · 준비용 조회 옵션 {days}일 (수집 실행 증거 아님)"
