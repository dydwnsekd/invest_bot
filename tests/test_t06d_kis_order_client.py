"""Offline contracts with conspicuously synthetic credentials and responses."""
from dataclasses import FrozenInstanceError, replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal, localcontext
from importlib import import_module
from types import SimpleNamespace

import pytest

from invest_bot.trading.models import Side
from invest_bot.trading.order_service import Dispatch

NOW = datetime(2026, 11, 22, 3, tzinfo=timezone.utc)
BASE = "https://openapivts.koreainvestment.com:29443"
ORDER_PATH = "/uapi/domestic-stock/v1/trading/order-cash"
QUERY_PATH = "/uapi/domestic-stock/v1/trading/inquire-daily-ccld"
BROKER_ID = "kis-mock-v1:20261122:91252:0000001234:120000"


class FakeResponse:
    def __init__(self, payload, *, status=200, continuation="E", headers=None, history=None):
        self.payload = payload
        self.status_code = status
        self.headers = {"tr_cont": continuation} if headers is None else headers
        self.history = [] if history is None else history
        self.url = ""
        self.closed = False

    def json(self):
        if isinstance(self.payload, Exception):
            raise self.payload
        return self.payload

    def close(self):
        self.closed = True


class FakeSession:
    """Explicitly trusted single-call transport; no hidden retries or I/O."""
    kis_mock_no_retries = True

    def __init__(self, *responses):
        self.responses = list(responses)
        self.calls = []

    def request(self, method, url, **kwargs):
        self.calls.append((method, url, kwargs))
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        response.url = url
        return response


def api():
    return import_module("invest_bot.clients.kis_order_client")


def case(*responses, clock=None, page_pause=None):
    module = api()
    credentials = module.KISMockCredentials(
        "12345678", "synthetic-app-key", "synthetic-app-secret", "synthetic-access-token",
        NOW + timedelta(hours=1),
    )
    session = FakeSession(*responses)
    arguments = dict(credentials=credentials, alias="paper", binding_version="binding-v1",
                     mode="mock", base_url=BASE, session=session, clock=clock or (lambda: NOW))
    if page_pause is not None:
        arguments["page_pause"] = page_pause
    client = module.KISMockOrderClient(**arguments)
    dispatch = Dispatch("claim-1", client.binding.binding_id, client.binding.version,
                        "005930", Side.BUY, 2, Decimal("100"), execution_target="kis_mock")
    return SimpleNamespace(m=module, credentials=credentials, session=session, arguments=arguments,
                           client=client, dispatch=dispatch)


def acceptance(**changes):
    output = dict(KRX_FWDG_ORD_ORGNO="91252", ODNO="0000001234", ORD_TMD="120000")
    output.update(changes)
    return FakeResponse({"rt_cd": "0", "output": output})


def row(**changes):
    result = dict(ord_dt="20261122", ord_gno_brno="91252", odno="0000001234", ord_tmd="120000",
                  ord_dvsn_cd="00", sll_buy_dvsn_cd="02", pdno="005930", ord_qty="2", ord_unpr="100",
                  tot_ccld_qty="0", tot_ccld_amt="0", cncl_yn="N", cnc_cfrm_qty="0", rmn_qty="2", rjct_qty="0")
    result.update(changes)
    return result


def page(*rows, continuation="E", fk="", nk=""):
    return FakeResponse(dict(rt_cd="0", output1=list(rows), ctx_area_fk100=fk, ctx_area_nk100=nk),
                        continuation=continuation)


def test_credentials_are_immutable_and_binding_hmac_scope_is_stable():
    c = case()
    assert not hasattr(c.credentials, "__dict__")
    with pytest.raises(FrozenInstanceError): c.credentials.access_token = "replacement"
    for value in (c.credentials.account_number, c.credentials.app_key, c.credentials.app_secret, c.credentials.access_token):
        assert value not in repr(c.credentials) + repr(c.client.binding) + repr(c.client)
    changed = dict(c.arguments, alias="another", binding_version="binding-v2",
                   credentials=replace(c.credentials, access_token="replacement", token_expires_at=NOW+timedelta(hours=2)))
    assert c.m.KISMockOrderClient(**changed).binding.binding_id == c.client.binding.binding_id
    for name, value in [("account_number", "87654321"), ("app_key", "other-key"), ("app_secret", "other-secret")]:
        changed = dict(c.arguments, credentials=replace(c.credentials, **{name: value}))
        assert c.m.KISMockOrderClient(**changed).binding.binding_id != c.client.binding.binding_id
    assert c.client.binding.execution_target == "kis_mock" and c.client.binding.mode == "mock"


