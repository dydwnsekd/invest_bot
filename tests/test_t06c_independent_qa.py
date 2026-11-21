"""Seven independent POSIX/SQLite cases using the public T06c contracts."""
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal, Inexact, Rounded, localcontext
import hashlib
import json
import multiprocessing
from pathlib import Path
import sqlite3
import stat
import subprocess
import sys
from types import SimpleNamespace
from urllib.parse import quote

import pytest

from t06c_order_fixture import start_spawned_worker

from invest_bot.trading.models import AccountBinding, AccountSnapshot, MarketSnapshot, OrderIntent, Position, RiskPolicy, Side
from invest_bot.trading.order_service import (
    EvidenceRejected, OrderService, ReconciliationEvidence, SenderStoppedEvidence,
    SubmissionReply, ValidationContext,
)
from invest_bot.trading.order_store import LedgerUnavailable, OrderStore

D = Decimal
NOW = datetime(2026, 11, 21, 4, tzinfo=UTC)


def data(other=False):
    suffix = "b" if other else "a"
    binding = AccountBinding("qa-paper-" + suffix, "qa-binding-" + suffix, "qa-binding-v1", "mock", "dry_run")
    intent = OrderIntent(1, "qa-first", "dry_run", "mock", binding.alias, binding.binding_id, binding.version,
                         "333333", Side.BUY, 7, D("12.50"), "KRW", "domestic_stock", "LIMIT", "qa-signal",
                         NOW-timedelta(seconds=1), NOW+timedelta(seconds=60))
    policy = RiskPolicy("qa-policy", "dry_run", "mock", frozenset({"333333"}), frozenset({"domestic_stock"}),
                        frozenset({"qa-session"}), D("500"), D("1000"), D("2000"), D("20"), 10,
                        D(".02"), D(".03"), D(".03"), D(".04"), D(".05"),
                        timedelta(seconds=120), timedelta(seconds=120), timedelta(seconds=30),
                        timedelta(seconds=30), timedelta(seconds=30))
    account = AccountSnapshot("qa-capture-1", "dry_run", "mock", binding.alias, binding.binding_id, binding.version,
                              "KRW", NOW, True, True, D("200"), (), D("0"), 0, NOW, "qa-valuation", "qa-book", 0, frozenset())
    market = MarketSnapshot("qa-market", "dry_run", "mock", "333333", "domestic_stock", "KRW", NOW,
                            True, True, "qa-session", "qa-calendar", "qa-calendar-v1", D(".25"), D("1"), D("100"))
    return SimpleNamespace(binding=binding, intent=intent, policy=policy, account=account, market=market)


def context(c, account=None, receipts=frozenset()):
    return ValidationContext(c.binding, c.policy, c.account if account is None else account, c.market, receipts)


def ack(dispatch):
    return SubmissionReply(dispatch.order_id, dispatch.account_binding_id, "ACKNOWLEDGED", "qa-broker-" + dispatch.order_id, True)


def proof(order, kind, *, event="qa-proof", sequence=1, qty=0, notional="0", at=NOW):
    return ReconciliationEvidence(event, order.order_id, order.account_binding_id,
                                  None if kind == "NOT_ACCEPTED" else order.broker_order_id,
                                  "qa-confirmed-source", at, kind, sequence, qty, D(notional), True)


def fail(*args, **kwargs):
    raise AssertionError("unexpected dispatch/context/clock")


def logical_state(path):
    with sqlite3.connect("file:" + quote(str(path), safe="/") + "?mode=ro", uri=True) as connection:
        return tuple(connection.iterdump())


def persisted_payload(path, order_id):
    with sqlite3.connect("file:" + quote(str(path), safe="/") + "?mode=ro", uri=True) as connection:
        row = connection.execute("SELECT state,payload FROM orders WHERE order_id=?", (order_id,)).fetchone()
        return row[0], json.loads(row[1])


def live_sender(path, ready, hold):
    c = data()
    service = OrderService(OrderStore.open(path), clock=lambda: NOW, kill_switch=lambda: False)
    def send(dispatch):
        ready.send(dispatch.order_id)
        if not hold.wait(30):
            raise AssertionError("parent failed to stop the test sender")
        return ack(dispatch)
    service.submit(c.intent, context=lambda: context(c), send=send)


