"""Pure order values. No settings, transport, storage or real clock."""
from dataclasses import dataclass, fields
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from enum import StrEnum
import hashlib
import json
import re


ORDER_TARGETS = frozenset({"dry_run", "kis_mock"})


class Side(StrEnum):
    BUY = "BUY"
    SELL = "SELL"


class ReasonCode(StrEnum):
    MODE_NOT_ALLOWED = "MODE_NOT_ALLOWED"
    INVALID_ORDER = "INVALID_ORDER"
    POLICY_REQUIRED = "POLICY_REQUIRED"
    SNAPSHOT_INVALID = "SNAPSHOT_INVALID"
    MARKET_UNAVAILABLE = "MARKET_UNAVAILABLE"
    RECONCILIATION_REQUIRED = "RECONCILIATION_REQUIRED"
    INSUFFICIENT_CASH = "INSUFFICIENT_CASH"
    INSUFFICIENT_POSITION = "INSUFFICIENT_POSITION"
    LIMIT_EXCEEDED = "LIMIT_EXCEEDED"
    IDEMPOTENCY_CONFLICT = "IDEMPOTENCY_CONFLICT"


class OrderState(StrEnum):
    REJECTED = "REJECTED"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    BROKER_REJECTED = "BROKER_REJECTED"
    UNKNOWN = "UNKNOWN"


class VirtualOutcome(StrEnum):
    ACKNOWLEDGED = "ACKNOWLEDGED"
    BROKER_REJECTED = "BROKER_REJECTED"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True, slots=True, repr=False)
class AccountBinding:
    alias: str
    binding_id: str
    version: str
    mode: str
    execution_target: str


@dataclass(frozen=True, slots=True, repr=False)
class OrderIntent:
    schema_version: int
    client_order_id: str
    execution_target: str
    mode: str
    account_alias: str
    account_binding_id: str
    binding_version: str
    symbol: str
    side: Side
    qty: int
    limit_price: Decimal
    currency: str
    market: str
    order_type: str
    source_id: str
    created_at: datetime
    expires_at: datetime


@dataclass(frozen=True, slots=True, repr=False)
class RiskPolicy:
    version: str
    execution_target: str
    mode: str
    allowed_symbols: frozenset[str]
    allowed_markets: frozenset[str]
    allowed_sessions: frozenset[str]
    max_order_notional: Decimal
    max_symbol_exposure: Decimal
    max_account_exposure: Decimal
    max_fee: Decimal
    max_open_orders: int
    buy_fee_rate: Decimal
    sell_fee_rate: Decimal
    buy_fixed_fee: Decimal
    sell_fixed_fee: Decimal
    cost_quantum: Decimal
    max_request_age: timedelta
    max_request_lifetime: timedelta
    max_snapshot_age: timedelta
    max_market_age: timedelta
    max_valuation_age: timedelta


@dataclass(frozen=True, slots=True, repr=False)
class Position:
    symbol: str
    sellable_qty: int
    market_value: Decimal
    open_buy_value: Decimal


@dataclass(frozen=True, slots=True, repr=False)
class AccountSnapshot:
    version: str
    execution_target: str
    mode: str
    account_alias: str
    account_binding_id: str
    binding_version: str
    currency: str
    captured_at: datetime
    complete: bool
    reservations_complete: bool
    available_cash: Decimal
    positions: tuple[Position, ...]
    account_exposure: Decimal
    open_order_count: int
    valuation_at: datetime
    valuation_source_id: str
    book_id: str
    reservation_watermark: int
    included_reservation_ids: frozenset[str]


@dataclass(frozen=True, slots=True, repr=False)
class MarketSnapshot:
    version: str
    execution_target: str
    mode: str
    symbol: str
    market: str
    currency: str
    captured_at: datetime
    complete: bool
    tradable: bool
    session: str
    calendar_source_id: str
    calendar_version: str
    tick_size: Decimal
    min_price: Decimal
    max_price: Decimal


@dataclass(frozen=True, slots=True)
class Reservation:
    order_id: str
    account_binding_id: str
    symbol: str
    side: Side
    cash: Decimal
    qty: int
    exposure: Decimal
    sequence: int


@dataclass(frozen=True, slots=True)
class ReservationBook:
    book_id: str
    revision: int
    entries: tuple[Reservation, ...]


@dataclass(frozen=True, slots=True)
class RiskDecision:
    allowed: bool
    reasons: tuple[ReasonCode, ...]
    policy_version: str | None
    account_version: str | None
    market_version: str | None
    fingerprint: str | None
    reserve_cash: Decimal
    reserve_qty: int
    reserve_exposure: Decimal
    book_revision: int | None = None


@dataclass(frozen=True, slots=True)
class OrderRecord:
    order_id: str | None
    state: OrderState
    decision: RiskDecision
    fingerprint: str | None
    reserved_cash: Decimal
    reserved_qty: int
    execution_target: str = "dry_run"
    client_order_id: str | None = None
    account_binding_id: str | None = None
    binding_version: str | None = None
    evaluated_at: datetime | None = None


def valid_id(value: object) -> bool:
    return type(value) is str and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}", value) is not None


def aware(value: object) -> bool:
    try:
        return (type(value) is datetime and type(value.tzinfo) is timezone
                and value.utcoffset() is not None)
    except Exception:
        return False


def order_key(intent: object, *, execution_target: str = "dry_run") -> tuple[str, str, str, str] | None:
    if (type(execution_target) is str and execution_target in ORDER_TARGETS
            and type(intent) is OrderIntent and type(intent.mode) is str and intent.mode == "mock"
            and type(intent.execution_target) is str and intent.execution_target == execution_target
            and valid_id(intent.account_binding_id) and valid_id(intent.client_order_id)):
        return intent.execution_target, intent.mode, intent.account_binding_id, intent.client_order_id
    return None


def order_fingerprint(intent: object) -> str | None:
    """No repr/str of arbitrary input. Unsupported values get an opaque marker.

    Opaque markers give process-local denial replay only, not a wire format or
    cross-process equivalence guarantee. They can never turn an invalid value
    into an accepted order. All accepted values have canonical typed encoding.
    """
    if type(intent) is not OrderIntent:
        return None
    try:
        encoded = []
        for field in fields(OrderIntent):
            value = getattr(intent, field.name)
            if type(value) is Decimal:
                sign, digits, exponent = value.as_tuple()
                digits = list(digits)
                if value.is_finite():
                    while digits and digits[-1] == 0:
                        digits.pop(); exponent += 1
                    if not digits:
                        sign, exponent = 0, 0
                atom = ["decimal", sign, digits, exponent]
            elif type(value) is datetime:
                if aware(value):
                    atom = ["datetime", value.astimezone(timezone.utc).isoformat()]
                elif value.tzinfo is None:
                    atom = ["invalid-naive-time", value.isoformat()]
                else:
                    atom = ["invalid-timezone", id(value)]
            elif type(value) is Side:
                atom = ["str", value.value]
            elif type(value) is float:
                atom = ["invalid-float", value.hex()]
            elif type(value) in (str, int, bool) or value is None:
                atom = [type(value).__name__, value]
            else:
                atom = ["invalid-opaque", id(value)]
            encoded.append([field.name, atom])
        raw = json.dumps(["t06b-intent-v1", encoded], ensure_ascii=True, separators=(",", ":"))
        return hashlib.sha256(raw.encode("ascii")).hexdigest()
    except Exception:
        return None
