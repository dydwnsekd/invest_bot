from dataclasses import replace
from datetime import timedelta
from decimal import Decimal
from types import SimpleNamespace

import pytest
import requests

from invest_bot.clients.kis_order_client import KISMockBoundaryError, KISMockOrderClient
from invest_bot.trading.kis_mock_orders import KISMockOrders
from invest_bot.trading.models import Position, ReasonCode
from invest_bot.trading.order_service import ValidationContext
from invest_bot.trading.order_store import LedgerUnavailable, OrderStore

from t06b_order_fixture import case as risk_case
from tests.test_t06d_kis_order_client import BASE, BROKER_ID, NOW, ORDER_PATH
from tests.test_t06d_kis_order_client import acceptance, case as client_case, page, row


def setup(tmp_path, *responses):
    runtime = SimpleNamespace(now=NOW, paused=False)
    clock = lambda: runtime.now
    kill_switch = lambda: runtime.paused
    c = client_case(*responses, clock=clock)
    binding = c.client.binding
    inputs = risk_case()
    scope = dict(
        account_alias=binding.alias, account_binding_id=binding.binding_id,
        binding_version=binding.version, execution_target="kis_mock",
    )
    intent = replace(inputs.intent, **scope, created_at=NOW - timedelta(seconds=1), expires_at=NOW + timedelta(seconds=10))
    account = replace(inputs.account, **scope, captured_at=NOW, valuation_at=NOW)
    context = ValidationContext(
        binding, replace(inputs.policy, execution_target="kis_mock"), account,
        replace(inputs.market, execution_target="kis_mock", captured_at=NOW), frozenset(),
    )
    store = OrderStore.bootstrap(
        tmp_path / "paper.sqlite", book_id=inputs.book.book_id, bindings=(binding,), execution_target="kis_mock",
    )
    orders = KISMockOrders(store, c.client, clock=clock, kill_switch=kill_switch)
    return SimpleNamespace(
        wire=c, store=store, orders=orders, intent=intent, context=context, runtime=runtime,
        clock=clock, kill_switch=kill_switch,
    )


def reopen(c):
    return KISMockOrders(
        OrderStore.open(c.store.path, execution_target="kis_mock"),
        c.wire.client, clock=c.clock, kill_switch=c.kill_switch,
    )


def forbidden_context():
    pytest.fail("unexpected context lookup")


def test_order_post_observes_durable_reservation_and_reopen_replays(tmp_path, monkeypatch):
    c = setup(tmp_path, acceptance())
    request = c.wire.session.request

    def observe(method, url, **kwargs):
        store = OrderStore.open(c.store.path, execution_target="kis_mock")
        pending, = store.orders()
        assert pending.state == "SUBMITTING" and pending.reserved_cash == Decimal("202")
        assert store.book().entries[0].cash == Decimal("202")
        return request(method, url, **kwargs)

    monkeypatch.setattr(c.wire.session, "request", observe)
    first = c.orders.submit(c.intent, context=lambda: c.context)
    assert first.execution_target == "kis_mock" and first.state == "ACKNOWLEDGED"
    assert first.broker_order_id == BROKER_ID and first.cumulative_qty == 0
    assert reopen(c).submit(c.intent, context=forbidden_context) == first
    changed = replace(c.intent, qty=1)
    assert reopen(c).submit(changed, context=forbidden_context).decision.reasons == (ReasonCode.IDEMPOTENCY_CONFLICT,)
    assert len(c.wire.session.calls) == 1
    raw = c.store.path.read_bytes()
    credentials = c.wire.credentials
    for value in (credentials.account_number, credentials.app_key, credentials.app_secret, credentials.access_token):
        assert value.encode() not in raw


@pytest.mark.parametrize("change,reason", [
    ("live", ReasonCode.MODE_NOT_ALLOWED),
    ("dry_run", ReasonCode.MODE_NOT_ALLOWED),
    ("account", ReasonCode.INVALID_ORDER),
    ("symbol", ReasonCode.INVALID_ORDER),
    ("fractional_won", ReasonCode.INVALID_ORDER),
    ("foreign_policy", ReasonCode.POLICY_REQUIRED),
    ("foreign_snapshot", ReasonCode.SNAPSHOT_INVALID),
    ("foreign_market", ReasonCode.MARKET_UNAVAILABLE),
    ("insufficient", ReasonCode.INSUFFICIENT_CASH),
])
def test_invalid_mode_context_and_limits_make_no_order_request(tmp_path, change, reason):
    c = setup(tmp_path)
    intent, context = c.intent, c.context
    if change == "live":
        intent = replace(intent, mode="live")
    elif change == "dry_run":
        intent = replace(intent, execution_target="dry_run")
    elif change == "account":
        intent = replace(intent, account_binding_id="another-binding")
    elif change == "symbol":
        intent = replace(intent, symbol="TEST")
    elif change == "fractional_won":
        intent = replace(intent, limit_price=Decimal("100.5"))
    elif change == "foreign_policy":
        context = replace(context, policy=replace(context.policy, execution_target="dry_run"))
    elif change == "foreign_snapshot":
        context = replace(context, account=replace(context.account, execution_target="dry_run"))
    elif change == "foreign_market":
        context = replace(context, market=replace(context.market, execution_target="dry_run"))
    else:
        context = replace(context, account=replace(context.account, available_cash=Decimal("201")))
    result = c.orders.submit(intent, context=lambda: context)
    assert result.state == "REJECTED" and result.decision.reasons == (reason,)
    assert c.wire.session.calls == [] and c.store.book().entries == ()


