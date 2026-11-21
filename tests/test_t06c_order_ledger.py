from dataclasses import replace
from datetime import timedelta
from decimal import localcontext
import multiprocessing
import sqlite3
import threading

import pytest

from t06c_order_fixture import (
    NOW, D, ack, api, case, context, evidence, setup, start_spawned_worker, worker,
)


def test_durable_replay_and_conflict_precede_context_clock_and_kill_switch(tmp_path):
    c, store, service = setup(tmp_path / "ledger.db")
    calls = []
    first = service.submit(c.intent, context=lambda: context(c), send=lambda d: (calls.append(d.order_id), ack(d))[1])
    assert first.state == "ACKNOWLEDGED" and first.reserved_cash == D("202")
    def forbidden(): pytest.fail("replay consulted current evidence")
    reopened = api().v.OrderService(api().s.OrderStore.open(store.path), clock=forbidden, kill_switch=forbidden)
    assert reopened.submit(replace(c.intent, limit_price=D("100.00")), context=forbidden, send=forbidden) == first
    conflict = reopened.submit(replace(c.intent, qty=1), context=forbidden, send=forbidden)
    assert conflict.decision.reasons == (c.d.m.ReasonCode.IDEMPOTENCY_CONFLICT,)
    assert len(calls) == 1 and len(store.orders()) == 1


def test_denial_replay_and_kill_switch_before_send(tmp_path):
    c, store, _ = setup(tmp_path / "ledger.db")
    service = api().v.OrderService(store, clock=lambda: NOW, kill_switch=lambda: True)
    rejected = service.submit(c.intent, context=lambda: context(c), send=lambda d: pytest.fail("killed send"))
    assert rejected.state == "REJECTED"
    service = api().v.OrderService(api().s.OrderStore.open(store.path), clock=lambda: NOW, kill_switch=lambda: False)
    assert service.submit(c.intent, context=lambda: context(c), send=lambda d: pytest.fail("rejudged denial")) == rejected


@pytest.mark.parametrize("kind", ["missing", "corrupt", "schema", "data"])
def test_reopen_never_recreates_missing_damaged_or_wrong_ledger(tmp_path, kind):
    a = api(); path = tmp_path / "ledger.db"
    if kind != "missing":
        c, store, service = setup(path)
        service.submit(c.intent, context=lambda: context(c), send=ack)
        if kind == "corrupt": path.write_bytes(b"broken database")
        else:
            with sqlite3.connect(path) as con:
                if kind == "schema": con.execute("CREATE TABLE surprise(value TEXT)")
                else: con.execute("UPDATE orders SET state='FILLED'")
    with pytest.raises(a.s.LedgerUnavailable): a.s.OrderStore.open(path)
    if kind == "missing": assert not path.exists()


@pytest.mark.parametrize("mode", ["before", "after", "response"])
def test_commit_failure_cuts_off_send_or_preserves_uncertain_claim(tmp_path, monkeypatch, mode):
    c, store, service = setup(tmp_path / "ledger.db")
    original = store._commit; count = 0; sent = []
    def broken(con):
        nonlocal count
        count += 1
        if mode == "after" and count == 1:
            original(con); raise OSError("PRIVATE-COMMIT-DETAIL")
        if (mode == "before" and count == 1) or (mode == "response" and count == 2):
            raise OSError("PRIVATE-COMMIT-DETAIL")
        original(con)
    monkeypatch.setattr(store, "_commit", broken)
    with pytest.raises(api().s.LedgerUnavailable) as error:
        service.submit(c.intent, context=lambda: context(c), send=lambda d: (sent.append(1), ack(d))[1])
    assert "PRIVATE" not in str(error.value)
    assert len(sent) == (1 if mode == "response" else 0)
    reopened = api().s.OrderStore.open(store.path)
    if mode == "before": assert reopened.orders() == ()
    else:
        assert reopened.orders()[0].state == "SUBMITTING"
        other = api().v.OrderService(reopened, clock=lambda: pytest.fail("replayed clock"), kill_switch=lambda: pytest.fail("replayed kill"))
        assert other.submit(c.intent, context=lambda: pytest.fail("replayed context"), send=lambda d: pytest.fail("resent")).state == "SUBMITTING"
    assert b"PRIVATE-COMMIT-DETAIL" not in store.path.read_bytes()