@pytest.mark.parametrize("field,value", [
    ("mode", "live"), ("mode", None), ("base_url", BASE+"/"), ("base_url", BASE+".evil"),
    ("base_url", "https://openapi.koreainvestment.com:9443"), ("base_url", None),
    ("alias", "bad alias"), ("binding_version", ""), ("session", None), ("clock", None),
])
def test_bad_configuration_is_rejected_without_io(field, value):
    c = case()
    with pytest.raises(c.m.KISMockBoundaryError): c.m.KISMockOrderClient(**dict(c.arguments, **{field: value}))
    assert c.session.calls == []


@pytest.mark.parametrize("field,value", [
    ("account_number", "1234567"), ("account_number", 12345678), ("app_key", ""),
    ("app_secret", "bad\nsecret"), ("access_token", "has space"),
    ("token_expires_at", NOW), ("token_expires_at", NOW.replace(tzinfo=None)),
])
def test_invalid_credentials_are_not_accepted_or_echoed(field, value):
    c = case()
    with pytest.raises(c.m.KISMockBoundaryError) as error:
        c.m.KISMockOrderClient(**dict(c.arguments, credentials=replace(c.credentials, **{field: value})))
    assert "secret" not in str(error.value) and c.session.calls == []


@pytest.mark.parametrize("side,tr_id,sell_type", [(Side.BUY, "VTTC0012U", ""), (Side.SELL, "VTTC0011U", "01")])
def test_submit_has_one_exact_mock_limit_order_request_and_acceptance_only(side, tr_id, sell_type):
    response = acceptance()
    c = case(response)
    result = c.client.submit_claim(replace(c.dispatch, side=side, limit_price=Decimal("100.00")))
    assert result.status == "ACKNOWLEDGED" and result.confirmed and result.broker_order_id == BROKER_ID
    assert result.order_id == c.dispatch.order_id and result.account_binding_id == c.client.binding.binding_id
    assert len(c.session.calls) == 1 and response.closed
    method, url, options = c.session.calls[0]
    assert (method, url) == ("POST", BASE+ORDER_PATH)
    assert options["json"] == dict(CANO="12345678", ACNT_PRDT_CD="01", PDNO="005930", ORD_DVSN="00",
                                   ORD_QTY="2", ORD_UNPR="100", EXCG_ID_DVSN_CD="KRX", SLL_TYPE=sell_type, CNDT_PRIC="")
    assert all(type(value) is str for value in options["json"].values())
    assert options["headers"]["tr_id"] == tr_id and options["headers"]["authorization"] == "Bearer synthetic-access-token"
    assert options["allow_redirects"] is False and options["verify"] is True and options["timeout"] == (3.05, 10.0)
    assert not any("hash" in key.lower() for key in options["headers"])


@pytest.mark.parametrize("field,value", [
    ("execution_target", "dry_run"), ("execution_target", "live"), ("mode", "live"), ("currency", "USD"),
    ("order_id", "bad id"), ("account_binding_id", "other"), ("binding_version", "other"),
    ("symbol", "A005930"), ("side", "BUY"), ("qty", True), ("qty", 0),
    ("limit_price", Decimal("0")), ("limit_price", Decimal("1.5")), ("limit_price", 100.0),
])
def test_invalid_dispatch_is_locally_blocked(field, value):
    c = case()
    with pytest.raises(c.m.KISMockBoundaryError): c.client.submit_claim(replace(c.dispatch, **{field: value}))
    assert c.session.calls == []


