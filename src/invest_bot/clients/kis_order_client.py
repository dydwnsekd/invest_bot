"""Explicit KIS mock-only cash-order boundary; no authentication or persistence.

The caller owns durable claims, request expiry, kill switches, risk evidence and
proof that a queried broker identity belongs to its stored order. A supplied
transport is trusted to issue each request once, honour TLS/redirect/timeouts,
and keep credentials out of logs. No live endpoint or legacy TR fallback exists.
"""
from calendar import monthrange
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
import hashlib
import hmac
import json
import re
from urllib.parse import urlsplit

import requests

from ..trading.models import AccountBinding, Side, aware, valid_id
from ..trading.order_service import Dispatch, SubmissionReply


MOCK_BASE_URL = "https://openapivts.koreainvestment.com:29443"
ORDER_PATH = "/uapi/domestic-stock/v1/trading/order-cash"
BALANCE_PATH = "/uapi/domestic-stock/v1/trading/inquire-balance"
QUERY_PATH = "/uapi/domestic-stock/v1/trading/inquire-daily-ccld"
KST = timezone(timedelta(hours=9))
TIMEOUT = (3.05, 10.0)
MAX_PAGES = 20
MORE_CONTINUATIONS = frozenset({"M", "F"})
FINAL_CONTINUATIONS = frozenset({"", "D", "E"})


class KISMockBoundaryError(ValueError):
    """Fixed local-boundary failure, containing no credential or broker text."""


@dataclass(frozen=True, slots=True, repr=False)
class KISMockCredentials:
    account_number: str
    app_key: str
    app_secret: str
    access_token: str
    token_expires_at: datetime


@dataclass(frozen=True, slots=True)
class KISMockObservation:
    kind: str
    cumulative_qty: int
    cumulative_notional: Decimal
    broker_order_id: str
    observed_at: datetime


@dataclass(frozen=True, slots=True)
class KISMockAccountCheck:
    balance_ok: bool
    orders_ok: bool | None

    @property
    def ok(self) -> bool:
        return self.balance_ok and self.orders_ok is True


def _digits(value, minimum, maximum):
    return type(value) is str and re.fullmatch(r"[0-9]{%d,%d}" % (minimum, maximum), value) is not None


def _header_secret(value):
    return type(value) is str and 0 < len(value) <= 4096 and all(33 <= ord(char) <= 126 for char in value)


def _broker_parts(day, branch, number, clock_time):
    if (not _digits(day, 8, 8) or not _digits(branch, 1, 10) or not int(branch)
            or not _digits(number, 1, 10) or not int(number) or not _digits(clock_time, 6, 6)):
        raise KISMockBoundaryError("INVALID_BROKER_IDENTITY")
    try:
        at = datetime(int(day[:4]), int(day[4:6]), int(day[6:]), int(clock_time[:2]),
                      int(clock_time[2:4]), int(clock_time[4:]), tzinfo=KST)
    except ValueError:
        raise KISMockBoundaryError("INVALID_BROKER_IDENTITY") from None
    return at, branch, number


def _parse_identity(value):
    if type(value) is not str or not valid_id(value):
        raise KISMockBoundaryError("INVALID_BROKER_IDENTITY")
    parts = value.split(":")
    if len(parts) != 5 or parts[0] != "kis-mock-v1":
        raise KISMockBoundaryError("INVALID_BROKER_IDENTITY")
    at, branch, number = _broker_parts(*parts[1:])
    return at, parts[1], branch, number, parts[4]


def _uint(value):
    if not _digits(value, 1, 18):
        raise KISMockBoundaryError("INVALID_QUERY_ROW")
    return int(value)


def _won(value):
    if (type(value) is not str or len(value) > 128
            or re.fullmatch(r"[0-9]+(?:\.[0-9]+)?", value) is None):
        raise KISMockBoundaryError("INVALID_QUERY_ROW")
    try:
        number = Decimal(value)
        if number.as_integer_ratio()[1] != 1:
            raise KISMockBoundaryError("INVALID_QUERY_ROW")
        return number
    except (InvalidOperation, ValueError, OverflowError):
        raise KISMockBoundaryError("INVALID_QUERY_ROW") from None