@pytest.mark.parametrize("scenario", ["same-id", "last-cash", "last-stock"])
def test_independent_processes_race_on_real_file(tmp_path, scenario):
    c, store, service = setup(tmp_path / "ledger.db")
    mp = multiprocessing.get_context("spawn"); start = mp.Event(); queue = mp.Queue()
    marker = tmp_path / "sends.txt"
    processes = [mp.Process(target=worker, args=(str(store.path), start, queue, str(marker)), kwargs={
        "client_id": "order-1" if scenario == "same-id" else f"order-{n}",
        "sell": scenario == "last-stock", "cash": "202" if scenario == "last-cash" else "1000",
    }) for n in (1, 2)]
    for process in processes:
        start_spawned_worker(process)
    start.set()
    for process in processes:
        process.join(15)
        if process.is_alive(): process.terminate(); process.join(); pytest.fail("ledger race deadlocked")
        assert process.exitcode == 0
    results = [queue.get(timeout=3) for _ in processes]
    assert marker.read_text().count("\n") == 1
    assert "ACKNOWLEDGED" in results
    book = store.book()
    assert len(book.entries) == 1 and book.entries[0].cash <= D("202") and book.entries[0].qty <= 2


def test_active_sender_cannot_be_declared_not_accepted_and_other_account_can_send(tmp_path):
    c = case(); a = api()
    b = replace(c.binding, alias="paper-b", binding_id="binding-b")
    store = a.s.OrderStore.bootstrap(tmp_path / "ledger.db", book_id="book-a", bindings=(c.binding, b))
    service = a.v.OrderService(store, clock=lambda: NOW, kill_switch=lambda: False)
    entered, finish = threading.Event(), threading.Event(); result = []
    def send(dispatch): entered.set(); assert finish.wait(10); return ack(dispatch)
    thread = threading.Thread(target=lambda: result.append(service.submit(c.intent, context=lambda: context(c), send=send)))
    thread.start(); assert entered.wait(5)
    order = store.orders()[0]
    proof = api().v.SenderStoppedEvidence(order.order_id, order.account_binding_id, "supervisor", NOW)
    try:
        with pytest.raises(api().v.EvidenceRejected):
            service.reconcile(evidence(order, "NOT_ACCEPTED"), stopped=proof)
        assert store.get(order.order_id).state == "SUBMITTING" and store.get(order.order_id).reserved_cash == D("202")
        other = replace(c.intent, account_alias=b.alias, account_binding_id=b.binding_id)
        capture = replace(c.account, account_alias=b.alias, account_binding_id=b.binding_id)
        assert service.submit(other, context=lambda: a.v.ValidationContext(b, c.policy, capture, c.market, frozenset()), send=ack).state == "ACKNOWLEDGED"
    finally: finish.set(); thread.join(10)
    assert result[0].state == "ACKNOWLEDGED"


def test_abort_restart_unknown_and_explicit_stopped_sender_reconciliation(tmp_path):
    c, store, service = setup(tmp_path / "ledger.db")
    mp = multiprocessing.get_context("spawn"); start=mp.Event(); queue=mp.Queue(); marker=tmp_path/"sends.txt"
    process=mp.Process(target=worker,args=(str(store.path),start,queue,str(marker)),kwargs={"crash":True})
    start_spawned_worker(process)
    start.set()
    process.join(15)
    if process.is_alive(): process.terminate(); process.join(); pytest.fail("crash worker stuck")
    assert process.exitcode == 23
    service=api().v.OrderService(api().s.OrderStore.open(store.path),clock=lambda:NOW,kill_switch=lambda:False)
    record=store.orders()[0]
    assert record.state=="SUBMITTING"
    denied=service.submit(replace(c.intent,client_order_id="new"),context=lambda:context(c),send=lambda d:pytest.fail("bypassed unknown"))
    assert not denied.decision.allowed
    with pytest.raises(api().v.EvidenceRejected): service.reconcile(evidence(record,"NOT_FOUND"))
    with pytest.raises(api().v.EvidenceRejected): service.reconcile(evidence(record,"NOT_ACCEPTED"))
    proof=api().v.SenderStoppedEvidence(record.order_id,record.account_binding_id,"supervisor",NOW)
    cleared=service.reconcile(evidence(record,"NOT_ACCEPTED"),stopped=proof)
    assert cleared.order.state=="NOT_ACCEPTED" and store.book().entries==()
    assert marker.read_text().count("\n")==1


