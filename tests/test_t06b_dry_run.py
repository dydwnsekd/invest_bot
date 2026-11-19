from dataclasses import FrozenInstanceError, replace
from datetime import timedelta
import builtins
from pathlib import Path
import socket
import os
import subprocess
import sys

import pytest

from t06b_order_fixture import D, NOW, broker, case, domain, execute


def test_replay_uses_original_result_without_new_policy_clock_capture_or_reservation():
    c = case(); b = broker(c)
    first = execute(b, c)
    replay = execute(b, c, intent=replace(c.intent, limit_price=D("100.00")), policy=None, account=None, market=None,
                     now=None, received_at=NOW+timedelta(days=2))
    assert replay is first
    assert first.state is c.d.m.OrderState.ACKNOWLEDGED and first.execution_target == "dry_run"
    assert (first.client_order_id, first.account_binding_id, first.binding_version, first.evaluated_at) == (
        "order-1", "binding-a", "binding-v1", NOW,
    )
    assert (replay.client_order_id, replay.account_binding_id, replay.binding_version, replay.evaluated_at) == (
        "order-1", "binding-a", "binding-v1", NOW,
    )
    assert b.execution_count == 1 and len(b.reservations) == 1
    for changed in (replace(c.intent, qty=1), replace(c.intent, created_at=NOW), replace(c.intent, expires_at=NOW+timedelta(seconds=9))):
        conflict = execute(b, c, intent=changed)
        assert conflict.decision.reasons == (c.d.m.ReasonCode.IDEMPOTENCY_CONFLICT,)
    assert b.execution_count == 1


def test_rejected_ids_are_claimed_and_alias_reassignment_cannot_rejudge():
    c = case(); b = broker(c)
    rejected = execute(b, c, account=replace(c.account, available_cash=D("0")))
    assert rejected.state is c.d.m.OrderState.REJECTED
    assert execute(b, c) is rejected and b.execution_count == 0
    changed = replace(c.intent, account_binding_id="binding-new", binding_version="binding-v2")
    assert not execute(b, c, intent=changed, account=replace(c.account, account_binding_id="binding-new", binding_version="binding-v2")).decision.allowed
    assert b.execution_count == 0


def test_buy_reservations_subtract_once_and_inclusion_needs_exact_watermark_evidence():
    c = case(); b = broker(c, [c.d.m.VirtualOutcome.ACKNOWLEDGED] * 4)
    first = execute(b, c)
    assert first.reserved_cash == D("202")
    second_intent = replace(c.intent, client_order_id="order-2")
    low = replace(c.account, version="account-v2", available_cash=D("403"))
    assert not execute(b, c, intent=second_intent, account=low).decision.allowed
    included = replace(c.account, version="account-v3", included_reservation_ids=frozenset({first.order_id}),
                       reservation_watermark=b.book.revision, available_cash=D("202"), open_order_count=1,
                       positions=(c.d.m.Position("005930", 0, D("0"), D("200")),), account_exposure=D("200"))
    third = execute(b, c, intent=replace(c.intent, client_order_id="order-3"), account=included)
    assert third.state is c.d.m.OrderState.ACKNOWLEDGED
    assert b.execution_count == 2 and len(b.reservations) == 2
    unknown = replace(included, version="account-v4", included_reservation_ids=frozenset({"unproven"}))
    assert not execute(b, c, intent=replace(c.intent, client_order_id="order-4"), account=unknown).decision.allowed


def test_sell_reservations_prevent_oversell_and_do_not_increase_cash():
    c = case(); b = broker(c, [c.d.m.VirtualOutcome.ACKNOWLEDGED] * 2)
    account = replace(c.account, positions=(c.d.m.Position("005930", 3, D("300"), D("0")),), account_exposure=D("300"))
    sell = replace(c.intent, side=c.d.m.Side.SELL)
    assert execute(b, c, intent=sell, account=account).state is c.d.m.OrderState.ACKNOWLEDGED
    second = execute(b, c, intent=replace(sell, client_order_id="sell-2"), account=account)
    assert c.d.m.ReasonCode.INSUFFICIENT_POSITION in second.decision.reasons
    assert sum(r.cash for r in b.reservations) == D("4")


def test_already_reflected_sell_reservation_is_not_subtracted_again():
    c = case(); b = broker(c, [c.d.m.VirtualOutcome.ACKNOWLEDGED] * 2)
    account = replace(c.account, positions=(c.d.m.Position("005930", 5, D("500"), D("0")),), account_exposure=D("500"))
    sell = replace(c.intent, side=c.d.m.Side.SELL)
    first = execute(b, c, intent=sell, account=account)
    included = replace(account, version="account-v2", positions=(c.d.m.Position("005930", 3, D("500"), D("0")),),
                       available_cash=D("996"), open_order_count=1, reservation_watermark=1,
                       included_reservation_ids=frozenset({first.order_id}))
    second = execute(b, c, intent=replace(sell, qty=3, client_order_id="sell-2"), account=included)
    assert second.state is c.d.m.OrderState.ACKNOWLEDGED
    assert sum(r.qty for r in b.reservations) == 5