@pytest.mark.parametrize("fault", ["timeout", "http", "redirect", "json", "nonzero", "missing", "bad-time", "day-rollover"])
def test_ambiguous_submission_is_unknown_and_never_retried(fault):
    response = acceptance()
    times = [NOW]
    if fault == "timeout": response = TimeoutError("PRIVATE raw token or KIS detail")
    elif fault == "http": response.status_code = 500
    elif fault == "redirect": response.status_code = 302
    elif fault == "json": response.payload = ValueError("PRIVATE JSON")
    elif fault == "nonzero": response.payload.update(rt_cd="1", msg1="PRIVATE rejection detail")
    elif fault == "missing": response.payload["output"].pop("ODNO")
    elif fault == "bad-time": response.payload["output"]["ORD_TMD"] = "250000"
    else: times = [NOW, NOW, NOW, NOW+timedelta(days=1)]
    c = case(response, clock=lambda: times.pop(0) if len(times)>1 else times[0])
    result = c.client.submit_claim(c.dispatch)
    assert result.status == "UNKNOWN" and not result.confirmed and result.broker_order_id is None
    assert len(c.session.calls) == 1 and "PRIVATE" not in repr(result)


@pytest.mark.parametrize("kind,changes,qty,notional", [
    ("ACKNOWLEDGED", {}, 0, "0"),
    ("PARTIALLY_FILLED", dict(tot_ccld_qty="1", tot_ccld_amt="99", rmn_qty="1"), 1, "99"),
    ("FILLED", dict(tot_ccld_qty="2", tot_ccld_amt="198", rmn_qty="0"), 2, "198"),
    ("BROKER_REJECTED", dict(rmn_qty="0", rjct_qty="2"), 0, "0"),
    ("CANCELLED", dict(cncl_yn="Y", cnc_cfrm_qty="2", rmn_qty="0"), 0, "0"),
    ("CANCELLED", dict(cncl_yn="Y", cnc_cfrm_qty="1", rmn_qty="0", tot_ccld_qty="1", tot_ccld_amt="99"), 1, "99"),
])
def test_lookup_requires_exact_known_order_and_complete_consistent_row(kind, changes, qty, notional):
    c = case(page(row(**changes)))
    with localcontext() as context:
        context.prec = 2
        result = c.client.lookup(c.dispatch, BROKER_ID)
    assert result.kind == kind and result.cumulative_qty == qty and result.cumulative_notional == Decimal(notional)
    assert result.broker_order_id == BROKER_ID and result.observed_at == NOW
    method, url, options = c.session.calls[0]
    assert (method, url) == ("GET", BASE+QUERY_PATH)
    assert options["headers"]["tr_id"] == "VTTC0081R" and options["headers"]["tr_cont"] == ""
    assert options["params"] == dict(CANO="12345678", ACNT_PRDT_CD="01", INQR_STRT_DT="20261122", INQR_END_DT="20261122",
                                    SLL_BUY_DVSN_CD="02", PDNO="005930", CCLD_DVSN="00", INQR_DVSN="00", INQR_DVSN_3="01",
                                    ORD_GNO_BRNO="91252", ODNO="0000001234", INQR_DVSN_1="", CTX_AREA_FK100="", CTX_AREA_NK100="", EXCG_ID_DVSN_CD="KRX")


@pytest.mark.parametrize("field,value", [
    ("ord_dt", "20261121"), ("ord_gno_brno", "other"), ("odno", "other"), ("ord_tmd", "120001"),
    ("pdno", "000660"), ("sll_buy_dvsn_cd", "01"), ("ord_dvsn_cd", "01"), ("ord_qty", "3"), ("ord_unpr", "101"),
    ("tot_ccld_qty", "3"), ("tot_ccld_amt", "1"), ("cncl_yn", "?"), ("cnc_cfrm_qty", "1"), ("rjct_qty", "1"),
    ("rmn_qty", "1"), ("ord_qty", 2),
])
def test_mixed_or_inconsistent_query_row_is_unknown(field, value):
    c = case(page(row(**{field: value})))
    assert c.client.lookup(c.dispatch, BROKER_ID) is None and len(c.session.calls) == 1


@pytest.mark.parametrize("broker_id", [None, "", "0000001234", "kis-mock-v1:20261123:91252:0000001234:120000", "kis-mock-v1:20260821:91252:0000001234:120000"])
def test_lookup_without_exact_recent_persisted_identity_does_not_search(broker_id):
    c = case()
    assert c.client.lookup(c.dispatch, broker_id) is None and c.session.calls == []