def test_partial_final_fill_exact_reservations_and_settlement_gate(tmp_path):
    c, store, service = setup(tmp_path / "ledger.db")
    record=service.submit(c.intent,context=lambda:context(c),send=ack)
    partial=evidence(record,"PARTIALLY_FILLED",qty=1,notional="99")
    with localcontext() as decimal_context:
        decimal_context.prec=2
        changed=service.reconcile(partial)
    assert changed.applied and changed.order.cumulative_qty==1
    assert changed.order.remaining_qty==1 and changed.order.reserved_cash==D("102")
    assert not service.reconcile(partial).applied
    stale=service.submit(replace(c.intent,client_order_id="old-capture"),context=lambda:context(c),send=lambda d:pytest.fail("stale filled funds"))
    assert not stale.decision.allowed
    final=evidence(record,"FILLED",qty=2,notional="198",seq=2,event="event-2")
    done=service.reconcile(final)
    assert done.order.state=="FILLED" and done.order.reserved_cash==0
    assert done.order.cumulative_notional==D("198")
    assert not service.reconcile(final).applied
    still_stale=service.submit(replace(c.intent,client_order_id="still-stale"),context=lambda:context(c),send=lambda d:pytest.fail("spent cash reused"))
    assert not still_stale.decision.allowed


@pytest.mark.parametrize("change", ["account", "broker", "oversize", "price", "sequence", "unconfirmed", "same-id-conflict"])
def test_bad_or_conflicting_evidence_changes_nothing(tmp_path, change):
    c, store, service=setup(tmp_path/"ledger.db")
    record=service.submit(c.intent,context=lambda:context(c),send=ack)
    first=evidence(record,"PARTIALLY_FILLED",qty=1,notional="99")
    service.reconcile(first); before=store.get(record.order_id)
    values={"event_id":"event-2","sequence":2,"kind":"FILLED","cumulative_qty":2,"cumulative_notional":D("198")}
    if change=="account": values["account_binding_id"]="other"
    elif change=="broker": values["broker_order_id"]="other"
    elif change=="oversize": values["cumulative_qty"]=3
    elif change=="price": values["cumulative_notional"]=D("300")
    elif change=="sequence": values["sequence"]=1
    elif change=="unconfirmed": values["confirmed"]=False
    else: values["event_id"]="event-1"
    with pytest.raises(api().v.EvidenceRejected): service.reconcile(replace(first,**values))
    assert store.get(record.order_id)==before


@pytest.mark.parametrize("boundary", ["expiry", "kill-switch"])
def test_context_delay_cannot_use_earlier_admission_time_or_kill_state(tmp_path, boundary):
    c, store, _ = setup(tmp_path / "ledger.db")
    now, killed = [NOW], [False]
    service = api().v.OrderService(store, clock=lambda: now[0], kill_switch=lambda: killed[0])
    def slow_context():
        if boundary == "expiry": now[0] = c.intent.expires_at
        else: killed[0] = True
        return context(c)
    result = service.submit(c.intent, context=slow_context, send=lambda d: pytest.fail("late dispatch"))
    assert not result.decision.allowed and store.book().entries == ()


@pytest.mark.parametrize("change", [{"mode": "live"}, {"execution_target": "real"}])
def test_disallowed_mode_preserves_t06b_reason(tmp_path, change):
    c, store, service = setup(tmp_path / "ledger.db")
    result = service.submit(replace(c.intent, **change), context=lambda: pytest.fail("mode context"), send=lambda d: pytest.fail("mode send"))
    assert result.decision.reasons == (c.d.m.ReasonCode.MODE_NOT_ALLOWED,)
    assert store.orders() == ()