@pytest.mark.parametrize("field", ["source_id", "account_alias", "binding_version"])
def test_immutable_payload_changes_conflict_without_reexecution(field):
    c = case(); b = broker(c)
    execute(b, c)
    result = execute(b, c, intent=replace(c.intent, **{field: "changed"}))
    assert result.decision.reasons == (c.d.m.ReasonCode.IDEMPOTENCY_CONFLICT,)
    assert b.execution_count == 1 and len(b.records) == 1


@pytest.mark.parametrize("outcome", ["BROKER_REJECTED", "UNKNOWN"])
def test_clear_rejection_releases_but_unknown_keeps_and_blocks_account(outcome):
    c = case(); b = broker(c, [getattr(c.d.m.VirtualOutcome, outcome), c.d.m.VirtualOutcome.ACKNOWLEDGED])
    first = execute(b, c)
    assert first.state.value == outcome
    assert execute(b, c) is first and b.execution_count == 1
    second = execute(b, c, intent=replace(c.intent, client_order_id="new-id"))
    if outcome == "UNKNOWN":
        assert c.d.m.ReasonCode.RECONCILIATION_REQUIRED in second.decision.reasons
        assert b.execution_count == 1 and len(b.reservations) == 1
    else:
        assert second.state is c.d.m.OrderState.ACKNOWLEDGED and len(b.reservations) == 1


def test_capture_version_mutation_or_rollback_and_public_state_cannot_bypass_limits():
    c = case(); script = [c.d.m.VirtualOutcome.ACKNOWLEDGED] * 3; b = broker(c, script)
    script[:] = [c.d.m.VirtualOutcome.BROKER_REJECTED]
    first = execute(b, c)
    assert first.state is c.d.m.OrderState.ACKNOWLEDGED
    changed = replace(c.account, available_cash=D("999999"))  # same capture version, different content
    denied = execute(b, c, intent=replace(c.intent, client_order_id="order-2"), account=changed)
    assert c.d.m.ReasonCode.SNAPSHOT_INVALID in denied.decision.reasons
    with pytest.raises(FrozenInstanceError): b.reservations[0].cash = D("0")
    with pytest.raises((AttributeError, TypeError)): b.records.clear()
    with pytest.raises(AttributeError): b.execution_count = 0


def test_bad_payload_never_calls_repr_or_leaks_exception_and_stays_claimed():
    class Private:
        def __repr__(self): raise AssertionError("PRIVATE-MATERIAL")
        def __str__(self): raise AssertionError("PRIVATE-MATERIAL")
    c = case(); b = broker(c); value = Private()
    bad = replace(c.intent, limit_price=value)
    result = execute(b, c, intent=bad)
    assert result.state is c.d.m.OrderState.REJECTED
    assert result.client_order_id == "order-1" and result.account_binding_id == "binding-a"
    assert "PRIVATE-MATERIAL" not in repr(result)
    assert execute(b, c, intent=bad) is result
    assert execute(b, c).decision.reasons == (c.d.m.ReasonCode.IDEMPOTENCY_CONFLICT,)
    assert b.execution_count == 0


def test_invalid_clock_is_none_and_unresolved_binding_is_not_reported_as_resolved():
    c = case(); b = broker(c)
    rejected = execute(b, c, now=None)
    assert rejected.state is c.d.m.OrderState.REJECTED and rejected.evaluated_at is None
    assert rejected.client_order_id == "order-1" and rejected.account_binding_id == "binding-a"
    assert execute(b, c) is rejected
    unknown = execute(b, c, intent=replace(c.intent, client_order_id="order-2", account_binding_id="unresolved"))
    assert unknown.client_order_id == "order-2" and unknown.account_binding_id is None and unknown.binding_version is None
    mode_denied = execute(b, c, intent=replace(c.intent, mode="live", client_order_id="denied-mode"))
    assert mode_denied.client_order_id == "denied-mode" and mode_denied.state is c.d.m.OrderState.REJECTED


def test_new_intents_use_explicit_trusted_policy_but_existing_key_never_rejudges():
    c = case(); b = broker(c)
    denied = execute(b, c, policy=replace(c.policy, max_order_notional=D("1")))
    relaxed = replace(c.policy, version="policy-v2")
    assert execute(b, c, policy=relaxed) is denied
    new_intent = replace(c.intent, client_order_id="order-2")
    accepted = execute(b, c, intent=new_intent, policy=relaxed)
    assert accepted.state is c.d.m.OrderState.ACKNOWLEDGED
    assert accepted.decision.policy_version == "policy-v2" and b.execution_count == 1