def test_live_process_and_orphan_reopen_do_not_authorize_early_release_or_resend(tmp_path):
    c, separate = data(), data(True)
    path = tmp_path / "live ledger 한글.sqlite"
    OrderStore.bootstrap(path, book_id="qa-book", bindings=(c.binding, separate.binding))
    mp = multiprocessing.get_context("spawn")
    reader, writer = mp.Pipe(duplex=False)
    hold = mp.Event()
    process = mp.Process(target=live_sender, args=(str(path), writer, hold))
    start_spawned_worker(process)
    try:
        assert reader.poll(10), "child did not reach its synchronous sender"
        order_id = reader.recv()
        independent = OrderStore.open(path)
        current = independent.get(order_id)
        assert current.state == "SUBMITTING" and current.reserved_cash == D("89.30")
        assert process.is_alive()
        service = OrderService(independent, clock=lambda: NOW, kill_switch=lambda: False)
        stopped = SenderStoppedEvidence(order_id, c.binding.binding_id, "qa-stopped-claim", NOW)
        before = logical_state(path)
        with pytest.raises(EvidenceRejected, match="SENDER_STILL_ACTIVE"):
            service.reconcile(proof(current, "NOT_ACCEPTED"), stopped=stopped)
        assert logical_state(path) == before
        assert service.submit(c.intent, context=fail, send=fail) == current
        conflict = service.submit(replace(c.intent, qty=6), context=fail, send=fail)
        assert conflict.decision.reasons[0].value == "IDEMPOTENCY_CONFLICT"
        consultations = []
        def valid_context():
            consultations.append(1)
            return context(c)
        denied = service.submit(replace(c.intent, client_order_id="qa-new-id"), context=valid_context, send=fail)
        assert denied.decision.reasons[0].value == "RECONCILIATION_REQUIRED"
        assert consultations == []
        other = service.submit(separate.intent, context=lambda: context(separate), send=ack)
        assert other.state == "ACKNOWLEDGED" and independent.get(order_id) == current
        process.terminate()
        process.join(10)
        assert not process.is_alive() and process.exitcode is not None
        reopened = OrderStore.open(path)
        replay = OrderService(reopened, clock=fail, kill_switch=fail)
        assert replay.submit(c.intent, context=fail, send=fail) == current
        restored = OrderService(reopened, clock=lambda: NOW, kill_switch=lambda: False)
        blocked = restored.submit(replace(c.intent, client_order_id="qa-after-restart"), context=valid_context, send=fail)
        assert blocked.decision.reasons[0].value == "RECONCILIATION_REQUIRED"
        assert consultations == []
        resolved = restored.reconcile(proof(current, "NOT_ACCEPTED"), stopped=stopped)
        assert resolved.applied and resolved.order.state == "NOT_ACCEPTED" and resolved.order.reserved_cash == 0
        assert len(reopened.book().entries) == 1
        assert reopened.book().entries[0].account_binding_id == separate.binding.binding_id
    finally:
        if process.is_alive():
            process.terminate()
        process.join(10)
        reader.close()
        writer.close()