def test_mock_ledger_accepts_only_the_explicit_target_and_account(tmp_path):
    c = setup(tmp_path)
    dry_binding = risk_case().binding
    dry = OrderStore.bootstrap(tmp_path / "dry.sqlite", book_id="book-a", bindings=(dry_binding,))
    assert OrderStore.open(dry.path).bindings() == (dry_binding,)
    before = (dry.path.read_bytes(), c.store.path.read_bytes())
    with pytest.raises(LedgerUnavailable):
        OrderStore.open(c.store.path)
    with pytest.raises(LedgerUnavailable):
        OrderStore.open(dry.path, execution_target="kis_mock")
    with pytest.raises(KISMockBoundaryError, match="MOCK_LEDGER_BINDING_MISMATCH"):
        KISMockOrders(dry, c.wire.client, clock=c.clock, kill_switch=c.kill_switch)
    mismatched = KISMockOrderClient(**dict(
        c.wire.arguments, credentials=replace(c.wire.credentials, account_number="23456789"),
    ))
    with pytest.raises(KISMockBoundaryError, match="MOCK_LEDGER_BINDING_MISMATCH"):
        KISMockOrders(c.store, mismatched, clock=c.clock, kill_switch=c.kill_switch)
    assert before == (dry.path.read_bytes(), c.store.path.read_bytes())
    assert c.wire.session.calls == []


@pytest.mark.parametrize("condition", ["kill", "expiry", "stale_market"])
def test_after_claim_recheck_releases_only_when_sender_knows_no_post(tmp_path, monkeypatch, condition):
    c = setup(tmp_path)
    if condition == "stale_market":
        c.intent = replace(c.intent, expires_at=NOW + timedelta(seconds=20))
        c.context = replace(c.context, policy=replace(c.context.policy, max_market_age=timedelta(seconds=2)))
    commit = c.store._commit

    def change_after_commit(connection):
        commit(connection)
        if condition == "kill":
            c.runtime.paused = True
        elif condition == "expiry":
            c.runtime.now = c.intent.expires_at
        else:
            c.runtime.now = NOW + timedelta(seconds=3)

    monkeypatch.setattr(c.store, "_commit", change_after_commit)
    result = c.orders.submit(c.intent, context=lambda: c.context)
    assert result.state == "NOT_ACCEPTED" and result.reserved_cash == 0
    assert c.wire.session.calls == [] and c.store.book().entries == ()
    with c.store.transaction() as connection:
        assert [row["action"] for row in connection.execute("SELECT action FROM audits ORDER BY revision")] == [
            "CLAIM", "SEND_SKIPPED",
        ]


def test_unknown_after_timeout_blocks_new_order_and_never_searches_without_reference(tmp_path):
    c = setup(tmp_path, TimeoutError("PRIVATE synthetic timeout"), acceptance())
    unknown = c.orders.submit(c.intent, context=lambda: c.context)
    assert unknown.state == "UNKNOWN" and unknown.broker_order_id is None and unknown.reserved_cash == Decimal("202")
    refreshed = reopen(c).refresh(unknown.order_id)
    assert not refreshed.applied and refreshed.order == unknown
    assert reopen(c).submit(c.intent, context=forbidden_context) == unknown
    other = reopen(c).submit(replace(c.intent, client_order_id="later"), context=forbidden_context)
    assert other.decision.reasons == (ReasonCode.RECONCILIATION_REQUIRED,)
    assert [call[0] for call in c.wire.session.calls] == ["POST"]