def test_empty_script_is_unknown_not_fake_success():
    c = case(); b = broker(c, [])
    result = execute(b, c)
    assert result.state is c.d.m.OrderState.UNKNOWN and len(b.reservations) == 1


def test_capture_watermark_and_time_cannot_go_backwards_after_inclusion():
    c = case(); b = broker(c, [c.d.m.VirtualOutcome.ACKNOWLEDGED] * 3)
    first = execute(b, c)
    included = replace(c.account, version="included-v1", reservation_watermark=1,
                       included_reservation_ids=frozenset({first.order_id}), open_order_count=1,
                       available_cash=D("798"), account_exposure=D("200"),
                       positions=(c.d.m.Position("005930", 0, D("0"), D("200")),))
    assert execute(b, c, intent=replace(c.intent, client_order_id="order-2"), account=included).decision.allowed
    rollback = replace(c.account, version="rollback")
    assert c.d.m.ReasonCode.SNAPSHOT_INVALID in execute(b, c, intent=replace(c.intent, client_order_id="order-3"), account=rollback).decision.reasons
    assert b.execution_count == 2


def test_unknown_is_scoped_to_binding_not_other_virtual_account():
    c = case()
    other = replace(c.binding, alias="other", binding_id="binding-b")
    b = c.d.dry.DryRunBroker(bindings=(c.binding, other), book_id="book-a",
                            outcomes=(c.d.m.VirtualOutcome.UNKNOWN, c.d.m.VirtualOutcome.ACKNOWLEDGED))
    execute(b, c)
    intent = replace(c.intent, account_alias="other", account_binding_id="binding-b")
    account = replace(c.account, account_alias="other", account_binding_id="binding-b")
    assert execute(b, c, intent=intent, account=account).state is c.d.m.OrderState.ACKNOWLEDGED


def test_fresh_public_import_and_execution_do_not_load_settings_objects_or_external_clients():
    root = Path(__file__).resolve().parents[1]
    code = r'''
import builtins, os, pathlib, socket
import invest_bot
calls = []
def block(*a, **kw):
    calls.append("forbidden operation")
    raise AssertionError("forbidden operation")
invest_bot.AppSettings.from_file = block
invest_bot.AppSettings.__init__ = block
original = builtins.__import__
def guarded(name, *a, **kw):
    if name.startswith(("invest_bot.config", "invest_bot.clients", "invest_bot.backtest", "requests", "sqlalchemy", "sqlite3")):
        calls.append("forbidden direct import")
        raise AssertionError("forbidden direct import")
    return original(name, *a, **kw)
builtins.__import__ = guarded
builtins.open = block
pathlib.Path.open = block
os.open = block
socket.socket.connect = block
socket.create_connection = block
from invest_bot.trading.models import OrderIntent
from invest_bot.risk.order_validation import validate_order
from invest_bot.trading.dry_run import DryRunBroker
from t06b_order_fixture import case, broker, execute
c = case()
assert execute(broker(c), c).state.value == "ACKNOWLEDGED"
assert calls == []
print("public-import-and-execute-zero-external-operations")
'''
    env = {"PATH": "/usr/bin:/bin:/usr/sbin:/sbin", "PYTHONDONTWRITEBYTECODE": "1", "TMPDIR": os.environ["TMPDIR"],
           "PYTHONPATH": os.pathsep.join((str(root / "src"), str(root / "tests")))}
    result = subprocess.run([sys.executable, "-B", "-c", code], env=env, cwd=root, capture_output=True, text=True, timeout=20)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "public-import-and-execute-zero-external-operations"


def test_import_and_execute_have_no_app_auth_http_cache_or_database_access(monkeypatch):
    c = case()
    forbidden = ("invest_bot.config", "invest_bot.clients", "invest_bot.backtest", "requests", "sqlalchemy")
    calls = []
    original_import = builtins.__import__
    def guard_import(name, *args, **kwargs):
        if name.startswith(forbidden):
            calls.append("import"); raise AssertionError("forbidden import")
        return original_import(name, *args, **kwargs)
    def block(*args, **kwargs):
        calls.append("external access"); raise AssertionError("external access")
    from invest_bot import AppSettings
    monkeypatch.setattr(AppSettings, "from_file", block)
    monkeypatch.setattr(AppSettings, "__init__", block)
    monkeypatch.setattr(builtins, "__import__", guard_import)
    monkeypatch.setattr(builtins, "open", block)
    monkeypatch.setattr(Path, "open", block)
    monkeypatch.setattr(socket.socket, "connect", block)
    assert execute(broker(c), c).state is c.d.m.OrderState.ACKNOWLEDGED
    assert not execute(broker(c), c, policy=None).decision.allowed
    assert calls == []