def test_zero_rows_or_duplicate_or_conflicting_rows_never_release():
    for rows in [[], [row(), row()], [row(), row(tot_ccld_qty="1", tot_ccld_amt="99", rmn_qty="1")]]:
        c = case(page(*rows))
        assert c.client.lookup(c.dispatch, BROKER_ID) is None


@pytest.mark.parametrize("fault", ["missing-cursor", "repeat-cursor", "missing-page", "mixed-page", "bad-final"])
def test_continuation_does_not_return_an_early_row(fault):
    first = page(row(), continuation="M", fk="cursor-1", nk="next-1")
    second = page(row(), continuation="E")
    if fault == "missing-cursor": first.payload.pop("ctx_area_nk100")
    elif fault == "repeat-cursor": second = page(row(), continuation="F", fk="cursor-1", nk="next-1")
    elif fault == "missing-page": second = TimeoutError("PRIVATE query failure")
    elif fault == "mixed-page": second = page(row(pdno="000660"))
    else: second.headers["tr_cont"] = "unexpected"
    pauses = []
    c = case(first, second, page_pause=lambda: pauses.append(1))
    assert c.client.lookup(c.dispatch, BROKER_ID) is None
    assert len(c.session.calls) == (1 if fault == "missing-cursor" else 2)
    if len(c.session.calls) == 2:
        options = c.session.calls[1][2]
        assert options["headers"]["tr_cont"] == "N"
        assert options["params"]["CTX_AREA_FK100"] == "cursor-1" and options["params"]["CTX_AREA_NK100"] == "next-1"
        assert pauses == [1]


def test_tokens_and_transport_attestation_are_rechecked_at_dispatch():
    now = [NOW]
    c = case(acceptance(), clock=lambda: now[0])
    now[0] = c.credentials.token_expires_at
    with pytest.raises(c.m.KISMockBoundaryError): c.client.submit_claim(c.dispatch)
    assert c.session.calls == []
    now[0] = NOW
    c.session.kis_mock_no_retries = False
    with pytest.raises(c.m.KISMockBoundaryError): c.client.submit_claim(c.dispatch)
    assert c.session.calls == []


def test_token_expiring_during_last_transport_check_still_prevents_http():
    c = case()
    now = [NOW]
    class Transport(FakeSession):
        checks = 0
        @property
        def kis_mock_no_retries(self):
            self.checks += 1
            if self.checks == 3:
                now[0] = c.credentials.token_expires_at
            return True
    session = Transport(acceptance())
    client = c.m.KISMockOrderClient(**dict(c.arguments, session=session, clock=lambda: now[0]))
    result = client.submit_claim(c.dispatch)
    assert result.status == "UNKNOWN" and session.calls == []


@pytest.mark.parametrize("fault", ["environment", "retry", "proxy", "auth", "cookie", "hook", "params", "tls", "host", "custom-method", "custom-adapter"])
def test_standard_requests_transport_rejects_implicit_behavior(fault):
    import requests
    c = case()
    with requests.Session() as session:
        session.trust_env = False
        if fault == "environment": session.trust_env = True
        elif fault == "retry": session.mount("https://", requests.adapters.HTTPAdapter(max_retries=1))
        elif fault == "proxy": session.proxies["https"] = "http://invalid.test"
        elif fault == "auth": session.auth = ("synthetic-user", "synthetic-secret")
        elif fault == "cookie": session.cookies.set("unsafe", "synthetic")
        elif fault == "hook": session.hooks["response"].append(lambda response: response)
        elif fault == "params": session.params["CANO"] = "87654321"
        elif fault == "tls": session.verify = False
        elif fault == "host": session.headers["Host"] = "other.test"
        elif fault == "custom-method": session.request = lambda *args, **kwargs: pytest.fail("custom transport invoked")
        else:
            class CustomAdapter(requests.adapters.HTTPAdapter):
                pass
            session.mount("https://", CustomAdapter())
        with pytest.raises(c.m.KISMockBoundaryError):
            c.m.KISMockOrderClient(**dict(c.arguments, session=session))


