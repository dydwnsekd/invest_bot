"""Durable one-shot virtual dispatch and explicit synthetic reconciliation.

The injected sender is synchronous: it must not retain dispatch capability or
queue/detach work after returning. No real broker, settings or network adapters
are supplied here. Snapshot receipts and confirmed events are trusted inputs,
not proof obtained from a real broker. File locks require a cooperating local
filesystem and all services using the same ledger file.
"""
from contextlib import nullcontext
from dataclasses import dataclass, fields, replace
from datetime import datetime, timezone
from decimal import Decimal
from fractions import Fraction
import json
import uuid

from .models import (
    AccountSnapshot, OrderIntent, Position, ReasonCode, Side, aware,
    order_fingerprint, order_key, valid_id,
)
from .order_store import LedgerOrder, OrderStore, SenderActive, decision_data, digest, encode, record
from ..risk.order_validation import _decimal, decision, validate_order

ZERO = Decimal(0)
TERMINAL = frozenset({"REJECTED", "BROKER_REJECTED", "NOT_ACCEPTED", "CANCELLED", "EXPIRED", "FILLED"})


class EvidenceRejected(ValueError):
    _ledger_domain_error = True


@dataclass(frozen=True, slots=True, repr=False)
class ValidationContext:
    binding: object
    policy: object
    account: object
    market: object
    settled_event_ids: frozenset[str]


@dataclass(frozen=True, slots=True)
class Dispatch:
    order_id: str
    account_binding_id: str
    binding_version: str
    symbol: str
    side: Side
    qty: int
    limit_price: Decimal
    currency: str = "KRW"
    mode: str = "mock"
    execution_target: str = "dry_run"


@dataclass(frozen=True, slots=True, repr=False)
class SubmissionReply:
    order_id: str
    account_binding_id: str
    status: str
    broker_order_id: str | None
    confirmed: bool


@dataclass(frozen=True, slots=True, repr=False)
class ReconciliationEvidence:
    event_id: str
    order_id: str
    account_binding_id: str
    broker_order_id: str | None
    source_id: str
    observed_at: datetime
    kind: str
    sequence: int
    cumulative_qty: int
    cumulative_notional: Decimal
    confirmed: bool


@dataclass(frozen=True, slots=True, repr=False)
class SenderStoppedEvidence:
    order_id: str
    account_binding_id: str
    source_id: str
    observed_at: datetime


@dataclass(frozen=True, slots=True)
class ReconcileResult:
    order: LedgerOrder
    applied: bool


def _time(value):
    return value.astimezone(timezone.utc).isoformat() if aware(value) else None


def _atom(value):
    """Canonical, exact snapshot hash, only after the pure validator accepts it."""
    if type(value) is Decimal:
        numerator, denominator = value.as_integer_ratio()
        return ["money", str(numerator), str(denominator)]
    if type(value) is datetime:
        return ["time", _time(value)]
    if type(value) in (AccountSnapshot, Position):
        return [[field.name, _atom(getattr(value, field.name))] for field in fields(value)]
    if type(value) is frozenset:
        return sorted(value)
    if type(value) is tuple:
        return [_atom(item) for item in value]
    if type(value) in (str, int, bool) or value is None:
        return value
    raise EvidenceRejected("SNAPSHOT_INVALID")


