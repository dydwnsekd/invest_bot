"""Eight independent offline mock-transport/real-ledger integration cases."""
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal
import json
import sqlite3
import threading
from types import SimpleNamespace
from urllib.parse import quote

import pytest
import requests

from invest_bot import AppSettings
from invest_bot.clients.kis_client import KISClient
from invest_bot.clients.kis_order_client import KISMockBoundaryError, KISMockCredentials, KISMockOrderClient
from invest_bot.trading.kis_mock_orders import KISMockOrders
from invest_bot.trading.models import AccountSnapshot, MarketSnapshot, OrderIntent, Position, RiskPolicy, Side
from invest_bot.trading.order_service import Dispatch, EvidenceRejected, ValidationContext
from invest_bot.trading.order_store import LedgerUnavailable, OrderStore

D = Decimal
NOW = datetime(2026, 11, 22, 4, 45, 30, tzinfo=UTC)
BASE = "https://openapivts.koreainvestment.com:29443"
ORDER = "/uapi/domestic-stock/v1/trading/order-cash"
QUERY = "/uapi/domestic-stock/v1/trading/inquire-daily-ccld"


@pytest.fixture(autouse=True)
def no_configuration_authentication_or_token_cache(monkeypatch):
    attempts = []
    def denied(*args, **kwargs):
        attempts.append("configuration/authentication/cache")
        raise AssertionError("forbidden runtime operation")
    monkeypatch.setattr(AppSettings, "from_file", denied)
    for name in ("authenticate", "_load_cached_token", "_save_cached_token"):
        monkeypatch.setattr(KISClient, name, denied)
    yield
    assert attempts == []


class Reply:
    def __init__(self, payload, continuation="E", status=200):
        self.payload, self.status_code = payload, status
        self.headers, self.history, self.url, self.closed = {"tr_cont": continuation}, [], "", False

    def json(self):
        return self.payload

    def close(self):
        self.closed = True


class Wire:
    kis_mock_no_retries = True

    def __init__(self, *responses):
        self.responses, self.calls, self.handler = list(responses), [], None
        self.lock = threading.Lock()

    def request(self, method, url, **kwargs):
        assert url == BASE + (ORDER if method == "POST" else QUERY)
        with self.lock:
            self.calls.append((method, url, kwargs))
            response = None if self.handler else self.responses.pop(0)
        response = self.handler(method, url, **kwargs) if self.handler else response
        if isinstance(response, Exception):
            raise response
        response.url = url
        return response


def acknowledgement():
    return Reply({"rt_cd": "0", "output": {"KRX_FWDG_ORD_ORGNO": "54321", "ODNO": "0000008642", "ORD_TMD": "134530"}})


def execution_row(**changes):
    row = dict(ord_dt="20261122", ord_gno_brno="54321", odno="0000008642", ord_tmd="134530",
               ord_dvsn_cd="00", sll_buy_dvsn_cd="02", pdno="444444", ord_qty="4", ord_unpr="125",
               tot_ccld_qty="2", tot_ccld_amt="248", cncl_yn="N", cnc_cfrm_qty="0", rmn_qty="2", rjct_qty="0")
    row.update(changes)
    return row


def page(*rows, continuation="E", cursor=""):
    return Reply(dict(rt_cd="0", output1=list(rows), ctx_area_fk100=cursor, ctx_area_nk100=cursor), continuation)