@pytest.mark.parametrize("failure_at", [1, 2])
def test_commit_errors_cut_off_send_or_leave_queryable_submitting(tmp_path, monkeypatch, failure_at):
    c = setup(tmp_path, acceptance())
    commit, commits = c.store._commit, 0

    def interrupted(connection):
        nonlocal commits
        commits += 1
        if commits == failure_at:
            raise OSError("PRIVATE synthetic write failure")
        commit(connection)

    monkeypatch.setattr(c.store, "_commit", interrupted)
    with pytest.raises(LedgerUnavailable, match="virtual ledger operation failed"):
        c.orders.submit(c.intent, context=lambda: c.context)
    if failure_at == 1:
        assert c.store.orders() == () and c.wire.session.calls == []
    else:
        pending, = c.store.orders()
        assert pending.state == "SUBMITTING" and pending.reserved_cash == Decimal("202")
        assert reopen(c).submit(c.intent, context=forbidden_context) == pending
        assert not reopen(c).refresh(pending.order_id).applied
        assert [call[0] for call in c.wire.session.calls] == ["POST"]


def test_mock_fill_refresh_waits_for_last_page_is_idempotent_and_requires_settlement(tmp_path):
    partial = row(tot_ccld_qty="1", tot_ccld_amt="98", rmn_qty="1")
    final = row(tot_ccld_qty="2", tot_ccld_amt="197", rmn_qty="0")
    c = setup(
        tmp_path, acceptance(), page(continuation="M", fk="first", nk="next"), page(partial),
        page(dict(partial, tot_ccld_amt="98.00")), page(final, continuation="F", fk="next", nk="end"),
        page(), acceptance(ODNO="0000001235", ORD_TMD="120003"),
    )
    original = c.orders.submit(c.intent, context=lambda: c.context)
    c.runtime.now = NOW + timedelta(seconds=1)
    result = reopen(c).refresh(original.order_id)
    assert result.applied and result.order.state == "PARTIALLY_FILLED"
    assert result.order.reserved_cash == Decimal("102") and result.order.cumulative_notional == Decimal("98")
    assert c.wire.session.calls[2][2]["headers"]["tr_cont"] == "N"
    c.runtime.now += timedelta(seconds=1)
    revision = c.store.book().revision
    duplicate = reopen(c).refresh(original.order_id)
    assert not duplicate.applied and duplicate.order == result.order and c.store.book().revision == revision
    c.runtime.now += timedelta(seconds=1)
    finished = reopen(c).refresh(original.order_id)
    assert finished.applied and finished.order.state == "FILLED" and c.store.book().entries == ()
    receipts = reopen(c).fill_receipts()
    assert [(receipt.cumulative_qty, receipt.cumulative_notional) for receipt in receipts] == [
        (1, Decimal("98")), (2, Decimal("197")),
    ]
    assert len({receipt.event_id for receipt in receipts}) == 2
    assert not reopen(c).refresh(original.order_id).applied
    denied = c.orders.submit(replace(c.intent, client_order_id="unsettled"), context=lambda: c.context)
    assert denied.decision.reasons == (ReasonCode.SNAPSHOT_INVALID,)
    account = replace(
        c.context.account, version="after-fill", captured_at=c.runtime.now, valuation_at=c.runtime.now,
        available_cash=Decimal("801"), positions=(Position(c.intent.symbol, 2, Decimal("197"), Decimal(0)),),
        account_exposure=Decimal("197"), reservation_watermark=c.store.book().revision,
    )
    settled = replace(c.context, account=account, settled_event_ids=frozenset(receipt.event_id for receipt in receipts))
    next_order = c.orders.submit(replace(c.intent, client_order_id="settled"), context=lambda: settled)
    assert next_order.state == "ACKNOWLEDGED"
    assert [call[0] for call in c.wire.session.calls].count("POST") == 2


def test_incomplete_and_empty_lookup_leave_acknowledged_order_untouched(tmp_path):
    c = setup(tmp_path, acceptance(), page(), page(row(), continuation="M", fk="partial", nk="no-end"), TimeoutError())
    order = c.orders.submit(c.intent, context=lambda: c.context)
    revision = c.store.book().revision
    for _ in range(2):
        result = reopen(c).refresh(order.order_id)
        assert result.order == order and not result.applied
        assert c.store.book().revision == revision
    assert c.store.get(order.order_id).reserved_cash == Decimal("202")


def test_more_specific_requests_mount_cannot_enable_automatic_order_retry():
    c = client_case()
    with requests.Session() as session:
        session.trust_env = False
        client = KISMockOrderClient(**dict(c.arguments, session=session))
        session.mount(BASE + ORDER_PATH, requests.adapters.HTTPAdapter(max_retries=1))
        with pytest.raises(KISMockBoundaryError, match="UNSUPPORTED_TRANSPORT"):
            client.submit_claim(c.dispatch)


def test_acknowledgement_time_cannot_precede_this_post_invocation():
    c = client_case(acceptance(ORD_TMD="115959"))
    result = c.client.submit_claim(c.dispatch)
    assert result.status == "UNKNOWN" and result.broker_order_id is None
    assert len(c.session.calls) == 1