@pytest.mark.parametrize("fault", ["old-time", "missing-receipt", "unknown-receipt", "old-watermark", "incomplete"])
def test_explicit_fill_receipts_cannot_approve_inconsistent_capture(tmp_path, fault):
    c, store, service = setup(tmp_path / "ledger.db")
    record = service.submit(c.intent, context=lambda: context(c), send=ack)
    service.reconcile(evidence(record, "PARTIALLY_FILLED", qty=1, notional="99"))
    book = store.book()
    account = replace(c.account, version="account-v2", available_cash=D("797"),
                      positions=(c.d.m.Position("005930", 1, D("99"), D("100")),),
                      account_exposure=D("199"), open_order_count=1,
                      reservation_watermark=book.revision, included_reservation_ids=frozenset({record.order_id}))
    settled = frozenset({"event-1"})
    if fault == "old-time": account = replace(account, captured_at=NOW-timedelta(seconds=1))
    elif fault == "missing-receipt": settled = frozenset()
    elif fault == "unknown-receipt": settled = frozenset({"event-1", "unseen"})
    elif fault == "old-watermark": account = replace(account, reservation_watermark=0, included_reservation_ids=frozenset())
    else: account = replace(account, reservations_complete=False)
    current = api().v.ValidationContext(c.binding, c.policy, account, c.market, settled)
    denied = service.submit(replace(c.intent, client_order_id="new"), context=lambda: current, send=lambda d: pytest.fail("unsettled admission"))
    assert not denied.decision.allowed


@pytest.mark.parametrize("terminal", [False, True])
def test_consistent_settled_capture_allows_new_order_without_double_reservation(tmp_path, terminal):
    c, store, service = setup(tmp_path / "ledger.db")
    record = service.submit(c.intent, context=lambda: context(c), send=ack)
    qty, actual, kind = (2, "198", "FILLED") if terminal else (1, "99", "PARTIALLY_FILLED")
    service.reconcile(evidence(record, kind, qty=qty, notional=actual))
    account = replace(c.account, version="account-v2", available_cash=D("797"),
                      positions=(c.d.m.Position("005930", qty, D(actual), D("0") if terminal else D("100")),),
                      account_exposure=D(actual) if terminal else D("199"), open_order_count=0 if terminal else 1,
                      reservation_watermark=store.book().revision,
                      included_reservation_ids=frozenset() if terminal else frozenset({record.order_id}))
    current = api().v.ValidationContext(c.binding, c.policy, account, c.market, frozenset({"event-1"}))
    new = service.submit(replace(c.intent, client_order_id="new"), context=lambda: current, send=ack)
    assert new.state == "ACKNOWLEDGED" and len(store.book().entries) == (1 if terminal else 2)
    assert new.reserved_cash == D("202")


@pytest.mark.parametrize("sell", [False, True])
def test_incremental_fill_price_cannot_hide_behind_cumulative_average(tmp_path, sell):
    c = case()
    if sell:
        c.intent = replace(c.intent, side=c.d.m.Side.SELL)
        c.account = replace(c.account, positions=(c.d.m.Position("005930", 2, D("200"), D("0")),), account_exposure=D("200"))
    c, store, service = setup(tmp_path / "ledger.db", c=c)
    record = service.submit(c.intent, context=lambda: context(c), send=ack)
    partial = service.reconcile(evidence(record, "PARTIALLY_FILLED", qty=1, notional="150" if sell else "50"))
    assert partial.order.reserved_cash == D("4" if sell else "102")
    assert partial.order.reserved_qty == (1 if sell else 0)
    with pytest.raises(api().v.EvidenceRejected):
        service.reconcile(evidence(record, "FILLED", qty=2, notional="240" if sell else "170", seq=2, event="event-2"))
    assert store.get(record.order_id) == partial.order


@pytest.mark.parametrize("terminal", ["CANCELLED", "EXPIRED"])
def test_terminal_reconciliation_releases_only_remaining_reservation(tmp_path, terminal):
    c, store, service = setup(tmp_path / "ledger.db")
    record = service.submit(c.intent, context=lambda: context(c), send=ack)
    service.reconcile(evidence(record, "PARTIALLY_FILLED", qty=1, notional="99"))
    done = service.reconcile(evidence(record, terminal, qty=1, notional="99", seq=2, event="event-2"))
    assert done.order.cumulative_qty == 1 and done.order.cumulative_notional == D("99")
    assert done.order.reserved_cash == 0 and store.book().entries == ()
    denied = service.submit(replace(c.intent, client_order_id="new"), context=lambda: context(c), send=lambda d: pytest.fail("spent fill reused"))
    assert not denied.decision.allowed


