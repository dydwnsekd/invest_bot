"""Deterministic, explicit-input validation for the virtual-only order scope."""
from dataclasses import replace
from datetime import timedelta
from decimal import Decimal
from fractions import Fraction

from ..trading.models import (
    AccountBinding, AccountSnapshot, MarketSnapshot, OrderIntent, Position,
    ReasonCode, Reservation, ReservationBook, RiskDecision, RiskPolicy, Side,
    aware, order_fingerprint, valid_id,
)

ZERO = Decimal(0)


def _money(value, *, positive=False):
    return type(value) is Decimal and value.is_finite() and (value > 0 if positive else value >= 0)


def _integer(value, *, positive=False):
    return type(value) is int and (value > 0 if positive else value >= 0)


def _ids(value):
    return type(value) is frozenset and bool(value) and all(valid_id(item) for item in value)


def _fresh(at, now, age):
    return aware(at) and at <= now and now - at <= age


def _decimal(value: Fraction) -> Decimal:
    """Exact finite decimal, independent of the caller's Decimal context."""
    numerator, denominator = value.numerator, value.denominator
    twos = fives = 0
    while denominator % 2 == 0:
        denominator //= 2; twos += 1
    while denominator % 5 == 0:
        denominator //= 5; fives += 1
    if denominator != 1:
        raise ValueError("Non-finite decimal arithmetic")
    scale = max(twos, fives)
    coefficient = abs(numerator) * 2 ** (scale - twos) * 5 ** (scale - fives)
    return Decimal((int(numerator < 0), tuple(int(digit) for digit in str(coefficient)), -scale))


def _binding_valid(binding):
    return (type(binding) is AccountBinding and all(valid_id(value) for value in (binding.alias, binding.binding_id, binding.version))
            and type(binding.mode) is str and binding.mode == "mock"
            and type(binding.execution_target) is str and binding.execution_target == "dry_run")


def _policy_valid(policy):
    if type(policy) is not RiskPolicy:
        return False
    money = (policy.max_order_notional, policy.max_symbol_exposure, policy.max_account_exposure, policy.max_fee,
             policy.buy_fee_rate, policy.sell_fee_rate, policy.buy_fixed_fee, policy.sell_fixed_fee)
    ages = (policy.max_request_age, policy.max_request_lifetime, policy.max_snapshot_age, policy.max_market_age, policy.max_valuation_age)
    return (valid_id(policy.version) and type(policy.mode) is str and policy.mode == "mock"
            and type(policy.execution_target) is str and policy.execution_target == "dry_run"
            and all(_ids(items) for items in (policy.allowed_symbols, policy.allowed_markets, policy.allowed_sessions))
            and all(_money(value) for value in money) and _money(policy.cost_quantum, positive=True)
            and _integer(policy.max_open_orders) and all(type(age) is timedelta and age >= timedelta(0) for age in ages))


def _book_valid(book):
    if type(book) is not ReservationBook or not valid_id(book.book_id) or not _integer(book.revision) or type(book.entries) is not tuple:
        return False
    for entry in book.entries:
        if (type(entry) is not Reservation or not all(valid_id(v) for v in (entry.order_id, entry.account_binding_id, entry.symbol))
                or type(entry.side) is not Side or not _money(entry.cash) or not _money(entry.exposure)
                or not _integer(entry.qty) or not _integer(entry.sequence, positive=True) or entry.sequence > book.revision):
            return False
        if entry.side is Side.BUY and not (entry.qty == 0 and entry.exposure > 0 and entry.cash >= entry.exposure):
            return False
        if entry.side is Side.SELL and not (entry.qty > 0 and entry.exposure == 0):
            return False
    return len({e.order_id for e in book.entries}) == len(book.entries) == len({e.sequence for e in book.entries})


