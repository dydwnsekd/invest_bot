from dataclasses import FrozenInstanceError, replace
from datetime import timedelta, timezone, tzinfo
from decimal import localcontext

import pytest

from t06b_order_fixture import D, NOW, case, validate


@pytest.mark.parametrize(("field", "value", "code"), [
    ("mode", "live", "MODE_NOT_ALLOWED"), ("execution_target", "kis_mock", "MODE_NOT_ALLOWED"),
    ("mode", "unknown", "MODE_NOT_ALLOWED"), ("qty", 0, "INVALID_ORDER"),
    ("qty", -1, "INVALID_ORDER"), ("qty", True, "INVALID_ORDER"), ("qty", 1.5, "INVALID_ORDER"),
    ("limit_price", 100.0, "INVALID_ORDER"), ("limit_price", D("NaN"), "INVALID_ORDER"),
    ("limit_price", D("Infinity"), "INVALID_ORDER"), ("limit_price", D("-1"), "INVALID_ORDER"),
    ("symbol", "", "INVALID_ORDER"), ("side", "HOLD", "INVALID_ORDER"),
    ("currency", "USD", "INVALID_ORDER"), ("order_type", "MARKET", "INVALID_ORDER"),
    ("account_binding_id", "other", "INVALID_ORDER"),
])
def test_invalid_intents_are_rejected_without_adjustment(field, value, code):
    c = case()
    intent = replace(c.intent, **{field: value})
    result = validate(c, intent=intent)
    assert not result.allowed
    assert code in [item.value for item in result.reasons]
    assert result.reserve_cash == 0 and result.reserve_qty == 0


def test_exact_cost_cash_and_exposure_boundaries_and_determinism():
    c = case()
    result = validate(c)
    assert result.allowed and result.reserve_cash == D("202") and result.reserve_exposure == D("200")
    assert validate(c) == result
    exact = replace(c.account, available_cash=D("202"))
    assert validate(c, account=exact).allowed
    assert not validate(c, account=replace(exact, available_cash=D("201.99"))).allowed
    assert validate(c, policy=replace(c.policy, max_order_notional=D("200"), max_symbol_exposure=D("200"), max_account_exposure=D("200"))).allowed
    for field in ("max_order_notional", "max_symbol_exposure", "max_account_exposure"):
        assert c.d.m.ReasonCode.LIMIT_EXCEEDED in validate(c, policy=replace(c.policy, **{field: D("199.99")})).reasons
    rounded = replace(c.policy, buy_fee_rate=D("0.013"), cost_quantum=D("5"))
    assert validate(c, policy=rounded).reserve_cash == D("205")  # ceiling to a multiple, not just decimal places
    assert c.intent.limit_price == D("100") and c.account.available_cash == D("1000")
    with pytest.raises(FrozenInstanceError):
        result.allowed = False


@pytest.mark.parametrize("field,value", [
    ("max_fee", D("NaN")), ("cost_quantum", D("0")), ("buy_fee_rate", D("-1")),
    ("max_open_orders", True), ("max_account_exposure", None), ("max_snapshot_age", timedelta(seconds=-1)),
    ("allowed_sessions", frozenset()),
])
def test_bad_or_missing_policy_never_uses_defaults(field, value):
    c = case()
    assert c.d.m.ReasonCode.POLICY_REQUIRED in validate(c, policy=None).reasons
    decision = validate(c, policy=replace(c.policy, **{field: value}))
    assert not decision.allowed and c.d.m.ReasonCode.POLICY_REQUIRED in decision.reasons


@pytest.mark.parametrize("kind", ["account", "market", "valuation", "intent"])
def test_freshness_equal_is_valid_but_exceeding_is_not(kind):
    c = case()
    if kind == "intent":
        at = replace(c.intent, created_at=NOW-c.policy.max_request_age)
        assert validate(c, intent=at).allowed
        assert not validate(c, intent=replace(at, created_at=at.created_at-timedelta(microseconds=1))).allowed
    else:
        field = "valuation_at" if kind == "valuation" else "captured_at"
        maximum = getattr(c.policy, "max_valuation_age" if kind == "valuation" else f"max_{'snapshot' if kind == 'account' else 'market'}_age")
        obj = c.market if kind == "market" else c.account
        at = replace(obj, **{field: NOW-maximum})
        args = {"market" if kind == "market" else "account": at}
        assert validate(c, **args).allowed
        args[next(iter(args))] = replace(at, **{field: NOW-maximum-timedelta(microseconds=1)})
        assert not validate(c, **args).allowed


@pytest.mark.parametrize("problem", ["naive", "future", "expired", "account", "incomplete", "cash-missing", "valuation", "market", "calendar", "unknown-session", "halt", "tick", "price-range"])
def test_bad_time_or_capture_or_market_is_fail_closed(problem):
    c = case()
    args = {}
    if problem == "naive": args["now"] = NOW.replace(tzinfo=None)
    elif problem == "future": args["account"] = replace(c.account, captured_at=NOW+timedelta(microseconds=1))
    elif problem == "expired": args["now"] = c.intent.expires_at
    elif problem == "account": args["account"] = replace(c.account, account_binding_id="other")
    elif problem == "incomplete": args["account"] = replace(c.account, complete=False)
    elif problem == "cash-missing": args["account"] = replace(c.account, available_cash=None)
    elif problem == "valuation": args["account"] = replace(c.account, valuation_source_id="")
    elif problem == "market": args["market"] = replace(c.market, symbol="000660")
    elif problem == "calendar": args["market"] = replace(c.market, calendar_version="")
    elif problem == "unknown-session": args["market"] = replace(c.market, session=None)
    elif problem == "halt": args["market"] = replace(c.market, tradable=False)
    elif problem == "tick": args["intent"] = replace(c.intent, limit_price=D("100.5"))
    else: args["intent"] = replace(c.intent, limit_price=D("1001"))
    assert not validate(c, **args).allowed


