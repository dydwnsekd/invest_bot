from datetime import datetime, timedelta, timezone
from importlib import import_module

import pytest

from tests.test_t06d_kis_order_client import BASE, FakeResponse, FakeSession, NOW, case


BALANCE_URL = BASE + "/uapi/domestic-stock/v1/trading/inquire-balance"
HISTORY_URL = BASE + "/uapi/domestic-stock/v1/trading/inquire-daily-ccld"
ENV_VALUES = {
    "INVEST_BOT_KIS_MOCK_ACCOUNT_NUMBER": "08765432",
    "INVEST_BOT_KIS_MOCK_APP_KEY": "check-test-app-key",
    "INVEST_BOT_KIS_MOCK_APP_SECRET": "check-test-app-secret",
    "INVEST_BOT_KIS_MOCK_ACCESS_TOKEN": "check-test-access-token",
    "INVEST_BOT_KIS_MOCK_TOKEN_EXPIRES_AT": "2099-01-01T00:00:00+09:00",
}


def balance(**overrides):
    payload = {"rt_cd": "0", "output1": [], "output2": [{"dnca_tot_amt": "321456"}]}
    payload.update(overrides)
    return FakeResponse(payload)


def history(**overrides):
    payload = {"rt_cd": "0", "output1": [], "output2": {"tot_ord_qty": "0"}}
    payload.update(overrides)
    return FakeResponse(payload)


def test_first_page_checks_only_two_mock_gets_and_uses_kst_date():
    day_boundary = datetime(2026, 11, 21, 16, tzinfo=timezone.utc)
    account_page = balance()
    account_page.headers = {"Tr_Cont": "M"}
    orders_page = history(output1=[{"odno": "0011223344"}])
    c = case(account_page, orders_page, clock=lambda: day_boundary)
    result = c.client.check_account()
    assert result.balance_ok is True and result.orders_ok is True and result.ok
    first, second = c.session.calls
    assert (first[0], first[1]) == ("GET", BALANCE_URL)
    assert (second[0], second[1]) == ("GET", HISTORY_URL)
    assert first[2]["params"] == {
        "CANO": c.credentials.account_number,
        "ACNT_PRDT_CD": "01",
        "AFHR_FLPR_YN": "N",
        "OFL_YN": "",
        "INQR_DVSN": "02",
        "UNPR_DVSN": "01",
        "FUND_STTL_ICLD_YN": "N",
        "FNCG_AMT_AUTO_RDPT_YN": "N",
        "PRCS_DVSN": "00",
        "CTX_AREA_FK100": "",
        "CTX_AREA_NK100": "",
    }
    assert second[2]["params"] == {
        "CANO": c.credentials.account_number,
        "ACNT_PRDT_CD": "01",
        "INQR_STRT_DT": "20261122",
        "INQR_END_DT": "20261122",
        "SLL_BUY_DVSN_CD": "00",
        "PDNO": "",
        "CCLD_DVSN": "00",
        "INQR_DVSN": "00",
        "INQR_DVSN_3": "01",
        "ORD_GNO_BRNO": "",
        "ODNO": "",
        "INQR_DVSN_1": "",
        "CTX_AREA_FK100": "",
        "CTX_AREA_NK100": "",
        "EXCG_ID_DVSN_CD": "KRX",
    }
    assert [call[2]["headers"]["tr_id"] for call in c.session.calls] == ["VTTC8434R", "VTTC0081R"]
    for _, _, options in c.session.calls:
        assert options["allow_redirects"] is False and options["verify"] is True
        assert options["headers"]["tr_cont"] == ""
    assert account_page.closed and orders_page.closed
    assert "321456" not in repr(result) and "0011223344" not in repr(result)