def setup_case(tmp_path, *responses):
    runtime = SimpleNamespace(now=NOW, killed=False)
    wire = Wire(*responses)
    credentials = KISMockCredentials("87654321", "qa-inert-app-key", "qa-inert-app-secret", "qa-inert-access-token", NOW+timedelta(hours=1))
    client_args = dict(credentials=credentials, alias="qa-paper", binding_version="qa-binding-4", mode="mock",
                       base_url=BASE, session=wire, clock=lambda: runtime.now)
    client = KISMockOrderClient(**client_args)
    binding = client.binding
    intent = OrderIntent(1, "qa-order", "kis_mock", "mock", binding.alias, binding.binding_id, binding.version,
                         "444444", Side.BUY, 4, D("125"), "KRW", "domestic_stock", "LIMIT", "qa-origin",
                         NOW-timedelta(seconds=1), NOW+timedelta(seconds=10))
    policy = RiskPolicy("qa-policy", "kis_mock", "mock", frozenset({"444444"}), frozenset({"domestic_stock"}),
                        frozenset({"qa-session"}), D("1000"), D("1500"), D("2000"), D("20"), 8,
                        D(".007"), D(".005"), D(".2"), D(".1"), D("1"),
                        timedelta(seconds=30), timedelta(seconds=30), timedelta(seconds=30),
                        timedelta(seconds=3), timedelta(seconds=30))
    account = AccountSnapshot("qa-capture", "kis_mock", "mock", binding.alias, binding.binding_id, binding.version,
                              "KRW", NOW, True, True, D("900"), (), D("0"), 0, NOW, "qa-mark", "qa-book", 0, frozenset())
    market = MarketSnapshot("qa-market", "kis_mock", "mock", "444444", "domestic_stock", "KRW", NOW,
                            True, True, "qa-session", "qa-calendar", "qa-calendar-1", D("1"), D("1"), D("1000"))
    context = ValidationContext(binding, policy, account, market, frozenset())
    path = tmp_path / "qa-mock.sqlite"
    store = OrderStore.bootstrap(path, book_id="qa-book", bindings=(binding,), execution_target="kis_mock")
    orders = KISMockOrders(store, client, clock=lambda: runtime.now, kill_switch=lambda: runtime.killed)
    return SimpleNamespace(runtime=runtime, wire=wire, credentials=credentials, client=client, args=client_args,
                           intent=intent, context=context, store=store, orders=orders, path=path)


def reopen(c):
    return KISMockOrders(OrderStore.open(c.path, execution_target="kis_mock"), c.client,
                         clock=lambda: c.runtime.now, kill_switch=lambda: c.runtime.killed)


def database_state(path):
    with sqlite3.connect("file:"+quote(str(path), safe="/")+"?mode=ro", uri=True) as connection:
        return tuple(connection.iterdump())


def never():
    raise AssertionError("unexpected context lookup")


def test_mock_configuration_token_transport_account_and_target_fail_before_io(tmp_path):
    c = setup_case(tmp_path)
    for field, value in (("mode", "live"), ("base_url", BASE+"/"), ("base_url", "https://openapi.koreainvestment.com:9443"),
                         ("credentials", replace(c.credentials, token_expires_at=NOW))):
        with pytest.raises(KISMockBoundaryError):
            KISMockOrderClient(**dict(c.args, **{field: value}))
    other = KISMockOrderClient(**dict(c.args, credentials=replace(c.credentials, account_number="87654320")))
    with pytest.raises(KISMockBoundaryError):
        KISMockOrders(c.store, other, clock=lambda: NOW, kill_switch=lambda: False)
    with pytest.raises(LedgerUnavailable):
        OrderStore.open(c.path)  # A mock ledger cannot be silently opened as dry_run.
    dispatch = Dispatch("qa-dispatch", c.client.binding.binding_id, c.client.binding.version, "444444", Side.BUY, 4, D("125"), execution_target="kis_mock")
    c.runtime.now = c.credentials.token_expires_at
    with pytest.raises(KISMockBoundaryError):
        c.client.submit_claim(dispatch)
    c.runtime.now = NOW
    c.wire.kis_mock_no_retries = False
    with pytest.raises(KISMockBoundaryError):
        c.client.submit_claim(dispatch)
    c.wire.kis_mock_no_retries = True
    with requests.Session() as session:
        session.trust_env = False
        native = KISMockOrderClient(**dict(c.args, session=session))
        session.mount(BASE+ORDER, requests.adapters.HTTPAdapter(max_retries=1))
        with pytest.raises(KISMockBoundaryError):
            native.submit_claim(dispatch)
    assert c.wire.calls == [] and c.store.orders() == ()


def test_absent_post_response_keeps_durable_claim_and_never_reposts_or_guesses_reference(tmp_path):
    for fault in ("no-response", "old-ack", "http-error"):
        folder = tmp_path / fault
        folder.mkdir()
        c = setup_case(folder)
        response = acknowledgement()
        if fault == "old-ack":
            response.payload["output"]["ORD_TMD"] = "134529"
        elif fault == "http-error":
            response.status_code = 503
        def uncertain(method, url, **kwargs):
            assert method == "POST" and kwargs["headers"]["tr_id"] == "VTTC0012U"
            independent = OrderStore.open(c.path, execution_target="kis_mock")
            pending, = independent.orders()
            assert pending.state == "SUBMITTING" and pending.reserved_cash == D("504")
            assert independent.book().entries[0].cash == D("504")
            return TimeoutError("qa-private-transport-detail") if fault == "no-response" else response
        c.wire.handler = uncertain
        first = c.orders.submit(c.intent, context=lambda: c.context)
        assert first.state == "UNKNOWN" and first.broker_order_id is None and first.reserved_cash == D("504")
        if fault != "no-response":
            assert response.closed
        restored = reopen(c)
        assert restored.submit(c.intent, context=never) == first
        consultations = []
        def valid_context():
            consultations.append(1)
            return c.context
        denied = restored.submit(replace(c.intent, client_order_id="qa-next", qty=1), context=valid_context)
        assert denied.decision.reasons[0].value == "RECONCILIATION_REQUIRED" and consultations == []
        assert not restored.refresh(first.order_id).applied
        assert len(c.wire.calls) == 1 and len(c.store.book().entries) == 1
        raw = c.path.read_bytes()
        assert b"qa-private-transport-detail" not in raw
        for secret in (c.credentials.app_key, c.credentials.app_secret, c.credentials.access_token):
            assert secret.encode() not in raw and secret not in repr(first)