@pytest.mark.parametrize("terminal", ["FILLED", "CANCELLED", "EXPIRED"])
def test_partial_terminal_database_values_and_settlement_gate_are_atomic(tmp_path, terminal):
    c = data()
    path = tmp_path / (terminal + ".sqlite")
    store = OrderStore.bootstrap(path, book_id="qa-book", bindings=(c.binding,))
    service = OrderService(store, clock=lambda: NOW+timedelta(seconds=3), kill_switch=lambda: False)
    sent = []
    def sender(dispatch):
        sent.append(dispatch.order_id)
        return ack(dispatch)
    original = service.submit(c.intent, context=lambda: context(c), send=sender)
    assert original.state == "ACKNOWLEDGED" and original.reserved_cash == D("89.30")
    # 87.50 notional; ceil((1.75+.03)/.05)*.05 = 1.80 fee.
    partial = proof(original, "PARTIALLY_FILLED", event="qa-partial", qty=3, notional="36.75", at=NOW+timedelta(seconds=3))
    with localcontext() as decimal_context:
        decimal_context.prec = 2
        decimal_context.traps[Inexact] = decimal_context.traps[Rounded] = True
        result = service.reconcile(partial)
    assert result.applied
    assert (result.order.remaining_qty, result.order.cumulative_qty, result.order.cumulative_notional) == (4, 3, D("36.75"))
    assert (result.order.reserved_cash, result.order.reserved_exposure) == (D("51.80"), D("50.00"))
    state, raw = persisted_payload(path, original.order_id)
    assert state == "PARTIALLY_FILLED" and raw["remaining_qty"] == 4 and raw["cumulative_qty"] == 3
    assert D(raw["reserved_cash"]) == D("51.80") and D(raw["cumulative_notional"]) == D("36.75")
    before = logical_state(path)
    for bad in (replace(partial, event_id="qa-reverse", sequence=2, cumulative_qty=2),
                replace(partial, cumulative_notional=D("36.50")), replace(partial, confirmed=False)):
        with pytest.raises(EvidenceRejected):
            service.reconcile(bad)
        assert logical_state(path) == before
    final_qty, final_notional = (7, "86.00") if terminal == "FILLED" else (3, "36.75")
    terminal_proof = proof(original, terminal, event="qa-terminal", sequence=2, qty=final_qty,
                           notional=final_notional, at=NOW+timedelta(seconds=3))
    finished = service.reconcile(terminal_proof).order
    assert (finished.state, finished.remaining_qty, finished.reserved_cash, finished.reserved_exposure) == (terminal, 0, 0, 0)
    assert finished.cumulative_qty == final_qty and finished.cumulative_notional == D(final_notional)
    assert store.book().entries == ()
    state, raw = persisted_payload(path, original.order_id)
    assert state == terminal and raw["remaining_qty"] == 0 and D(raw["reserved_cash"]) == 0
    assert raw["cumulative_qty"] == final_qty and D(raw["cumulative_notional"]) == D(final_notional)
    unchanged = logical_state(path)
    replay_service = OrderService(OrderStore.open(path), clock=fail, kill_switch=fail)
    assert replay_service.submit(c.intent, context=fail, send=fail) == finished
    assert not replay_service.reconcile(terminal_proof).applied
    assert replay_service.submit(replace(c.intent, qty=8), context=fail, send=fail).state == "REJECTED"
    assert logical_state(path) == unchanged
    receipts = frozenset({"qa-partial", "qa-terminal"} if terminal == "FILLED" else {"qa-partial"})
    old = replace(c.account, version="qa-stale-renamed", reservation_watermark=store.book().revision)
    denied = service.submit(replace(c.intent, client_order_id="qa-stale-id"), context=lambda: context(c, old, receipts), send=fail)
    assert denied.decision.reasons[0].value == "SNAPSHOT_INVALID"
    actual_cash, valuation, large_qty = ("112.20", "87.50", 9) if terminal == "FILLED" else ("161.45", "37.50", 13)
    settled = replace(c.account, version="qa-settled", captured_at=NOW+timedelta(seconds=3), valuation_at=NOW+timedelta(seconds=3),
                      available_cash=D(actual_cash), positions=(Position("333333", final_qty, D(valuation), D("0")),),
                      account_exposure=D(valuation), reservation_watermark=store.book().revision)
    insufficient = service.submit(replace(c.intent, client_order_id="qa-too-large", qty=large_qty),
                                  context=lambda: context(c, settled, receipts), send=fail)
    assert insufficient.decision.reasons[0].value == "INSUFFICIENT_CASH"
    accepted = service.submit(replace(c.intent, client_order_id="qa-small-valid", qty=1),
                              context=lambda: context(c, settled, receipts), send=sender)
    assert accepted.state == "ACKNOWLEDGED" and accepted.reserved_cash == D("12.80") and len(sent) == 2
    assert store.get(original.order_id) == finished