def test_standard_requests_transport_can_be_validated_without_creating_or_sending_it():
    import requests
    c = case()
    with requests.Session() as session:
        session.trust_env = False
        client = c.m.KISMockOrderClient(**dict(c.arguments, session=session))
        assert client.binding == c.client.binding


@pytest.mark.parametrize("continuation", ["", "D", "E"])
def test_only_explicit_completion_headers_can_finish_a_query(continuation):
    c = case(page(row(), continuation=continuation))
    assert c.client.lookup(c.dispatch, BROKER_ID).kind == "ACKNOWLEDGED"


@pytest.mark.parametrize("headers", [{}, {"tr_cont": None}, {"tr_cont": "e"}, {"tr_cont": " E"}, {"tr_cont": "E", "TR_CONT": "D"}])
def test_missing_malformed_or_ambiguous_completion_header_is_not_a_last_page(headers):
    response = page(row()); response.headers = headers
    c = case(response)
    assert c.client.lookup(c.dispatch, BROKER_ID) is None


def test_header_names_are_case_insensitive_but_response_fields_are_not():
    response = page(row()); response.headers = {"Tr_Cont": "E"}
    c = case(response)
    assert c.client.lookup(c.dispatch, BROKER_ID).kind == "ACKNOWLEDGED"
    response = acceptance(); response.payload["output"]["odno"] = response.payload["output"].pop("ODNO")
    c = case(response)
    assert c.client.submit_claim(c.dispatch).status == "UNKNOWN"


def test_pagination_is_finite_even_when_transport_keeps_returning_new_cursors():
    c = case(*(page(row(), continuation="M", fk=f"cursor-{number}", nk="next") for number in range(api().MAX_PAGES)))
    assert c.client.lookup(c.dispatch, BROKER_ID) is None
    assert len(c.session.calls) == c.m.MAX_PAGES


@pytest.mark.parametrize("fault", ["token-expired", "pause-error"])
def test_between_page_pause_cannot_trigger_an_unchecked_second_request(fault):
    now = [NOW]
    def pause():
        if fault == "pause-error": raise RuntimeError("PRIVATE callback failure")
        now[0] += timedelta(hours=2)
    c = case(page(row(), continuation="M", fk="cursor", nk="next"), page(row()),
             clock=lambda: now[0], page_pause=pause)
    assert c.client.lookup(c.dispatch, BROKER_ID) is None and len(c.session.calls) == 1


@pytest.mark.parametrize("changes", [
    dict(tot_ccld_qty="1", tot_ccld_amt="101", rmn_qty="1"),
    dict(tot_ccld_qty="1", tot_ccld_amt="99.5", rmn_qty="1"),
    dict(tot_ccld_qty="1", tot_ccld_amt="0", rmn_qty="1"),
    dict(tot_ccld_qty="1", tot_ccld_amt="99", rmn_qty="0", rjct_qty="1"),
    dict(cncl_yn="Y", cnc_cfrm_qty="1", rmn_qty="1"),
])
def test_partial_or_inconsistent_terminal_evidence_cannot_release(changes):
    c = case(page(row(**changes)))
    assert c.client.lookup(c.dispatch, BROKER_ID) is None


def test_sell_fill_uses_actual_notional_and_minimum_limit_price():
    valid = row(sll_buy_dvsn_cd="01", tot_ccld_qty="1", tot_ccld_amt="101.00", rmn_qty="1")
    c = case(page(valid))
    dispatch = replace(c.dispatch, side=Side.SELL)
    result = c.client.lookup(dispatch, BROKER_ID)
    assert result.kind == "PARTIALLY_FILLED" and result.cumulative_notional == Decimal("101.00")
    assert c.session.calls[0][2]["params"]["SLL_BUY_DVSN_CD"] == "01"
    c.session.responses.append(page(row(**dict(valid, tot_ccld_amt="99"))))
    assert c.client.lookup(dispatch, BROKER_ID) is None