@pytest.mark.parametrize("boundary", ["kill", "expiry", "market-stale"])
def test_after_durable_commit_local_stop_has_zero_http_and_distinct_release_audit(tmp_path, monkeypatch, boundary):
    c = setup_case(tmp_path)
    real = c.store._commit
    commits = []
    def after_commit(connection):
        real(connection)
        commits.append(1)
        if len(commits) == 1:
            if boundary == "kill":
                c.runtime.killed = True
            else:
                c.runtime.now = c.intent.expires_at if boundary == "expiry" else NOW+timedelta(seconds=4)
    monkeypatch.setattr(c.store, "_commit", after_commit)
    result = c.orders.submit(c.intent, context=lambda: c.context)
    assert result.state == "NOT_ACCEPTED" and result.reserved_cash == 0 and c.store.book().entries == ()
    assert c.wire.calls == []
    with sqlite3.connect(c.path) as connection:
        assert connection.execute("SELECT action FROM audits ORDER BY revision").fetchall() == [("CLAIM",), ("SEND_SKIPPED",)]
    assert reopen(c).submit(c.intent, context=never) == result


def test_only_complete_unique_matching_query_can_change_reservations(tmp_path):
    c = setup_case(tmp_path, acknowledgement())
    first = c.orders.submit(c.intent, context=lambda: c.context)
    assert first.state == "ACKNOWLEDGED" and first.cumulative_qty == 0 and first.reserved_cash == D("504")
    responses = [page(continuation="M", cursor="qa-one"), page(execution_row(), continuation="F", cursor="qa-two"), page()]
    completed_pages = tuple(responses)
    page_count = []
    def delayed_evidence(method, url, **kwargs):
        assert method == "GET" and url == BASE+QUERY
        assert kwargs["params"]["ODNO"] == "0000008642"
        assert c.store.get(first.order_id) == first  # No early-page application.
        page_count.append(kwargs["headers"]["tr_cont"])
        return responses.pop(0)
    c.wire.handler = delayed_evidence
    partial = c.orders.refresh(first.order_id)
    assert partial.applied and partial.order.cumulative_qty == 2 and partial.order.reserved_cash == D("254")
    assert partial.order.cumulative_notional == D("248") and page_count == ["", "N", "N"]
    assert all(response.closed for response in completed_pages)
    c.wire.handler = None
    before = database_state(c.path)
    for responses in ([page()], [page(execution_row(), execution_row())],
                      [page(execution_row(odno="0000008643"))],
                      [page(continuation="M", cursor="qa-incomplete"), TimeoutError("qa-query-timeout")],
                      [page(execution_row(cncl_yn="Y", cnc_cfrm_qty="1", rmn_qty="1"))]):
        c.wire.responses.extend(responses)
        observed = c.orders.refresh(first.order_id)
        assert not observed.applied and observed.order == partial.order
        assert database_state(c.path) == before
    c.wire.responses.append(page(execution_row(cncl_yn="Y", cnc_cfrm_qty="2", rmn_qty="0")))
    cancelled = c.orders.refresh(first.order_id)
    assert cancelled.applied and cancelled.order.state == "CANCELLED"
    assert (cancelled.order.cumulative_qty, cancelled.order.cumulative_notional, cancelled.order.reserved_cash) == (2, D("248"), 0)
    assert c.store.book().entries == () and len(c.orders.fill_receipts()) == 1
    assert sum(method == "POST" for method, _, _ in c.wire.calls) == 1