@pytest.mark.parametrize("phase", ["before-claim-commit", "response-persistence"])
def test_commit_faults_never_resend_and_durable_status_is_queryable(tmp_path, monkeypatch, phase):
    c = data()
    path = tmp_path / "fault.sqlite"
    store = OrderStore.bootstrap(path, book_id="qa-book", bindings=(c.binding,))
    service = OrderService(store, clock=lambda: NOW, kill_switch=lambda: False)
    real_commit = store._commit
    commits, sent = [], []
    def fault(connection):
        commits.append(1)
        if len(commits) == (1 if phase == "before-claim-commit" else 2):
            raise RuntimeError("qa-private-failure-detail")
        real_commit(connection)
    monkeypatch.setattr(store, "_commit", fault)  # Fault injection only, real DB/transactions/service.
    def sender(dispatch):
        sent.append(dispatch)
        return ack(dispatch)
    initial = logical_state(path)
    with pytest.raises(LedgerUnavailable) as error:
        service.submit(c.intent, context=lambda: context(c), send=sender)
    assert "qa-private-failure-detail" not in str(error.value)
    reopened = OrderStore.open(path)
    if phase == "before-claim-commit":
        assert not sent and reopened.orders() == () and logical_state(path) == initial
    else:
        assert len(sent) == 1
        pending = reopened.orders()[0]
        assert pending.state == "SUBMITTING" and pending.reserved_cash == D("89.30")
        no_resend = OrderService(reopened, clock=fail, kill_switch=fail)
        assert no_resend.submit(c.intent, context=fail, send=fail) == pending
        resolver = OrderService(reopened, clock=lambda: NOW, kill_switch=lambda: False)
        actual_ack = replace(proof(pending, "ACKNOWLEDGED"), broker_order_id=ack(sent[0]).broker_order_id)
        stopped = SenderStoppedEvidence(pending.order_id, c.binding.binding_id, "qa-sync-returned", NOW)
        resolved = resolver.reconcile(actual_ack, stopped=stopped)
        assert resolved.order.state == "ACKNOWLEDGED" and resolved.order.reserved_cash == D("89.30")
        assert len(sent) == 1 and len(reopened.book().entries) == 1


def test_file_pair_permissions_fail_closed_open_and_import_has_no_creation(tmp_path):
    root = Path(__file__).resolve().parents[1]
    code = '''
import sqlite3, sys, os, pathlib
attempts=[]
def audit(event,args):
    if event.startswith("sqlite3.connect") or event in ("socket.connect","socket.bind"):
        attempts.append(event); raise AssertionError(event)
    if event=="open":
        path,mode,flags=args
        if type(path) is not str or flags & (os.O_WRONLY|os.O_RDWR|os.O_CREAT|os.O_TRUNC) or pathlib.Path(path).suffix not in (".py",".pyc",".so",".zip"):
            attempts.append("non-source-io"); raise AssertionError("non-source-io")
sys.addaudithook(audit)
from invest_bot.trading.order_store import OrderStore
from invest_bot.trading.order_service import OrderService
assert not attempts
print("normal-import-no-ledger-or-external-io")
'''
    child = subprocess.run([sys.executable, "-B", "-c", "import sys;sys.path.insert(0,"+repr(str(root/"src"))+")\n"+code],
                           cwd=root, env={"PATH":"/usr/bin:/bin:/usr/sbin:/sbin", "PYTHONDONTWRITEBYTECODE":"1", "TMPDIR":str(root.parent/"tmp")},
                           text=True, capture_output=True, timeout=20)
    assert child.returncode == 0, child.stdout+child.stderr
    assert child.stdout.strip() == "normal-import-no-ledger-or-external-io"
    missing = tmp_path / "absent.sqlite"
    with pytest.raises(LedgerUnavailable):
        OrderStore.open(missing)
    assert not missing.exists() and not missing.with_name(missing.name+".sender-lock").exists()
    c = data()
    path = tmp_path / "pair.sqlite"
    store = OrderStore.bootstrap(path, book_id="qa-book", bindings=(c.binding,))
    companion = path.with_name(path.name+".sender-lock")
    assert stat.S_IMODE(path.stat().st_mode) == stat.S_IMODE(companion.stat().st_mode) == 0o600
    before = (hashlib.sha256(path.read_bytes()).hexdigest(), companion.read_bytes())
    with pytest.raises(LedgerUnavailable):
        OrderStore.bootstrap(path, book_id="qa-other-book", bindings=(c.binding,))
    assert before == (hashlib.sha256(path.read_bytes()).hexdigest(), companion.read_bytes())
    companion.unlink()
    with pytest.raises(LedgerUnavailable):
        OrderStore.open(path)
    with pytest.raises(LedgerUnavailable):
        store.book()
    assert not companion.exists()