def _account_valid(account, binding, policy, book, now):
    if type(account) is not AccountSnapshot or not _book_valid(book):
        return False
    if (not all(valid_id(v) for v in (account.version, account.valuation_source_id, account.book_id))
            or type(account.execution_target) is not str or account.execution_target != "dry_run"
            or type(account.mode) is not str or account.mode != "mock" or type(account.currency) is not str or account.currency != "KRW"
            or any(type(v) is not str for v in (account.account_alias, account.account_binding_id, account.binding_version))
            or (account.account_alias, account.account_binding_id, account.binding_version) != (binding.alias, binding.binding_id, binding.version)
            or account.complete is not True or account.reservations_complete is not True
            or not _fresh(account.captured_at, now, policy.max_snapshot_age)
            or not _fresh(account.valuation_at, now, policy.max_valuation_age)
            or not _money(account.available_cash) or not _money(account.account_exposure)
            or not _integer(account.open_order_count) or type(account.positions) is not tuple
            or account.book_id != book.book_id or not _integer(account.reservation_watermark)
            or account.reservation_watermark > book.revision or type(account.included_reservation_ids) is not frozenset
            or not all(valid_id(v) for v in account.included_reservation_ids)):
        return False
    for position in account.positions:
        if (type(position) is not Position or not valid_id(position.symbol) or not _integer(position.sellable_qty)
                or not _money(position.market_value) or not _money(position.open_buy_value)
                or (position.sellable_qty > 0 and position.market_value <= 0)):
            return False
    if len({p.symbol for p in account.positions}) != len(account.positions):
        return False
    if sum((Fraction(p.market_value) + Fraction(p.open_buy_value) for p in account.positions), Fraction(0)) != Fraction(account.account_exposure):
        return False
    included = tuple(e for e in book.entries if e.account_binding_id == binding.binding_id and e.sequence <= account.reservation_watermark)
    if account.included_reservation_ids != frozenset(e.order_id for e in included) or account.open_order_count < len(included):
        return False
    for entry in included:
        if entry.side is Side.BUY:
            needed = sum((Fraction(e.exposure) for e in included if e.side is Side.BUY and e.symbol == entry.symbol), Fraction(0))
            captured = sum((Fraction(p.open_buy_value) for p in account.positions if p.symbol == entry.symbol), Fraction(0))
            if captured < needed:
                return False
    return True


def _market_valid(market, intent, policy, now):
    return (type(market) is MarketSnapshot and all(valid_id(v) for v in (market.version, market.calendar_source_id, market.calendar_version))
            and type(market.execution_target) is str and market.execution_target == "dry_run"
            and type(market.mode) is str and market.mode == "mock"
            and type(market.symbol) is str and market.symbol == intent.symbol
            and type(market.market) is str and market.market == intent.market
            and type(market.currency) is str and market.currency == "KRW"
            and market.complete is True and market.tradable is True
            and valid_id(market.session) and market.session in policy.allowed_sessions
            and intent.symbol in policy.allowed_symbols and intent.market in policy.allowed_markets
            and _fresh(market.captured_at, now, policy.max_market_age)
            and all(_money(v, positive=True) for v in (market.tick_size, market.min_price, market.max_price))
            and market.min_price <= market.max_price)


def decision(reasons, fingerprint=None, policy=None, account=None, market=None, cash=ZERO, qty=0, exposure=ZERO):
    reasons = tuple(code for code in ReasonCode if code in reasons)
    return RiskDecision(not reasons, reasons, policy, account, market, fingerprint,
                        ZERO if reasons else cash, 0 if reasons else qty, ZERO if reasons else exposure)


def validate_order(intent, binding, policy, account, market, book, *, now) -> RiskDecision:
    """Validate only explicit evidence; malformed objects never escape in errors."""
    fingerprint = order_fingerprint(intent)
    try:
        result = _validate(intent, binding, policy, account, market, book, now, fingerprint)
        return replace(result, book_revision=book.revision) if result.account_version is not None else result
    except Exception:
        return decision((ReasonCode.INVALID_ORDER,), fingerprint)