class OrderService:
    """Claims commit before dispatch; any ambiguous commit cuts dispatch off.

    SUBMITTING and UNKNOWN block the entire binding, including after reopen.
    Replay never asks for a clock, kill-switch or new validation context.
    """

    def __init__(self, store, *, clock, kill_switch):
        if type(store) is not OrderStore or not callable(clock) or not callable(kill_switch):
            raise ValueError("explicit store, clock and kill switch are required")
        self.store, self.clock, self.kill_switch = store, clock, kill_switch

    @staticmethod
    def _replay(row, fingerprint):
        prior = record(row)
        if prior.fingerprint == fingerprint:
            return prior
        return replace(prior, state="REJECTED", decision=decision((ReasonCode.IDEMPOTENCY_CONFLICT,), fingerprint),
                       fingerprint=fingerprint, reserved_cash=ZERO, reserved_qty=0, reserved_exposure=ZERO,
                       remaining_qty=0)

    def submit(self, intent, *, context, send):
        key, fingerprint = order_key(intent), order_fingerprint(intent)
        if key is None:
            wrong_mode = (type(intent) is OrderIntent and
                          (type(intent.mode) is not str or intent.mode != "mock"
                           or type(intent.execution_target) is not str or intent.execution_target != "dry_run"))
            reason = ReasonCode.MODE_NOT_ALLOWED if wrong_mode else ReasonCode.INVALID_ORDER
            return LedgerOrder(None, "REJECTED", decision((reason,), fingerprint), fingerprint)
        scope = encode(key)
        # Fast immutable replay, repeated under the write lock for a new claim.
        with self.store.transaction() as con:
            prior = con.execute("SELECT * FROM orders WHERE scope=?", (scope,)).fetchone()
            if prior:
                return self._replay(prior, fingerprint)
        with self.store.sender_barrier():
            with self.store.transaction(write=True) as con:
                prior = con.execute("SELECT * FROM orders WHERE scope=?", (scope,)).fetchone()
                if prior:
                    return self._replay(prior, fingerprint)
                order_id, token = uuid.uuid4().hex, uuid.uuid4().hex
                binding = self.store._binding(con, intent.account_alias) if valid_id(intent.account_alias) else None
                resolved = (binding is not None and type(intent.account_binding_id) is str
                            and binding.binding_id == intent.account_binding_id
                            and type(intent.binding_version) is str and binding.version == intent.binding_version)
                now = None
                result = decision((ReasonCode.RECONCILIATION_REQUIRED,), fingerprint)
                blocked = con.execute("SELECT 1 FROM orders WHERE binding_id=? AND state IN ('SUBMITTING','UNKNOWN')",
                                      (key[2],)).fetchone()
                if not blocked:
                    current = None
                    book = self.store._book(con)
                    try:
                        # Fresh evidence and clock are acquired inside BEGIN IMMEDIATE.
                        if self.kill_switch() is False:
                            current = context()
                            # Context acquisition can block. Its earlier admission
                            # time/kill state cannot authorize a later claim.
                            now = self.clock()
                            if (self.kill_switch() is False and type(current) is ValidationContext
                                    and current.binding == binding):
                                result = validate_order(intent, binding, current.policy, current.account,
                                                        current.market, book, now=now)
                    except Exception:
                        # No raw callback errors are recorded or exposed as broker rejection.
                        result = decision((ReasonCode.RECONCILIATION_REQUIRED,), fingerprint)
                    if result.account_version is not None:
                        try:
                            captured = self._capture(con, binding, current)
                        except EvidenceRejected:
                            captured = False
                        if not captured:
                            result = replace(result, allowed=False, reasons=(ReasonCode.SNAPSHOT_INVALID,),
                                             reserve_cash=ZERO, reserve_qty=0, reserve_exposure=ZERO)
                active = result.allowed
                data = dict(fingerprint=fingerprint, decision=decision_data(result),
                            client_order_id=key[3], binding_version=binding.version if resolved else None,
                            evaluated_at=_time(now), broker_order_id=None,
                            symbol=intent.symbol if active else None, side=Side(intent.side).value if active else None,
                            qty=intent.qty if active else 0, limit_price=str(intent.limit_price) if active else "0",
                            fee_ceiling=str(_decimal(Fraction(result.reserve_cash) - Fraction(result.reserve_exposure))),
                            reserved_cash=str(result.reserve_cash), reserved_qty=result.reserve_qty,
                            reserved_exposure=str(result.reserve_exposure), remaining_qty=intent.qty if active else 0,
                            reservation_sequence=0, cumulative_qty=0, cumulative_notional="0",
                            event_sequence=0, event_at=None, sender_token=token if active else None)
                state = "SUBMITTING" if active else "REJECTED"
                con.execute("INSERT INTO orders VALUES (?,?,?,?,?,?)", (order_id, scope,
                            binding.binding_id if resolved else None, state, int(active), encode(data)))
                revision = self.store._audit(con, order_id, "CLAIM" if active else "DENY", _time(now))
                if active:
                    data["reservation_sequence"] = revision
                    self.store._update(con, order_id, state, True, data)
                pending = record(self.store._find(con, order_id))
            # No SQLite transaction or write lock exists across this callback.
            # A commit error (even one reported after the commit) cannot reach here.
            if not active:
                return pending
            dispatch = Dispatch(order_id, binding.binding_id, binding.version, intent.symbol,
                                Side(intent.side), intent.qty, intent.limit_price)
            try:
                reply = send(dispatch)
            except Exception:
                reply = None
            return self._finish(order_id, token, reply)

    def _capture(self, con, binding, current):
        account, settled = current.account, current.settled_event_ids
        if type(settled) is not frozenset or not all(valid_id(item) for item in settled):
            return False
        fills = con.execute("SELECT event_id,revision,payload FROM events WHERE binding_id=? AND filled=1",
                            (binding.binding_id,)).fetchall()
        # A receipt is explicit evidence of the particular fills in this capture.
        # A newer timestamp/version alone cannot discharge this gate.
        if settled != frozenset(row["event_id"] for row in fills):
            return False
        if fills and account.reservation_watermark < max(row["revision"] for row in fills):
            return False
        if any(account.captured_at < datetime.fromisoformat(json.loads(row["payload"])["observed_at"]) for row in fills):
            return False
        capture_digest = digest([_atom(account), sorted(settled)])
        prior = con.execute("SELECT * FROM captures WHERE binding_id=? AND version=?",
                            (binding.binding_id, account.version)).fetchone()
        if prior and prior["digest"] != capture_digest:
            return False
        for previous in con.execute("SELECT captured_at,watermark FROM captures WHERE binding_id=?", (binding.binding_id,)):
            if (account.captured_at < datetime.fromisoformat(previous["captured_at"])
                    or account.reservation_watermark < previous["watermark"]):
                return False
        if not prior:
            con.execute("INSERT INTO captures VALUES (?,?,?,?,?)", (binding.binding_id, account.version,
                        capture_digest, _time(account.captured_at), account.reservation_watermark))
        return True

    def _finish(self, order_id, token, reply):
        with self.store.transaction(write=True) as con:
            row = self.store._find(con, order_id)
            data = json.loads(row["payload"])
            if row["state"] != "SUBMITTING" or row["sender_active"] != 1 or data["sender_token"] != token:
                raise EvidenceRejected("CLAIM_MISMATCH")
            status, broker_id = "UNKNOWN", None
            if (type(reply) is SubmissionReply and type(reply.order_id) is str and reply.order_id == order_id
                    and type(reply.account_binding_id) is str and reply.account_binding_id == row["binding_id"]
                    and reply.confirmed is True and type(reply.status) is str):
                if reply.status == "ACKNOWLEDGED" and valid_id(reply.broker_order_id):
                    if self._broker_available(con, order_id, row["binding_id"], reply.broker_order_id):
                        status, broker_id = reply.status, reply.broker_order_id
                elif (reply.status == "BROKER_REJECTED" and (reply.broker_order_id is None or valid_id(reply.broker_order_id))
                      and (reply.broker_order_id is None or self._broker_available(con, order_id, row["binding_id"], reply.broker_order_id))):
                    status, broker_id = reply.status, reply.broker_order_id
            data["broker_order_id"], data["sender_token"] = broker_id, None
            revision = self.store._audit(con, order_id, "SEND_" + status, data["evaluated_at"])
            if status == "BROKER_REJECTED":
                self._release(data, revision)
            self.store._update(con, order_id, status, False, data)
            result = record(self.store._find(con, order_id))
        return result

    @staticmethod
    def _broker_available(con, order_id, binding_id, broker_id):
        return all(json.loads(other["payload"])["broker_order_id"] != broker_id for other in con.execute(
            "SELECT payload FROM orders WHERE binding_id=? AND order_id<>?", (binding_id, order_id)))

    @staticmethod
    def _release(data, revision):
        data.update(reserved_cash="0", reserved_qty=0, reserved_exposure="0", remaining_qty=0,
                    reservation_sequence=revision)

    @staticmethod
    def _evidence_data(e):
        if (type(e) is not ReconciliationEvidence or e.confirmed is not True
                or not all(valid_id(v) for v in (e.event_id, e.order_id, e.account_binding_id, e.source_id))
                or (e.broker_order_id is not None and not valid_id(e.broker_order_id))
                or not aware(e.observed_at) or type(e.kind) is not str
                or e.kind not in {"ACKNOWLEDGED", "PARTIALLY_FILLED", "FILLED", "BROKER_REJECTED", "NOT_ACCEPTED", "CANCELLED", "EXPIRED"}
                or type(e.sequence) is not int or e.sequence < 1 or type(e.cumulative_qty) is not int or e.cumulative_qty < 0
                or type(e.cumulative_notional) is not Decimal or not e.cumulative_notional.is_finite() or e.cumulative_notional < 0):
            raise EvidenceRejected("INVALID_EVIDENCE")
        return dict(event_id=e.event_id, order_id=e.order_id, account_binding_id=e.account_binding_id,
                    broker_order_id=e.broker_order_id, source_id=e.source_id, observed_at=_time(e.observed_at),
                    kind=e.kind, sequence=e.sequence, cumulative_qty=e.cumulative_qty,
                    cumulative_notional=_atom(e.cumulative_notional))

    def reconcile(self, evidence, *, stopped=None):
        payload = self._evidence_data(evidence)
        e = evidence
        with self.store.transaction() as con:
            row = self.store._find(con, e.order_id)
            if row is None or row["binding_id"] != e.account_binding_id:
                raise EvidenceRejected("ORDER_SCOPE_MISMATCH")
            active = row["sender_active"] == 1
        if active and type(stopped) is not SenderStoppedEvidence:
            raise EvidenceRejected("SENDER_STOP_PROOF_REQUIRED")
        try:
            barrier = self.store.sender_barrier(exclusive=True) if active else nullcontext()
            with barrier:
                return self._reconcile(e, payload, stopped)
        except SenderActive:
            raise EvidenceRejected("SENDER_STILL_ACTIVE") from None

    def _reconcile(self, e, payload, stopped):
        event_key, proof_digest = encode([e.account_binding_id, e.event_id]), digest(payload)
        with self.store.transaction(write=True) as con:
            row = self.store._find(con, e.order_id)
            existing = con.execute("SELECT digest FROM events WHERE event_key=?", (event_key,)).fetchone()
            if existing:
                if existing["digest"] != proof_digest:
                    raise EvidenceRejected("EVENT_CONFLICT")
                return ReconcileResult(record(row), False)
            data = json.loads(row["payload"])
            try:
                now = self.clock()
            except Exception:
                raise EvidenceRejected("CLOCK_UNAVAILABLE") from None
            if (not aware(now) or e.observed_at > now or data["evaluated_at"] is None
                    or e.observed_at < datetime.fromisoformat(data["evaluated_at"])
                    or (data["event_at"] and e.observed_at < datetime.fromisoformat(data["event_at"]))
                    or e.sequence <= data["event_sequence"] or row["state"] in TERMINAL):
                raise EvidenceRejected("EVENT_ORDER_INVALID")
            if row["sender_active"]:
                if (type(stopped) is not SenderStoppedEvidence or type(stopped.order_id) is not str or stopped.order_id != e.order_id
                        or type(stopped.account_binding_id) is not str or stopped.account_binding_id != e.account_binding_id
                        or not valid_id(stopped.source_id) or not aware(stopped.observed_at)
                        or not datetime.fromisoformat(data["evaluated_at"]) <= stopped.observed_at <= e.observed_at):
                    raise EvidenceRejected("SENDER_STOP_PROOF_INVALID")
            old_qty, qty = data["cumulative_qty"], e.cumulative_qty
            old_value, value = Fraction(Decimal(data["cumulative_notional"])), Fraction(e.cumulative_notional)
            if (qty < old_qty or qty > data["qty"] or value < old_value
                    or (qty == old_qty and value != old_value) or (qty == 0 and value != 0)):
                raise EvidenceRejected("CUMULATIVE_FILL_INVALID")
            if qty > old_qty:
                delta = value - old_value
                limit = Fraction(Decimal(data["limit_price"])) * (qty - old_qty)
                if delta <= 0 or (data["side"] == "BUY" and delta > limit) or (data["side"] == "SELL" and delta < limit):
                    raise EvidenceRejected("FILL_PRICE_INVALID")
            if data["broker_order_id"] is not None and e.broker_order_id != data["broker_order_id"]:
                raise EvidenceRejected("BROKER_IDENTITY_CONFLICT")
            if e.broker_order_id is not None and not self._broker_available(con, e.order_id, e.account_binding_id, e.broker_order_id):
                raise EvidenceRejected("BROKER_IDENTITY_CONFLICT")
            if e.kind == "NOT_ACCEPTED":
                if row["state"] not in {"SUBMITTING", "UNKNOWN"} or qty or value or e.broker_order_id is not None or data["broker_order_id"]:
                    raise EvidenceRejected("NOT_ACCEPTED_INVALID")
            elif e.kind == "BROKER_REJECTED":
                if qty or value:
                    raise EvidenceRejected("REJECTION_WITH_FILL")
            elif not valid_id(e.broker_order_id):
                raise EvidenceRejected("BROKER_IDENTITY_REQUIRED")
            if e.kind == "ACKNOWLEDGED" and (qty or row["state"] == "PARTIALLY_FILLED"):
                raise EvidenceRejected("ACK_AFTER_FILL")
            if e.kind == "PARTIALLY_FILLED" and not (old_qty < qty < data["qty"]):
                raise EvidenceRejected("PARTIAL_FILL_INVALID")
            if e.kind == "FILLED" and not (old_qty < qty == data["qty"]):
                raise EvidenceRejected("FINAL_FILL_INVALID")
            if e.kind in {"CANCELLED", "EXPIRED"} and qty >= data["qty"]:
                raise EvidenceRejected("TERMINAL_FILL_INVALID")
            revision = self.store._audit(con, e.order_id, "RECONCILE_" + e.kind, _time(e.observed_at), proof_digest)
            data.update(cumulative_qty=qty, cumulative_notional=str(e.cumulative_notional),
                        broker_order_id=e.broker_order_id, event_sequence=e.sequence, event_at=_time(e.observed_at), sender_token=None)
            if e.kind in TERMINAL:
                self._release(data, revision)
            elif qty > old_qty:
                remaining = data["qty"] - qty
                exposure = Fraction(Decimal(data["limit_price"])) * remaining if data["side"] == "BUY" else Fraction(0)
                data.update(remaining_qty=remaining, reserved_exposure=str(_decimal(exposure)),
                            reserved_cash=str(_decimal(exposure + Fraction(Decimal(data["fee_ceiling"])))),
                            reserved_qty=remaining if data["side"] == "SELL" else 0, reservation_sequence=revision)
            self.store._update(con, e.order_id, e.kind, False, data)
            con.execute("INSERT INTO events VALUES (?,?,?,?,?,?,?,?)", (event_key, e.order_id, e.account_binding_id,
                        e.event_id, proof_digest, revision, int(qty > old_qty), encode(payload)))
            result = ReconcileResult(record(self.store._find(con, e.order_id)), True)
        return result