class KISMockOrderClient:
    """One POST per invocation and at most MAX_PAGES successive GETs.

    Standard requests.Session is supported only without custom methods/adapters,
    retries, proxies, environment use, auth, cookies, hooks or shared parameters.
    Other injected transports must explicitly declare kis_mock_no_retries=True
    and implement request(method, url, **kwargs). That declaration is a trusted
    composition assertion, not introspection of an arbitrary transport's internals.
    page_pause, if supplied, runs only between successive pages; no sleep/rate
    policy or retry is inferred. The current server rate limit is not established.
    """

    __slots__ = ("_credentials", "_binding", "_session", "_clock", "_page_pause")

    def __init__(self, *, credentials, alias, binding_version, mode, base_url, session, clock, page_pause=None):
        if (type(mode) is not str or mode != "mock" or type(base_url) is not str or base_url != MOCK_BASE_URL
                or not valid_id(alias) or not valid_id(binding_version) or not callable(clock)
                or (page_pause is not None and not callable(page_pause)) or type(credentials) is not KISMockCredentials
                or not _digits(credentials.account_number, 8, 8)
                or not all(_header_secret(v) for v in (credentials.app_key, credentials.app_secret, credentials.access_token))
                or not aware(credentials.token_expires_at)):
            raise KISMockBoundaryError("INVALID_KIS_MOCK_CONFIGURATION")
        self._credentials, self._session, self._clock, self._page_pause = credentials, session, clock, page_pause
        self._check_session()
        self._now()
        # The secret is the HMAC key. Public identifiers cannot be used to test
        # guesses of the account without knowledge of that explicit key scope.
        message = json.dumps(["kis-mock-binding-v1", credentials.account_number, "01", credentials.app_key],
                             ensure_ascii=True, separators=(",", ":")).encode("ascii")
        binding_id = "kis-mock-" + hmac.new(credentials.app_secret.encode("ascii"), message, hashlib.sha256).hexdigest()
        self._binding = AccountBinding(alias, binding_id, binding_version, "mock", "kis_mock")

    @property
    def binding(self):
        return self._binding

    def _check_session(self):
        try:
            session = self._session
            if isinstance(session, requests.Session):
                if (type(session) is not requests.Session or session.trust_env is not False or session.verify is not True
                        or session.auth is not None or session.cert is not None or session.proxies or session.params
                        or session.cookies or session.hooks != {"response": []}):
                    raise KISMockBoundaryError("UNSUPPORTED_TRANSPORT")
                if ({key.lower() for key in session.headers} - {"user-agent", "accept-encoding", "accept", "connection"}
                        or any(type(value) is not str or not 0 < len(value) <= 4096
                               or any(not 32 <= ord(char) <= 126 for char in value) for value in session.headers.values())):
                    raise KISMockBoundaryError("UNSUPPORTED_TRANSPORT")
                for name in ("request", "send", "prepare_request", "merge_environment_settings", "get_adapter", "resolve_redirects"):
                    if getattr(getattr(session, name), "__func__", None) is not getattr(requests.Session, name):
                        raise KISMockBoundaryError("UNSUPPORTED_TRANSPORT")
                # More-specific mounts take precedence over the authority.
                # A mounted order path could otherwise bypass the retry check.
                if set(session.adapters) != {"https://", "http://"}:
                    raise KISMockBoundaryError("UNSUPPORTED_TRANSPORT")
                adapter = session.get_adapter(MOCK_BASE_URL + ORDER_PATH)
                if (type(adapter) is not requests.adapters.HTTPAdapter or type(adapter.max_retries.total) is not int
                        or adapter.max_retries.total != 0
                        or getattr(adapter.send, "__func__", None) is not requests.adapters.HTTPAdapter.send):
                    raise KISMockBoundaryError("RETRYING_TRANSPORT")
            elif getattr(session, "kis_mock_no_retries", None) is not True:
                raise KISMockBoundaryError("UNATTESTED_TRANSPORT")
            if not callable(getattr(session, "request", None)):
                raise KISMockBoundaryError("UNSUPPORTED_TRANSPORT")
        except Exception:
            raise KISMockBoundaryError("UNSUPPORTED_TRANSPORT") from None

    def _now(self):
        try:
            now = self._clock()
            if not aware(now) or now >= self._credentials.token_expires_at:
                raise KISMockBoundaryError("INVALID_CLOCK_OR_EXPIRED_TOKEN")
            return now
        except Exception:
            raise KISMockBoundaryError("INVALID_CLOCK_OR_EXPIRED_TOKEN") from None

    def _dispatch(self, dispatch):
        if (type(dispatch) is not Dispatch or not all(valid_id(v) for v in (dispatch.order_id, dispatch.account_binding_id, dispatch.binding_version))
                or type(dispatch.execution_target) is not str or dispatch.execution_target != "kis_mock"
                or type(dispatch.mode) is not str or dispatch.mode != "mock" or type(dispatch.currency) is not str or dispatch.currency != "KRW"
                or dispatch.account_binding_id != self.binding.binding_id or dispatch.binding_version != self.binding.version
                or not _digits(dispatch.symbol, 6, 6) or type(dispatch.side) is not Side
                or type(dispatch.qty) is not int or dispatch.qty <= 0
                or type(dispatch.limit_price) is not Decimal or not dispatch.limit_price.is_finite() or dispatch.limit_price <= 0
                or dispatch.limit_price.as_integer_ratio()[1] != 1):
            raise KISMockBoundaryError("INVALID_DISPATCH")

    def _headers(self, tr_id, continuation=""):
        return {"content-type": "application/json", "authorization": "Bearer " + self._credentials.access_token,
                "appkey": self._credentials.app_key, "appsecret": self._credentials.app_secret,
                "tr_id": tr_id, "custtype": "P", "tr_cont": continuation}

    def _request(self, method, path, *, headers, **kwargs):
        response = None
        try:
            # Revalidate mutable transport configuration immediately before I/O.
            self._check_session()
            self._now()
            response = self._session.request(method, MOCK_BASE_URL + path, headers=headers, timeout=TIMEOUT,
                                             allow_redirects=False, verify=True, **kwargs)
            if type(response.status_code) is not int or response.status_code != 200:
                return None
            if type(response.history) not in (list, tuple) or response.history:
                return None
            url = urlsplit(response.url)
            if (url.scheme != "https" or url.netloc != "openapivts.koreainvestment.com:29443"
                    or url.path != path or url.fragment or (method == "POST" and url.query)):
                return None
            payload = response.json()
            if type(payload) is not dict or type(payload.get("rt_cd")) is not str or payload["rt_cd"] != "0":
                return None
            if not isinstance(response.headers, Mapping):
                return None
            continuation = [value for key, value in response.headers.items() if type(key) is str and key.lower() == "tr_cont"]
            return payload, continuation
        except Exception:
            return None
        finally:
            try:
                if response is not None:
                    response.close()
            except Exception:
                pass

    def _daily_query_params(self, day, *, side="00", symbol="", branch="", order_number=""):
        return {
            "CANO": self._credentials.account_number, "ACNT_PRDT_CD": "01",
            "INQR_STRT_DT": day, "INQR_END_DT": day, "SLL_BUY_DVSN_CD": side, "PDNO": symbol,
            "CCLD_DVSN": "00", "INQR_DVSN": "00", "INQR_DVSN_3": "01", "ORD_GNO_BRNO": branch,
            "ODNO": order_number, "INQR_DVSN_1": "", "CTX_AREA_FK100": "", "CTX_AREA_NK100": "",
            "EXCG_ID_DVSN_CD": "KRX",
        }

    @staticmethod
    def _check_page(response, *, balance):
        if response is None:
            return False
        payload, continuations = response
        if (len(continuations) != 1 or type(continuations[0]) is not str
                or continuations[0] not in MORE_CONTINUATIONS | FINAL_CONTINUATIONS):
            return False
        rows, summary = payload.get("output1"), payload.get("output2")
        if (type(rows) is not list or len(rows) > (20 if balance else 15)
                or any(type(row) is not dict for row in rows)):
            return False
        if balance:
            return type(summary) is list and bool(summary) and all(type(row) is dict and row for row in summary)
        return type(summary) is dict

    def check_account(self) -> KISMockAccountCheck:
        """Check one page from each read-only endpoint with the supplied mock token."""
        params = {
            "CANO": self._credentials.account_number, "ACNT_PRDT_CD": "01",
            "AFHR_FLPR_YN": "N", "OFL_YN": "", "INQR_DVSN": "02", "UNPR_DVSN": "01",
            "FUND_STTL_ICLD_YN": "N", "FNCG_AMT_AUTO_RDPT_YN": "N", "PRCS_DVSN": "00",
            "CTX_AREA_FK100": "", "CTX_AREA_NK100": "",
        }
        balance = self._request("GET", BALANCE_PATH, headers=self._headers("VTTC8434R"), params=params)
        if not self._check_page(balance, balance=True):
            return KISMockAccountCheck(False, None)

        try:
            if self._page_pause is not None:
                self._page_pause()
            day = self._now().astimezone(KST).strftime("%Y%m%d")
        except Exception:
            return KISMockAccountCheck(True, False)
        orders = self._request(
            "GET", QUERY_PATH, headers=self._headers("VTTC0081R"), params=self._daily_query_params(day),
        )
        return KISMockAccountCheck(True, self._check_page(orders, balance=False))

    def submit_claim(self, dispatch: Dispatch) -> SubmissionReply:
        self._dispatch(dispatch)
        self._check_session()
        before = self._now()
        unknown = SubmissionReply(dispatch.order_id, self.binding.binding_id, "UNKNOWN", None, False)
        body = {"CANO": self._credentials.account_number, "ACNT_PRDT_CD": "01", "PDNO": dispatch.symbol,
                "ORD_DVSN": "00", "ORD_QTY": str(dispatch.qty), "ORD_UNPR": str(dispatch.limit_price.as_integer_ratio()[0]),
                "EXCG_ID_DVSN_CD": "KRX", "SLL_TYPE": "01" if dispatch.side is Side.SELL else "", "CNDT_PRIC": ""}
        tr_id = "VTTC0012U" if dispatch.side is Side.BUY else "VTTC0011U"
        response = self._request("POST", ORDER_PATH, headers=self._headers(tr_id), json=body)
        try:
            after = self._now()
            if response is None or after < before or before.astimezone(KST).date() != after.astimezone(KST).date():
                return unknown
            output = response[0].get("output")
            if type(output) is not dict:
                return unknown
            local_day = before.astimezone(KST).date()
            day = f"{local_day.year:04d}{local_day.month:02d}{local_day.day:02d}"
            branch, number, clock_time = output.get("KRX_FWDG_ORD_ORGNO"), output.get("ODNO"), output.get("ORD_TMD")
            at, _, _ = _broker_parts(day, branch, number, clock_time)
            if not before.replace(microsecond=0) <= at <= after:
                return unknown
            broker_id = f"kis-mock-v1:{day}:{branch}:{number}:{clock_time}"
            return SubmissionReply(dispatch.order_id, self.binding.binding_id, "ACKNOWLEDGED", broker_id, True)
        except Exception:
            return unknown

    @staticmethod
    def _recent(at, now):
        today = now.astimezone(KST).date()
        month_index = today.year * 12 + today.month - 1 - 3
        year, month = month_index // 12, month_index % 12 + 1
        floor = date(year, month, min(today.day, monthrange(year, month)[1]))
        return at <= now and floor <= at.date() <= today

    def lookup(self, dispatch: Dispatch, broker_order_id: str) -> KISMockObservation | None:
        try:
            self._dispatch(dispatch)
            self._check_session()
            now = self._now()
            at, day, branch, number, clock_time = _parse_identity(broker_order_id)
            if not self._recent(at, now):
                return None
            params = self._daily_query_params(
                day, side="02" if dispatch.side is Side.BUY else "01",
                symbol=dispatch.symbol, branch=branch, order_number=number,
            )
            seen, observations, continuation = {("", "")}, [], ""
            for page_index in range(MAX_PAGES):
                if page_index and self._page_pause is not None:
                    self._page_pause()
                before = self._now()
                if not self._recent(at, before):
                    return None
                response = self._request("GET", QUERY_PATH, headers=self._headers("VTTC0081R", continuation), params=dict(params))
                now = self._now()
                if response is None or now < before:
                    return None
                payload, header_values = response
                if len(header_values) != 1 or type(header_values[0]) is not str:
                    return None
                response_cont = header_values[0]
                if response_cont not in MORE_CONTINUATIONS | FINAL_CONTINUATIONS:
                    return None
                rows = payload.get("output1")
                if type(rows) is not list or len(rows) > 15:
                    return None
                for row in rows:
                    observation = self._row(dispatch, row, day, branch, number, clock_time)
                    if observation is None:
                        return None
                    observations.append(observation)
                if response_cont in FINAL_CONTINUATIONS:
                    if len(observations) != 1:
                        return None
                    kind, qty, amount = observations[0]
                    return KISMockObservation(kind, qty, amount, broker_order_id, now)
                fk, nk = payload.get("ctx_area_fk100"), payload.get("ctx_area_nk100")
                if any(type(value) is not str or len(value) > 100 or any(not 32 <= ord(char) <= 126 for char in value) for value in (fk, nk)):
                    return None
                cursor = (fk.strip(), nk.strip())
                if cursor in seen:
                    return None
                seen.add(cursor)
                params.update(CTX_AREA_FK100=fk, CTX_AREA_NK100=nk)
                continuation = "N"
            return None
        except Exception:
            # No raw transport/KIS row/error data crosses this boundary.
            return None

    @staticmethod
    def _row(dispatch, row, day, branch, number, clock_time):
        if type(row) is not dict:
            return None
        expected = {"ord_dt": day, "ord_gno_brno": branch, "odno": number, "ord_tmd": clock_time,
                    "ord_dvsn_cd": "00", "sll_buy_dvsn_cd": "02" if dispatch.side is Side.BUY else "01", "pdno": dispatch.symbol}
        if any(type(row.get(key)) is not str or row[key] != value for key, value in expected.items()):
            return None
        if _uint(row.get("ord_qty")) != dispatch.qty or _won(row.get("ord_unpr")) != dispatch.limit_price:
            return None
        filled, remaining, cancelled, rejected = (_uint(row.get(key)) for key in ("tot_ccld_qty", "rmn_qty", "cnc_cfrm_qty", "rjct_qty"))
        amount = _won(row.get("tot_ccld_amt"))
        if (filled + remaining + cancelled + rejected != dispatch.qty or type(row.get("cncl_yn")) is not str
                or row["cncl_yn"] not in {"N", "Y"} or (filled == 0 and amount != 0) or (filled > 0 and amount <= 0)):
            return None
        actual = amount.as_integer_ratio()[0]
        limit = dispatch.limit_price.as_integer_ratio()[0] * filled
        if (dispatch.side is Side.BUY and actual > limit) or (dispatch.side is Side.SELL and actual < limit):
            return None
        if rejected:
            if rejected == dispatch.qty and not filled and not remaining and not cancelled and row["cncl_yn"] == "N":
                return "BROKER_REJECTED", filled, amount
            return None
        if row["cncl_yn"] == "Y":
            if cancelled > 0 and filled < dispatch.qty and not remaining:
                return "CANCELLED", filled, amount
            return None
        if cancelled:
            return None
        kind = "FILLED" if filled == dispatch.qty else "PARTIALLY_FILLED" if filled else "ACKNOWLEDGED"
        return kind, filled, amount