def _validate(intent, binding, policy, account, market, book, now, fingerprint):
    reasons = []
    if type(intent) is not OrderIntent:
        return decision((ReasonCode.INVALID_ORDER,))
    if type(intent.mode) is not str or intent.mode != "mock" or type(intent.execution_target) is not str or intent.execution_target != "dry_run":
        reasons.append(ReasonCode.MODE_NOT_ALLOWED)
    if (type(intent.schema_version) is not int or intent.schema_version != 1 or fingerprint is None
            or not all(valid_id(v) for v in (intent.client_order_id, intent.account_alias, intent.account_binding_id,
                                           intent.binding_version, intent.symbol, intent.source_id))
            or type(intent.side) not in (Side, str) or intent.side not in (Side.BUY, Side.SELL)
            or not _integer(intent.qty, positive=True) or not _money(intent.limit_price, positive=True)
            or type(intent.currency) is not str or intent.currency != "KRW"
            or type(intent.market) is not str or intent.market != "domestic_stock"
            or type(intent.order_type) is not str or intent.order_type != "LIMIT"
            or not aware(intent.created_at) or not aware(intent.expires_at) or not _binding_valid(binding)
            or (intent.account_alias, intent.account_binding_id, intent.binding_version) != (binding.alias, binding.binding_id, binding.version)):
        reasons.append(ReasonCode.INVALID_ORDER)
    if reasons:
        return decision(reasons, fingerprint)
    if not _policy_valid(policy):
        return decision((ReasonCode.POLICY_REQUIRED,), fingerprint)
    if (not aware(now) or not intent.created_at <= now < intent.expires_at
            or now-intent.created_at > policy.max_request_age
            or intent.expires_at-intent.created_at > policy.max_request_lifetime):
        return decision((ReasonCode.INVALID_ORDER,), fingerprint, policy.version)
    account_ok = _account_valid(account, binding, policy, book, now)
    market_ok = _market_valid(market, intent, policy, now)
    if not account_ok: reasons.append(ReasonCode.SNAPSHOT_INVALID)
    if not market_ok: reasons.append(ReasonCode.MARKET_UNAVAILABLE)
    if reasons:
        return decision(reasons, fingerprint, policy.version, account.version if account_ok else None, market.version if market_ok else None)
    if not market.min_price <= intent.limit_price <= market.max_price:
        return decision((ReasonCode.INVALID_ORDER,), fingerprint, policy.version, account.version, market.version)
    price = Fraction(intent.limit_price)
    if (price / Fraction(market.tick_size)).denominator != 1:
        return decision((ReasonCode.INVALID_ORDER,), fingerprint, policy.version, account.version, market.version)
    unseen = tuple(e for e in book.entries if e.account_binding_id == binding.binding_id and e.order_id not in account.included_reservation_ids)
    notional = price * intent.qty
    buying = intent.side == Side.BUY
    raw_fee = notional * Fraction(policy.buy_fee_rate if buying else policy.sell_fee_rate) + Fraction(policy.buy_fixed_fee if buying else policy.sell_fixed_fee)
    quantum = Fraction(policy.cost_quantum)
    fee = -(-raw_fee // quantum) * quantum
    cash = notional + fee if buying else fee
    exposure = notional if buying else Fraction(0)
    remaining_cash = Fraction(account.available_cash) - sum((Fraction(e.cash) for e in unseen), Fraction(0))
    position = next((p for p in account.positions if p.symbol == intent.symbol), None)
    available_qty = (position.sellable_qty if position else 0) - sum(e.qty for e in unseen if e.symbol == intent.symbol)
    symbol_exposure = Fraction(position.market_value) + Fraction(position.open_buy_value) if position else Fraction(0)
    symbol_exposure += sum((Fraction(e.exposure) for e in unseen if e.symbol == intent.symbol), Fraction(0))
    account_exposure = Fraction(account.account_exposure) + sum((Fraction(e.exposure) for e in unseen), Fraction(0))
    if remaining_cash < cash: reasons.append(ReasonCode.INSUFFICIENT_CASH)
    if not buying and available_qty < intent.qty: reasons.append(ReasonCode.INSUFFICIENT_POSITION)
    if (notional > Fraction(policy.max_order_notional) or fee > Fraction(policy.max_fee)
            or symbol_exposure+exposure > Fraction(policy.max_symbol_exposure)
            or account_exposure+exposure > Fraction(policy.max_account_exposure)
            or account.open_order_count+len(unseen)+1 > policy.max_open_orders):
        reasons.append(ReasonCode.LIMIT_EXCEEDED)
    if reasons:
        return decision(reasons, fingerprint, policy.version, account.version, market.version)
    return decision((), fingerprint, policy.version, account.version, market.version,
                    _decimal(cash), 0 if buying else intent.qty, _decimal(exposure))