@pytest.mark.parametrize("reply", ["exception", "unconfirmed", "wrong-account", "wrong-order", "rejected"])
def test_send_ambiguity_never_becomes_clear_rejection(tmp_path, reply):
    c, store, service = setup(tmp_path / "ledger.db")
    def send(dispatch):
        if reply == "exception": raise RuntimeError("PRIVATE-RESPONSE-TEXT")
        result = ack(dispatch)
        if reply == "unconfirmed": return replace(result, status="BROKER_REJECTED", confirmed=False)
        if reply == "wrong-account": return replace(result, account_binding_id="other")
        if reply == "wrong-order": return replace(result, order_id="other")
        return replace(result, status="BROKER_REJECTED")
    record = service.submit(c.intent, context=lambda: context(c), send=send)
    assert record.state == ("BROKER_REJECTED" if reply == "rejected" else "UNKNOWN")
    assert bool(store.book().entries) == (reply != "rejected")
    reopened = api().s.OrderStore.open(store.path)
    assert reopened.get(record.order_id) == record
    assert b"PRIVATE-RESPONSE-TEXT" not in store.path.read_bytes()
    if reply != "rejected":
        newer = service.submit(replace(c.intent, client_order_id="new"), context=lambda: pytest.fail("blocked context"), send=lambda d: pytest.fail("unknown retry"))
        assert newer.decision.reasons == (c.d.m.ReasonCode.RECONCILIATION_REQUIRED,)


@pytest.mark.parametrize("change", ["balance", "backwards-time", "backwards-watermark"])
def test_capture_version_pin_and_backward_evidence_are_fail_closed(tmp_path, change):
    c, store, service = setup(tmp_path / "ledger.db")
    record = service.submit(c.intent, context=lambda: context(c), send=ack)
    account = replace(c.account, version="account-v2", available_cash=D("798"),
                      positions=(c.d.m.Position("005930", 0, D("0"), D("200")),),
                      account_exposure=D("200"), open_order_count=1, reservation_watermark=store.book().revision,
                      included_reservation_ids=frozenset({record.order_id}))
    current = api().v.ValidationContext(c.binding, c.policy, account, c.market, frozenset())
    service.submit(replace(c.intent, client_order_id="pin", qty=1), context=lambda: current, send=ack)
    if change == "balance": account = replace(account, available_cash=D("900"))
    elif change == "backwards-time": account = replace(account, version="account-v3", captured_at=NOW-timedelta(seconds=1))
    else: account = replace(account, version="account-v3", reservation_watermark=0, included_reservation_ids=frozenset())
    current = replace(current, account=account)
    result = service.submit(replace(c.intent, client_order_id="new"), context=lambda: current, send=lambda d: pytest.fail("changed capture used"))
    assert result.decision.reasons == (c.d.m.ReasonCode.SNAPSHOT_INVALID,)


@pytest.mark.parametrize("damage", ["missing", "corrupt", "replacement"])
def test_sender_barrier_loss_or_replacement_never_recreates_it(tmp_path, damage):
    c, store, service = setup(tmp_path / "ledger.db")
    lock = store.barrier_path
    if damage == "missing": lock.unlink()
    elif damage == "corrupt": lock.write_bytes(b"wrong ledger")
    else:
        replacement = tmp_path / "replacement"
        replacement.write_bytes(lock.read_bytes()); replacement.replace(lock)
    with pytest.raises(api().s.LedgerUnavailable): api().s.OrderStore.open(store.path)
    with pytest.raises(api().s.LedgerUnavailable): service.submit(c.intent, context=lambda: context(c), send=lambda d: pytest.fail("unprotected sender"))
    if damage == "missing": assert not lock.exists()