def test_sell_uses_sellable_quantity_and_never_credits_proceeds():
    c = case()
    position = c.d.m.Position("005930", 2, D("200"), D("0"))
    account = replace(c.account, positions=(position,), account_exposure=D("200"), available_cash=D("4"))
    sell = replace(c.intent, side=c.d.m.Side.SELL)
    result = validate(c, intent=sell, account=account)
    assert result.allowed and result.reserve_qty == 2 and result.reserve_cash == D("4") and result.reserve_exposure == 0
    assert not validate(c, intent=replace(sell, qty=3), account=account).allowed
    zero_fees = replace(c.policy, sell_fee_rate=D("0"), sell_fixed_fee=D("0"))
    assert validate(c, intent=sell, account=replace(account, available_cash=D("0")), policy=zero_fees).allowed
    assert not validate(c, intent=sell, account=c.account).allowed  # complete empty holdings != unknown
    missing = replace(c.account, positions=None)
    assert c.d.m.ReasonCode.SNAPSHOT_INVALID in validate(c, intent=sell, account=missing).reasons


def test_multiple_reason_order_and_open_order_and_fee_caps():
    c = case()
    decision = validate(c, account=replace(c.account, available_cash=D("0")), policy=replace(c.policy, max_order_notional=D("1"), max_open_orders=0))
    assert decision.reasons == (c.d.m.ReasonCode.INSUFFICIENT_CASH, c.d.m.ReasonCode.LIMIT_EXCEEDED)
    assert not validate(c, policy=replace(c.policy, max_fee=D("1"))).allowed


def test_decimal_context_and_equivalent_times_do_not_change_exact_results():
    c = case()
    intent = replace(c.intent, limit_price=D("123.456"), qty=3)
    market = replace(c.market, tick_size=D("0.001"))
    expected = validate(c, intent=intent, market=market)
    with localcontext() as ctx:
        ctx.prec = 2
        assert validate(c, intent=intent, market=market) == expected
    assert expected.allowed and expected.reserve_cash == D("374.368")
    shifted = replace(c.intent, created_at=c.intent.created_at.astimezone(timezone(timedelta(hours=9))))
    assert c.d.m.order_fingerprint(shifted) == c.d.m.order_fingerprint(c.intent)


def test_untrusted_timezone_and_snapshot_objects_do_not_execute_custom_methods():
    calls = []
    class CustomZone(tzinfo):
        def utcoffset(self, dt): calls.append("tz callback"); raise AssertionError("PRIVATE")
    class Private:
        def __eq__(self, other): calls.append("eq callback"); raise AssertionError("PRIVATE")
        def __str__(self): calls.append("str callback"); raise AssertionError("PRIVATE")
        def __repr__(self): calls.append("repr callback"); raise AssertionError("PRIVATE")
    c = case()
    assert not validate(c, intent=replace(c.intent, created_at=NOW.replace(tzinfo=CustomZone()))).allowed
    assert not validate(c, account=replace(c.account, mode=Private())).allowed
    assert calls == []


@pytest.mark.parametrize("field,value", [
    ("reservations_complete", False), ("reservation_watermark", 1),
    ("included_reservation_ids", frozenset({"unproven"})), ("book_id", "foreign-book"),
    ("account_exposure", D("1")), ("open_order_count", True),
    ("available_cash", D("Infinity")), ("positions", []),
])
def test_reservation_capture_evidence_must_be_complete_and_consistent(field, value):
    c = case()
    result = validate(c, account=replace(c.account, **{field: value}))
    assert not result.allowed and c.d.m.ReasonCode.SNAPSHOT_INVALID in result.reasons


def test_price_range_fee_cap_and_pending_count_are_inclusive():
    c = case()
    assert validate(c, intent=replace(c.intent, qty=1, limit_price=D("1"))).allowed
    high = replace(c.intent, qty=1, limit_price=D("1000"))
    assert validate(c, intent=high, account=replace(c.account, available_cash=D("1010"))).allowed
    assert validate(c, policy=replace(c.policy, max_open_orders=1, max_fee=D("2"))).allowed
    assert not validate(c, policy=replace(c.policy, max_open_orders=0)).allowed
    assert not validate(c, policy=replace(c.policy, max_fee=D("1.99"))).allowed


def test_extreme_price_is_rejected_by_explicit_range_before_ratio_expansion():
    c = case()
    assert not validate(c, intent=replace(c.intent, limit_price=D("1E+1000000000"))).allowed


@pytest.mark.parametrize("field,value", [
    ("schema_version", True), ("client_order_id", ""), ("source_id", ""),
    ("account_alias", "unknown"), ("binding_version", "changed"),
])
def test_identity_and_source_are_not_inferred(field, value):
    c = case()
    assert not validate(c, intent=replace(c.intent, **{field: value})).allowed