def test_unexpected_sensitive_response_fields_are_not_retained():
    response = acceptance(PRIVATE_FIELD="PRIVATE-RESPONSE-SECRET")
    c = case(response, page(row(PRIVATE_FIELD="PRIVATE-RESPONSE-SECRET")))
    reply = c.client.submit_claim(c.dispatch)
    observation = c.client.lookup(c.dispatch, reply.broker_order_id)
    for value in (reply, observation, c.client.binding, c.client):
        assert "PRIVATE-RESPONSE-SECRET" not in repr(value)
        assert c.credentials.account_number not in repr(value)
        assert c.credentials.access_token not in repr(value)
    assert not hasattr(c.client, "__dict__") and not hasattr(observation, "__dict__")


def test_kst_day_change_is_ambiguous_even_when_utc_date_did_not_change():
    before = NOW - timedelta(hours=12, seconds=1)
    after = before + timedelta(seconds=1)
    times = [before, before, before, after]
    c = case(acceptance(ORD_TMD="235959"), clock=lambda: times.pop(0))
    assert c.client.submit_claim(c.dispatch).status == "UNKNOWN" and len(c.session.calls) == 1


def test_exact_three_calendar_month_boundary_uses_only_recent_mock_query_tr():
    broker_id = BROKER_ID.replace("20261122", "20260822")
    c = case(page(row(ord_dt="20260822")))
    assert c.client.lookup(c.dispatch, broker_id).kind == "ACKNOWLEDGED"
    assert c.session.calls[0][2]["params"]["INQR_STRT_DT"] == "20260822"
    assert c.session.calls[0][2]["headers"]["tr_id"] == "VTTC0081R"


@pytest.mark.parametrize("fault", ["timeout", "http", "rt-code", "json", "oversized-page", "empty-page", "missing-output"])
def test_failed_or_incomplete_query_never_synthesizes_rejection(fault):
    response = page(row())
    if fault == "timeout": response = TimeoutError("PRIVATE network detail")
    elif fault == "http": response.status_code = 503
    elif fault == "rt-code": response.payload.update(rt_cd="1", msg1="PRIVATE KIS detail")
    elif fault == "json": response.payload = ValueError("PRIVATE JSON")
    elif fault == "oversized-page": response.payload["output1"] = [row() for _ in range(16)]
    elif fault == "empty-page": response.payload["output1"] = []
    else: response.payload.pop("output1")
    c = case(response)
    assert c.client.lookup(c.dispatch, BROKER_ID) is None and len(c.session.calls) == 1


@pytest.mark.parametrize("fault", ["history", "response-url", "future-order-time", "backwards-clock"])
def test_response_identity_and_clock_ambiguity_do_not_acknowledge(fault):
    response = acceptance()
    if fault == "history": response.history = [object()]
    elif fault == "future-order-time": response.payload["output"]["ORD_TMD"] = "120001"
    times = [NOW, NOW, NOW, NOW-timedelta(seconds=1)] if fault == "backwards-clock" else [NOW]*4
    c = case(response, clock=lambda: times.pop(0))
    if fault == "response-url":
        class RedirectingTransport(FakeSession):
            def request(self, *args, **kwargs):
                result = super().request(*args, **kwargs)
                result.url = "https://other.test" + ORDER_PATH
                return result
        c = case()
        session = RedirectingTransport(response)
        c.client = c.m.KISMockOrderClient(**dict(c.arguments, session=session))
        c.session = session
    assert c.client.submit_claim(c.dispatch).status == "UNKNOWN" and len(c.session.calls) == 1


def test_client_does_not_create_sessions_or_authenticate_or_read_configuration(monkeypatch):
    from pathlib import Path
    import builtins
    import requests
    from invest_bot.clients.kis_client import KISClient
    from invest_bot.config.settings import AppSettings
    c = case(acceptance(), page(row()))
    def forbidden(*args, **kwargs): pytest.fail("implicit I/O/authentication/session construction")
    monkeypatch.setattr(requests.Session, "__init__", forbidden)
    monkeypatch.setattr(KISClient, "authenticate", forbidden)
    monkeypatch.setattr(AppSettings, "from_file", forbidden)
    monkeypatch.setattr(builtins, "open", forbidden)
    monkeypatch.setattr(Path, "open", forbidden)
    client = c.m.KISMockOrderClient(**c.arguments)
    reply = client.submit_claim(c.dispatch)
    assert reply.status == "ACKNOWLEDGED"
    assert client.lookup(c.dispatch, reply.broker_order_id).kind == "ACKNOWLEDGED"