def test_overlapping_get_cannot_regress_fill_or_duplicate_settlement_receipts(tmp_path):
    c = setup_case(tmp_path, acknowledgement())
    first = c.orders.submit(c.intent, context=lambda: c.context)
    entered, release = threading.Event(), threading.Event()
    results, failures = [], []
    def racing(method, url, **kwargs):
        assert method == "GET"
        if threading.current_thread().name == "qa-slow-get":
            entered.set()
            assert release.wait(5)
            return page(execution_row(tot_ccld_qty="1", tot_ccld_amt="124", rmn_qty="3"))
        return page(execution_row())
    c.wire.handler = racing
    def slow_get():
        try:
            results.append(reopen(c).refresh(first.order_id))
        except EvidenceRejected as error:
            results.append(str(error))
        except BaseException as error:
            failures.append(error)
    slow = threading.Thread(target=slow_get, name="qa-slow-get")
    slow.start()
    try:
        assert entered.wait(5)
        fast = reopen(c).refresh(first.order_id)
        assert fast.applied and fast.order.cumulative_qty == 2
        after_fast = database_state(c.path)
    finally:
        release.set()
        slow.join(5)
    assert not slow.is_alive() and not failures and len(results) == 1
    if isinstance(results[0], str):
        assert results[0] in {"EVENT_ORDER_INVALID", "EVENT_CONFLICT"}
    else:
        assert not results[0].applied
    assert database_state(c.path) == after_fast and c.store.get(first.order_id).cumulative_qty == 2
    receipts = c.orders.fill_receipts()
    assert len(receipts) == 1 and receipts[0].cumulative_notional == D("248")
    c.wire.handler = None
    c.wire.responses.extend([page(execution_row(tot_ccld_amt="248.00")),
                             page(execution_row(tot_ccld_qty="4", tot_ccld_amt="496", rmn_qty="0"))])
    assert not c.orders.refresh(first.order_id).applied
    assert c.orders.fill_receipts() == receipts and database_state(c.path) == after_fast
    full = c.orders.refresh(first.order_id)
    assert full.applied and full.order.state == "FILLED" and full.order.reserved_cash == 0
    restored = reopen(c)
    receipts = restored.fill_receipts()
    assert len(receipts) == 2 and receipts[-1].cumulative_qty == 4
    c.runtime.now = NOW+timedelta(seconds=2)
    stale = replace(c.context.account, version="qa-renamed", captured_at=NOW+timedelta(seconds=2), reservation_watermark=c.store.book().revision)
    blocked = restored.submit(replace(c.intent, client_order_id="qa-missing-settlement"), context=lambda: replace(c.context, account=stale))
    assert blocked.decision.reasons[0].value == "SNAPSHOT_INVALID"
    settled = replace(stale, version="qa-settled", available_cash=D("400"),
                      positions=(Position("444444", 4, D("500"), D("0")),), account_exposure=D("500"),
                      reservation_watermark=c.store.book().revision)
    limited = restored.submit(replace(c.intent, client_order_id="qa-reuse-old-cash"),
                              context=lambda: replace(c.context, account=settled, settled_event_ids=frozenset(r.event_id for r in receipts)))
    assert limited.decision.reasons[0].value == "INSUFFICIENT_CASH"
    assert restored.fill_receipts() == receipts and sum(method == "POST" for method, _, _ in c.wire.calls) == 1


def test_claim_and_response_storage_failures_keep_one_shot_http_boundary(tmp_path, monkeypatch):
    for phase, fail_at in (("claim", 1), ("response", 2)):
        folder = tmp_path / phase
        folder.mkdir()
        c = setup_case(folder, acknowledgement())
        real, commits = c.store._commit, []
        def interrupted(connection):
            commits.append(1)
            if len(commits) == fail_at:
                raise RuntimeError("qa-private-storage-detail")
            real(connection)
        with monkeypatch.context() as patch:
            patch.setattr(c.store, "_commit", interrupted)
            with pytest.raises(LedgerUnavailable) as error:
                c.orders.submit(c.intent, context=lambda: c.context)
        assert "qa-private-storage-detail" not in str(error.value)
        restored_store = OrderStore.open(c.path, execution_target="kis_mock")
        if phase == "claim":
            assert c.wire.calls == [] and restored_store.orders() == ()
        else:
            pending, = restored_store.orders()
            assert pending.state == "SUBMITTING" and pending.broker_order_id is None and pending.reserved_cash == D("504")
            restored = reopen(c)
            assert restored.submit(c.intent, context=never) == pending
            denied = restored.submit(replace(c.intent, client_order_id="qa-storage-new"), context=lambda: c.context)
            assert denied.decision.reasons[0].value == "RECONCILIATION_REQUIRED"
            assert not restored.refresh(pending.order_id).applied
            assert len(c.wire.calls) == 1 and c.wire.calls[0][0] == "POST"
