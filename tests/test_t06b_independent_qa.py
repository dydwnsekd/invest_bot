"""Independent synthetic expectations for T06b's normal public API."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import FrozenInstanceError, replace
from datetime import timedelta, timezone
from decimal import Decimal, Inexact, ROUND_DOWN, ROUND_UP, Rounded, localcontext
import inspect
import json
from pathlib import Path
import subprocess
import sys
import textwrap

import pytest

from invest_bot.risk.order_validation import validate_order
from invest_bot.trading.dry_run import DryRunBroker
from invest_bot.trading.models import OrderState, Position, ReasonCode, Side, VirtualOutcome


def sample():
    # Independent virtual data, not operating limits or an owner test fixture.
    from datetime import UTC, datetime, timedelta
    from decimal import Decimal
    from types import SimpleNamespace
    from invest_bot.trading.models import (
        AccountBinding, AccountSnapshot, MarketSnapshot, OrderIntent, Position,
        ReservationBook, RiskPolicy, Side,
    )
    d = Decimal
    now = datetime(2026, 11, 18, 5, tzinfo=UTC)
    binding = AccountBinding("qa-paper", "qa-binding", "binding-3", "mock", "dry_run")
    intent = OrderIntent(1, "qa-order", "dry_run", "mock", binding.alias, binding.binding_id, binding.version,
                         "111111", Side.BUY, 3, d("7.25"), "KRW", "domestic_stock", "LIMIT", "qa-source",
                         now-timedelta(seconds=5), now+timedelta(seconds=5))
    policy = RiskPolicy("qa-policy", "dry_run", "mock", frozenset({"111111", "222222"}),
                        frozenset({"domestic_stock"}), frozenset({"qa-open"}),
                        d("50"), d("100"), d("150"), d("2"), 4,
                        d("0.01"), d("0.02"), d("0.11"), d("0.03"), d("0.25"),
                        timedelta(seconds=5), timedelta(seconds=10), timedelta(seconds=3),
                        timedelta(seconds=2), timedelta(seconds=4))
    positions = (Position("111111", 8, d("58"), d("0")), Position("222222", 2, d("20"), d("0")))
    account = AccountSnapshot("qa-capture", "dry_run", "mock", binding.alias, binding.binding_id, binding.version,
                              "KRW", now-timedelta(seconds=3), True, True, d("100"), positions, d("78"), 0,
                              now-timedelta(seconds=4), "qa-valuation", "qa-book", 0, frozenset())
    market = MarketSnapshot("qa-market", "dry_run", "mock", "111111", "domestic_stock", "KRW",
                            now-timedelta(seconds=2), True, True, "qa-open", "qa-calendar", "calendar-7",
                            d("0.25"), d("1"), d("50"))
    return SimpleNamespace(now=now, binding=binding, intent=intent, policy=policy, account=account,
                           market=market, book=ReservationBook("qa-book", 0, ()))


def validate(c, **changes):
    args = dict(intent=c.intent, binding=c.binding, policy=c.policy, account=c.account,
                market=c.market, book=c.book, now=c.now)
    args.update(changes)
    return validate_order(**args)


def execute(broker, c, **changes):
    args = dict(intent=c.intent, policy=c.policy, account=c.account, market=c.market, now=c.now)
    args.update(changes)
    return broker.execute(**args)


def owner(c, outcomes=(VirtualOutcome.ACKNOWLEDGED,)):
    return DryRunBroker(bindings=(c.binding,), book_id=c.book.book_id, outcomes=outcomes)


@pytest.mark.parametrize("precision,rounding", [(2, ROUND_UP), (40, ROUND_DOWN)])
def test_money_is_exact_with_quarter_unit_fee_under_ambient_context(precision, rounding):
    c = sample()
    before = deepcopy(vars(c))
    with localcontext() as context:
        context.prec, context.rounding = precision, rounding
        context.traps[Inexact] = context.traps[Rounded] = True
        decision = validate(c)
    # 3*7.25=21.75; raw fee=.2175+.11=.3275; ceil to .25 gives .50.
    assert decision.allowed and decision.reasons == ()
    assert (decision.reserve_cash, decision.reserve_exposure, decision.reserve_qty) == (Decimal("22.25"), Decimal("21.75"), 0)
    assert vars(c) == before


def test_all_financial_caps_and_cash_allow_exact_equality():
    c = sample()
    result = validate(c, account=replace(c.account, available_cash=Decimal("22.25")),
                      policy=replace(c.policy, max_order_notional=Decimal("21.75"), max_fee=Decimal(".50"),
                                     max_symbol_exposure=Decimal("79.75"), max_account_exposure=Decimal("99.75"), max_open_orders=1))
    assert result.allowed and result.reserve_cash == Decimal("22.25")


@pytest.mark.parametrize("field,value,expected", [
    ("available_cash", "22.24", ReasonCode.INSUFFICIENT_CASH),
    ("max_order_notional", "21.74", ReasonCode.LIMIT_EXCEEDED),
    ("max_symbol_exposure", "79.74", ReasonCode.LIMIT_EXCEEDED),
    ("max_account_exposure", "99.74", ReasonCode.LIMIT_EXCEEDED),
    ("max_fee", ".49", ReasonCode.LIMIT_EXCEEDED),
    ("max_open_orders", 0, ReasonCode.LIMIT_EXCEEDED),
])
def test_normal_size_financial_overrun_rejects_without_reservation(field, value, expected):
    c = sample()
    args = {"account": replace(c.account, **{field: Decimal(value)})} if field == "available_cash" else {
        "policy": replace(c.policy, **{field: value if field == "max_open_orders" else Decimal(value)})}
    result = validate(c, **args)
    assert result.reasons == (expected,) and not result.allowed
    assert (result.reserve_cash, result.reserve_qty, result.reserve_exposure) == (0, 0, 0)


@pytest.mark.parametrize("field,value", [
    ("qty", True), ("qty", 0), ("qty", 3.0), ("qty", Decimal("3")),
    ("limit_price", 7.25), ("limit_price", Decimal("NaN")),
    ("limit_price", Decimal("sNaN")), ("limit_price", Decimal("Infinity")),
])
def test_malformed_numeric_types_fail_closed(field, value):
    c = sample()
    b = owner(c)
    record = execute(b, c, intent=replace(c.intent, **{field: value}))
    assert record.state is OrderState.REJECTED
    assert record.decision.reasons == (ReasonCode.INVALID_ORDER,)
    assert b.execution_count == 0 and b.reservations == ()


@pytest.mark.parametrize("kind,expected", [
    ("mode", ReasonCode.MODE_NOT_ALLOWED), ("target", ReasonCode.MODE_NOT_ALLOWED),
    ("binding", ReasonCode.INVALID_ORDER), ("incomplete", ReasonCode.SNAPSHOT_INVALID),
    ("market-target", ReasonCode.MARKET_UNAVAILABLE), ("policy-target", ReasonCode.POLICY_REQUIRED),
])
def test_scope_and_evidence_mismatch_cannot_execute(kind, expected):
    c = sample()
    args = {
        "mode": {"intent": replace(c.intent, mode="live")},
        "target": {"intent": replace(c.intent, execution_target="kis_mock")},
        "binding": {"intent": replace(c.intent, binding_version="binding-4")},
        "incomplete": {"account": replace(c.account, complete=False)},
        "market-target": {"market": replace(c.market, execution_target="kis_mock")},
        "policy-target": {"policy": replace(c.policy, execution_target="kis_mock")},
    }[kind]
    b = owner(c)
    record = execute(b, c, **args)
    assert record.decision.reasons == (expected,)
    assert b.execution_count == 0 and not b.reservations


@pytest.mark.parametrize("kind,expected", [
    ("request", ReasonCode.INVALID_ORDER), ("snapshot", ReasonCode.SNAPSHOT_INVALID),
    ("market", ReasonCode.MARKET_UNAVAILABLE), ("valuation", ReasonCode.SNAPSHOT_INVALID),
])
def test_age_equality_is_inclusive_but_one_microsecond_beyond_rejects(kind, expected):
    c = sample()
    assert validate(c).allowed
    older = timedelta(microseconds=1)
    args = {
        "request": {"policy": replace(c.policy, max_request_age=timedelta(seconds=5)-older)},
        "snapshot": {"account": replace(c.account, captured_at=c.account.captured_at-older)},
        "market": {"market": replace(c.market, captured_at=c.market.captured_at-older)},
        "valuation": {"account": replace(c.account, valuation_at=c.account.valuation_at-older)},
    }[kind]
    assert validate(c, **args).reasons == (expected,)


def test_request_expiration_is_exclusive_and_financial_reasons_are_stable():
    c = sample()
    assert validate(c, intent=replace(c.intent, expires_at=c.now)).reasons == (ReasonCode.INVALID_ORDER,)
    decision = validate(c, intent=replace(c.intent, side=Side.SELL, qty=99),
                        account=replace(c.account, available_cash=Decimal("0")))
    assert decision.reasons == (ReasonCode.INSUFFICIENT_CASH, ReasonCode.INSUFFICIENT_POSITION, ReasonCode.LIMIT_EXCEEDED)


@pytest.mark.parametrize("accepted", [True, False], ids=["acceptance", "original-denial"])
def test_replay_is_original_even_after_context_time_and_received_metadata_change(accepted):
    c = sample()
    if not accepted:
        c.account = replace(c.account, available_cash=Decimal("22.24"))
    b = owner(c)
    original = execute(b, c)
    offset = timezone(timedelta(hours=9))
    equivalent = replace(c.intent, limit_price=Decimal("7.2500"), created_at=c.intent.created_at.astimezone(offset),
                         expires_at=c.intent.expires_at.astimezone(offset))
    again = execute(b, c, intent=equivalent, policy=None, account=None, market=None, now=None, received_at=object())
    assert again is original
    assert original.evaluated_at == c.now and original.client_order_id == "qa-order"
    assert (original.account_binding_id, original.binding_version) == (c.binding.binding_id, c.binding.version)
    assert b.execution_count == int(accepted) and len(b.reservations) == int(accepted)


@pytest.mark.parametrize("field", ["qty", "source_id", "account_alias", "binding_version", "created_at", "expires_at"])
def test_conflict_never_replaces_the_original_or_consumes_another_outcome(field):
    c = sample()
    b = owner(c)
    first = execute(b, c)
    changed = {"qty": 4, "source_id": "qa-source-other", "account_alias": "qa-rebound", "binding_version": "binding-4",
               "created_at": c.intent.created_at-timedelta(seconds=1),
               "expires_at": c.intent.expires_at+timedelta(seconds=1)}[field]
    conflict = execute(b, c, intent=replace(c.intent, **{field: changed}))
    assert conflict.decision.reasons == (ReasonCode.IDEMPOTENCY_CONFLICT,)
    assert b.records == (first,) and b.execution_count == 1
    assert execute(b, c) is first and len(b.reservations) == 1


@pytest.mark.parametrize("complete,expected", [(True, ReasonCode.INSUFFICIENT_CASH), (False, ReasonCode.SNAPSHOT_INVALID)])
def test_complete_zero_cash_empty_holdings_are_distinct_from_missing_capture(complete, expected):
    c = sample()
    empty = replace(c.account, available_cash=Decimal("0"), positions=(), account_exposure=Decimal("0"), complete=complete)
    result = validate(c, account=empty)
    assert result.reasons == (expected,) and not result.allowed
    assert result.reserve_cash == 0 and result.reserve_qty == 0


def test_zero_cash_can_sell_existing_stock_under_explicit_zero_fee_policy():
    c = sample()
    b = owner(c)
    record = execute(b, c, intent=replace(c.intent, side=Side.SELL),
                     account=replace(c.account, available_cash=Decimal("0")),
                     policy=replace(c.policy, sell_fee_rate=Decimal("0"), sell_fixed_fee=Decimal("0")))
    assert record.state is OrderState.ACKNOWLEDGED
    assert (record.reserved_cash, record.reserved_qty) == (0, 3)
    assert b.reservations[0].cash == 0 and b.reservations[0].qty == 3


def test_new_policy_epoch_is_checked_for_new_id_while_denied_original_stays_cached():
    c = sample()
    b = owner(c)
    denial = execute(b, c, policy=replace(c.policy, max_fee=Decimal("0")))
    assert denial.decision.reasons == (ReasonCode.LIMIT_EXCEEDED,)
    next_policy = replace(c.policy, version="qa-policy-2")
    assert execute(b, c, policy=next_policy) is denial
    accepted = execute(b, c, policy=next_policy, intent=replace(c.intent, client_order_id="qa-next-epoch"))
    assert accepted.state is OrderState.ACKNOWLEDGED and accepted.decision.policy_version == "qa-policy-2"
    assert denial.decision.policy_version == "qa-policy" and b.execution_count == 1


def test_unreflected_and_already_included_buy_reservations_subtract_exactly_once():
    c = sample()
    c.account = replace(c.account, available_cash=Decimal("44.50"))
    c.policy = replace(c.policy, max_symbol_exposure=Decimal("200"), max_account_exposure=Decimal("200"), max_open_orders=10)
    b = owner(c, (VirtualOutcome.ACKNOWLEDGED,)*3)
    first = execute(b, c)
    assert first.reserved_cash == Decimal("22.25")
    included = replace(c.account, version="qa-capture-2", captured_at=c.now, available_cash=Decimal("22.25"),
                       positions=(replace(c.account.positions[0], open_buy_value=Decimal("21.75")), c.account.positions[1]),
                       account_exposure=Decimal("99.75"), open_order_count=1, reservation_watermark=1,
                       included_reservation_ids=frozenset({first.order_id}))
    second = execute(b, c, intent=replace(c.intent, client_order_id="qa-second"), account=included)
    assert second.state is OrderState.ACKNOWLEDGED
    third = execute(b, c, intent=replace(c.intent, client_order_id="qa-third"), account=included)
    assert third.decision.reasons == (ReasonCode.INSUFFICIENT_CASH,)
    assert b.execution_count == 2 and sum(r.cash for r in b.reservations) == Decimal("44.50")


def test_sell_coverage_keeps_fee_cash_and_net_sellable_quantity_separate():
    c = sample()
    c.intent = replace(c.intent, side=Side.SELL)
    c.account = replace(c.account, available_cash=Decimal("1"))
    b = owner(c, (VirtualOutcome.ACKNOWLEDGED,)*3)
    first = execute(b, c)
    assert (first.reserved_cash, first.reserved_qty) == (Decimal(".50"), 3)
    included = replace(c.account, version="qa-sell-capture-2", captured_at=c.now, available_cash=Decimal(".50"),
                       positions=(replace(c.account.positions[0], sellable_qty=5), c.account.positions[1]),
                       open_order_count=1, reservation_watermark=1, included_reservation_ids=frozenset({first.order_id}))
    second = execute(b, c, intent=replace(c.intent, client_order_id="qa-second"), account=included)
    assert second.state is OrderState.ACKNOWLEDGED
    third = execute(b, c, intent=replace(c.intent, client_order_id="qa-third"), account=included)
    assert third.decision.reasons == (ReasonCode.INSUFFICIENT_CASH, ReasonCode.INSUFFICIENT_POSITION)
    assert sum(r.qty for r in b.reservations) == 6 and sum(r.cash for r in b.reservations) == Decimal("1")
    assert c.account.available_cash == Decimal("1")  # No sale proceeds or fills.


@pytest.mark.parametrize("problem", ["same-version-content", "incomplete-coverage", "future-watermark", "foreign-book", "unknown-included-id"])
def test_changed_or_unproven_capture_never_drops_a_hold(problem):
    c = sample()
    b = owner(c, (VirtualOutcome.ACKNOWLEDGED,)*2)
    execute(b, c)
    holds = b.reservations
    changes = {
        "same-version-content": {"available_cash": Decimal("101")},
        "incomplete-coverage": {"reservations_complete": False},
        "future-watermark": {"reservation_watermark": 2},
        "foreign-book": {"book_id": "qa-other-book"},
        "unknown-included-id": {"included_reservation_ids": frozenset({"qa-not-an-order"})},
    }[problem]
    rejected = execute(b, c, intent=replace(c.intent, client_order_id="qa-new"), account=replace(c.account, **changes))
    assert rejected.decision.reasons == (ReasonCode.SNAPSHOT_INVALID,)
    assert b.reservations == holds and b.execution_count == 1


def test_rejection_releases_only_its_hold_and_caller_script_mutation_does_not_change_it():
    c = sample()
    c.policy = replace(c.policy, max_symbol_exposure=Decimal("200"))
    script = [VirtualOutcome.ACKNOWLEDGED, VirtualOutcome.BROKER_REJECTED]
    b = owner(c, script)
    script[:] = [VirtualOutcome.UNKNOWN]
    first = execute(b, c)
    second = execute(b, c, intent=replace(c.intent, client_order_id="qa-second"))
    assert first.state is OrderState.ACKNOWLEDGED and second.state is OrderState.BROKER_REJECTED
    assert second.decision.allowed and (second.reserved_cash, second.reserved_qty) == (0, 0)
    assert len(b.reservations) == 1 and b.reservations[0].order_id == first.order_id
    assert b.execution_count == 2 and not b.blocked_accounts


@pytest.mark.parametrize("script", [(VirtualOutcome.UNKNOWN,), ()], ids=["explicit-unknown", "script-exhausted"])
def test_unknown_blocks_all_new_ids_for_binding_but_not_an_independent_account(script):
    c = sample()
    other_binding = replace(c.binding, alias="qa-paper-other", binding_id="qa-binding-other")
    b = DryRunBroker(bindings=(c.binding, other_binding), book_id="qa-book", outcomes=script)
    first = execute(b, c)
    assert first.state is OrderState.UNKNOWN and len(b.reservations) == 1
    denied = execute(b, c, intent=replace(c.intent, client_order_id="qa-new"), market=None)
    assert denied.decision.reasons == (ReasonCode.RECONCILIATION_REQUIRED,)
    spoof = execute(b, c, intent=replace(c.intent, client_order_id="qa-spoof", account_binding_id="qa-not-registered"))
    assert spoof.decision.reasons == (ReasonCode.INVALID_ORDER,)
    assert execute(b, c, now=None, policy=None, account=None, market=None) is first
    assert b.execution_count == 1 and b.blocked_accounts == frozenset({c.binding.binding_id})
    # A deliberately separate registered account may execute; empty script gives
    # it its own UNKNOWN, rather than treating the first account's block as global.
    different = execute(b, c, intent=replace(c.intent, client_order_id="qa-other", account_alias=other_binding.alias,
                                           account_binding_id=other_binding.binding_id),
                        account=replace(c.account, account_alias=other_binding.alias, account_binding_id=other_binding.binding_id))
    assert different.state is OrderState.UNKNOWN and b.execution_count == 2


def test_public_state_and_original_inputs_are_immutable():
    c = sample()
    b = owner(c)
    record = execute(b, c)
    for obj, field, value in ((record, "state", OrderState.UNKNOWN), (record.decision, "allowed", False),
                              (b.book, "revision", 99), (b.reservations[0], "cash", Decimal("0")),
                              (c.policy, "max_fee", Decimal("0")), (c.binding, "binding_id", "changed")):
        with pytest.raises(FrozenInstanceError):
            setattr(obj, field, value)
    assert isinstance(b.records, tuple) and isinstance(b.reservations, tuple) and isinstance(b.blocked_accounts, frozenset)
    with pytest.raises(AttributeError):
        b.execution_count = 99
    assert execute(b, c) is record and record.state is OrderState.ACKNOWLEDGED


@pytest.mark.parametrize("field", ["qty", "limit_price", "source_id"])
def test_bad_payloads_do_not_render_arbitrary_objects_or_echo_raw_values(field):
    class Secret:
        calls = 0
        def __repr__(self):
            self.calls += 1
            raise AssertionError("qa-secret-marker")
        def __str__(self):
            self.calls += 1
            raise AssertionError("qa-secret-marker")
    secret = Secret()
    c = sample()
    bad = replace(c.intent, **{field: secret})
    b = owner(c)
    record = execute(b, c, intent=bad)
    assert record.decision.reasons == (ReasonCode.INVALID_ORDER,)
    assert execute(b, c, intent=bad, policy=None, account=None, market=None, now=None) is record
    assert secret.calls == 0 and "qa-secret-marker" not in repr(record)
    assert b.execution_count == 0 and not b.reservations


def test_fresh_normal_public_import_validate_and_execute_without_runtime_effects(tmp_path):
    root = Path(__file__).resolve().parents[1]
    temporary = tmp_path / "child-temp"
    temporary.mkdir()
    guard = textwrap.dedent('''
        import dataclasses, datetime, decimal, enum, fractions, hashlib, importlib.abc, json, os, pathlib, re, sys
        forbidden = []
        def deny(label):
            forbidden.append(label)
            raise AssertionError(label)
        class Boundary(importlib.abc.MetaPathFinder):
            def find_spec(self, fullname, path=None, target=None):
                roots = ("requests", "sqlalchemy", "invest_bot.clients", "invest_bot.db", "invest_bot.jobs", "invest_bot.backtest", "invest_bot.dashboard")
                if any(fullname == item or fullname.startswith(item + ".") for item in roots):
                    deny("forbidden-import:" + fullname)
        sys.meta_path.insert(0, Boundary())
        def profile(frame, event, arg):
            if event == "call":
                name = frame.f_code.co_name
                if frame.f_code.co_filename.endswith("/config/settings.py") and name not in ("<module>", "TradingMode", "AppSettings"):
                    deny("settings-call:" + name)
                instance = frame.f_locals.get("self")
                if name == "__init__" and type(instance).__name__ == "AppSettings" and type(instance).__module__ == "invest_bot.config.settings":
                    deny("settings-construction")
        sys.setprofile(profile)
        def audit(event, args):
            if event in ("socket.connect", "socket.bind", "subprocess.Popen", "os.system"):
                deny(event)
            if event == "open":
                path, mode, flags = args
                if type(path) is not str or any(token in (mode or "") for token in ("w", "a", "x", "+")) or flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC):
                    deny("file-write-or-unknown")
                if pathlib.Path(path).suffix not in (".py", ".pyc", ".so", ".zip"):
                    deny("non-source-file-read")
        sys.addaudithook(audit)
        from invest_bot.trading.dry_run import DryRunBroker
        from invest_bot.risk.order_validation import validate_order
        from invest_bot.trading.models import VirtualOutcome, OrderState
    ''')
    scenario = textwrap.dedent('''
        c = sample()
        decision = validate_order(c.intent, c.binding, c.policy, c.account, c.market, c.book, now=c.now)
        assert decision.allowed and decision.reserve_cash == decimal.Decimal("22.25")
        broker = DryRunBroker(bindings=(c.binding,), book_id="qa-book", outcomes=(VirtualOutcome.ACKNOWLEDGED,))
        record = broker.execute(c.intent, policy=c.policy, account=c.account, market=c.market, now=c.now)
        assert record.state is OrderState.ACKNOWLEDGED and broker.execution_count == 1
        assert broker.execute(c.intent, policy=None, account=None, market=None, now=None) is record
        assert not forbidden
        sys.setprofile(None)
        print(json.dumps({"public_import": True, "state": record.state.value, "cash": str(record.reserved_cash), "replay_original": True, "forbidden_operations": forbidden}))
    ''')
    source = "import sys\nsys.path.insert(0, " + repr(str(root / "src")) + ")\n" + guard + "\n" + inspect.getsource(sample) + "\n" + scenario
    result = subprocess.run([sys.executable, "-B", "-c", source], cwd=root,
                            env={"PATH": "/usr/bin:/bin:/usr/sbin:/sbin", "PYTHONDONTWRITEBYTECODE": "1", "TMPDIR": str(temporary)},
                            text=True, capture_output=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr
    observed = json.loads(result.stdout)
    assert observed == {"public_import": True, "state": "ACKNOWLEDGED", "cash": "22.25", "replay_original": True, "forbidden_operations": []}
    (tmp_path / "public-import-observation.json").write_text(json.dumps(observed, indent=2))