@pytest.mark.parametrize("fault", ["http", "broker", "empty-summary", "malformed-rows", "missing-header"])
def test_failed_balance_check_skips_order_history(fault):
    response = balance()
    if fault == "http":
        response.status_code = 503
    elif fault == "broker":
        response.payload.update(rt_cd="1", msg1="do not expose raw response")
    elif fault == "empty-summary":
        response.payload["output2"] = []
    elif fault == "malformed-rows":
        response.payload["output1"] = [None]
    else:
        response.headers = {}
    c = case(response)
    result = c.client.check_account()
    assert result.balance_ok is False and result.orders_ok is None and not result.ok
    assert [call[:2] for call in c.session.calls] == [("GET", BALANCE_URL)]
    assert response.closed and "do not expose raw response" not in repr(result)


@pytest.mark.parametrize("reply", ["empty-ok", "malformed-summary", "timeout"])
def test_order_history_result_does_not_require_orders_to_exist(reply):
    response = history()
    if reply == "malformed-summary":
        response.payload["output2"] = ["bad"]
    elif reply == "timeout":
        response = TimeoutError("private transport detail")
    c = case(balance(), response)
    result = c.client.check_account()
    assert result.balance_ok is True and result.orders_ok is (reply == "empty-ok")
    assert result.ok is (reply == "empty-ok")
    assert [call[:2] for call in c.session.calls] == [("GET", BALANCE_URL), ("GET", HISTORY_URL)]


def test_expired_token_and_a_cancelled_pause_do_not_trigger_another_request():
    now = [NOW]
    c = case(balance(), clock=lambda: now[0])
    now[0] += timedelta(hours=1)
    assert not c.client.check_account().ok
    assert c.session.calls == []

    def interrupted():
        raise RuntimeError("private pause detail")

    c = case(balance(), page_pause=interrupted)
    result = c.client.check_account()
    assert result.balance_ok and result.orders_ok is False and not result.ok
    assert [call[:2] for call in c.session.calls] == [("GET", BALANCE_URL)]


class LocalCheckSession(FakeSession):
    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


def local_command():
    return import_module("scripts.check_kis_mock_account")


def test_cli_with_only_live_or_generic_keys_stops_before_session(monkeypatch, capsys):
    for name in ENV_VALUES:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("INVEST_BOT_KIS_APP_KEY", "generic-private-key")
    monkeypatch.setenv("INVEST_BOT_KIS_LIVE_APP_SECRET", "live-private-secret")
    command = local_command()

    def unexpected():
        pytest.fail("session created without mock credentials")

    monkeypatch.setattr(command, "Session", unexpected)
    assert command.main([]) == 2
    output = capsys.readouterr().out
    assert "INVEST_BOT_KIS_MOCK_ACCOUNT_NUMBER" in output
    assert "generic-private-key" not in output and "live-private-secret" not in output


def test_cli_uses_provided_mock_scope_and_only_prints_check_status(monkeypatch, capsys):
    for name, value in ENV_VALUES.items():
        monkeypatch.setenv(name, value)
    command = local_command()
    session = LocalCheckSession(balance(), history())
    monkeypatch.setattr(command, "Session", lambda: session)
    monkeypatch.setattr(command, "sleep", lambda _: None)
    assert command.main([]) == 0
    assert session.trust_env is False
    assert [call[:2] for call in session.calls] == [("GET", BALANCE_URL), ("GET", HISTORY_URL)]
    output = capsys.readouterr().out
    assert output.strip() == "balance=ok orders=ok"
    assert all(value not in output for value in ENV_VALUES.values())


def test_cli_with_bad_expiry_is_redacted_and_makes_no_request(monkeypatch, capsys):
    for name, value in ENV_VALUES.items():
        monkeypatch.setenv(name, value)
    monkeypatch.setenv("INVEST_BOT_KIS_MOCK_TOKEN_EXPIRES_AT", "invalid-private-expiry")
    command = local_command()

    def unexpected():
        pytest.fail("session created with bad expiry")

    monkeypatch.setattr(command, "Session", unexpected)
    assert command.main([]) == 2
    assert "invalid-private-expiry" not in capsys.readouterr().out