def test_request_secret_fields_are_hashed_not_persisted_and_bootstrap_is_explicit(tmp_path):
    c, store, service = setup(tmp_path / "ledger.db")
    secret = "PRIVATE-SOURCE-PAYLOAD"
    service.submit(replace(c.intent, source_id=secret), context=lambda: context(c), send=ack)
    assert secret.encode() not in store.path.read_bytes()
    with pytest.raises(api().s.LedgerUnavailable):
        api().s.OrderStore.bootstrap(store.path, book_id="book-a", bindings=(c.binding,))
    with sqlite3.connect(store.path) as con: con.execute("DELETE FROM audits")
    with pytest.raises(api().s.LedgerUnavailable): store.orders()


def test_reused_broker_identity_cannot_resolve_two_orders(tmp_path):
    c, store, service = setup(tmp_path / "ledger.db")
    first = service.submit(c.intent, context=lambda: context(c), send=ack)
    second = service.submit(replace(c.intent, client_order_id="second"), context=lambda: context(c),
                            send=lambda d: replace(ack(d), broker_order_id=first.broker_order_id))
    assert second.state == "UNKNOWN" and len(store.book().entries) == 2
    with pytest.raises(api().v.EvidenceRejected):
        service.reconcile(evidence(second, "ACKNOWLEDGED", broker_order_id=first.broker_order_id))
    assert store.get(second.order_id) == second


@pytest.mark.parametrize("after_commit", [False, True])
def test_reconciliation_commit_failure_is_atomic_and_never_dispatches(tmp_path, monkeypatch, after_commit):
    c, store, service = setup(tmp_path / "ledger.db")
    original = service.submit(c.intent, context=lambda: context(c), send=ack)
    fill = evidence(original, "PARTIALLY_FILLED", qty=1, notional="99")
    commit = store._commit
    def broken(con):
        if after_commit: commit(con)
        raise OSError("PRIVATE-RECONCILE-DETAIL")
    monkeypatch.setattr(store, "_commit", broken)
    with pytest.raises(api().s.LedgerUnavailable): service.reconcile(fill)
    reopened = api().s.OrderStore.open(store.path)
    current = reopened.get(original.order_id)
    assert current.state == ("PARTIALLY_FILLED" if after_commit else "ACKNOWLEDGED")
    assert current.reserved_cash == D("102" if after_commit else "202")
    assert b"PRIVATE-RECONCILE-DETAIL" not in store.path.read_bytes()
    if after_commit:
        replay = api().v.OrderService(reopened, clock=lambda: pytest.fail("duplicate clock"), kill_switch=lambda: pytest.fail("duplicate kill"))
        assert not replay.reconcile(fill).applied


def test_unknown_can_be_resolved_by_confirmed_not_accepted_after_sender_returned(tmp_path):
    c, store, service = setup(tmp_path / "ledger.db")
    record = service.submit(c.intent, context=lambda: context(c), send=lambda d: None)
    assert record.state == "UNKNOWN"
    done = service.reconcile(evidence(record, "NOT_ACCEPTED"))
    assert done.order.state == "NOT_ACCEPTED" and store.book().entries == ()
    assert not service.reconcile(evidence(record, "NOT_ACCEPTED")).applied
    newer = service.submit(replace(c.intent, client_order_id="new"), context=lambda: context(c), send=ack)
    assert newer.state == "ACKNOWLEDGED"


def test_new_claim_fetches_context_and_clock_only_after_writer_lock(tmp_path):
    c, store, service = setup(tmp_path / "ledger.db")
    entered, read_context, read_clock = threading.Event(), threading.Event(), threading.Event()
    now, result, errors = [NOW], [], []
    service = api().v.OrderService(store, clock=lambda: (read_clock.set(), now[0])[1], kill_switch=lambda: False)
    def run():
        entered.set()
        try:
            result.append(service.submit(c.intent, context=lambda: (read_context.set(), context(c))[1], send=lambda d: pytest.fail("expired while waiting")))
        except BaseException as error: errors.append(type(error).__name__)
    with store.transaction(write=True):
        thread = threading.Thread(target=run); thread.start(); assert entered.wait(3)
        assert not read_context.wait(.05) and not read_clock.is_set()
        now[0] = c.intent.expires_at
    thread.join(10)
    assert not thread.is_alive() and errors == []
    assert read_context.is_set() and read_clock.is_set() and not result[0].decision.allowed
