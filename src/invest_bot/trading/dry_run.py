"""Sequential process-memory simulation, not a transport or a fill engine."""
from dataclasses import replace
from decimal import Decimal
import hashlib
import json

from .models import (
    AccountSnapshot, OrderIntent, OrderRecord, OrderState, ReasonCode, Reservation,
    ReservationBook, Side, VirtualOutcome, aware, order_fingerprint, order_key, valid_id,
)
from ..risk.order_validation import _binding_valid, decision, validate_order

ZERO = Decimal(0)


class DryRunBroker:
    """Explicit scripted outcomes only; no I/O and no automatic re-evaluation.

    Public state is immutable. This is not a security sandbox against private
    attribute reflection, a process lock, a durable ledger or broker proof.
    """
    __slots__ = ("_bindings", "_book_id", "_outcomes", "_count", "_revision", "_records", "_active", "_blocked", "_captures", "_latest")

    def __init__(self, *, bindings, book_id, outcomes):
        if (type(bindings) is not tuple or not bindings or not all(_binding_valid(b) for b in bindings)
                or len({b.alias for b in bindings}) != len(bindings) or len({b.binding_id for b in bindings}) != len(bindings)
                or not valid_id(book_id) or type(outcomes) not in (tuple, list)
                or not all(type(outcome) is VirtualOutcome for outcome in outcomes)):
            raise ValueError("Explicit virtual bindings, book and outcome script are required")
        self._bindings = {b.alias: b for b in bindings}
        self._book_id, self._outcomes = book_id, tuple(outcomes)
        self._count = self._revision = 0
        self._records, self._active, self._captures, self._latest = {}, {}, {}, {}
        self._blocked = set()

    @property
    def execution_count(self):
        return self._count

    @property
    def records(self):
        return tuple(self._records.values())

    @property
    def reservations(self):
        return tuple(self._active.values())

    @property
    def blocked_accounts(self):
        return frozenset(self._blocked)

    @property
    def outcomes(self):
        return self._outcomes

    @property
    def book(self):
        return ReservationBook(self._book_id, self._revision, self.reservations)

    def execute(self, intent, *, policy, account, market, now, received_at=None):
        # received_at is attempt-only metadata, intentionally not decision input.
        key, fingerprint = order_key(intent), order_fingerprint(intent)
        prior = self._records.get(key) if key is not None else None
        if prior is not None:
            if prior.fingerprint == fingerprint:
                return prior
            rejected = decision((ReasonCode.IDEMPOTENCY_CONFLICT,), fingerprint)
            return OrderRecord(prior.order_id, OrderState.REJECTED, rejected, fingerprint, ZERO, 0,
                               client_order_id=prior.client_order_id, account_binding_id=prior.account_binding_id,
                               binding_version=prior.binding_version, evaluated_at=now if aware(now) else None)
        order_id = hashlib.sha256(json.dumps(key).encode()).hexdigest() if key is not None else None
        if key is not None and key[2] in self._blocked:
            result = decision((ReasonCode.RECONCILIATION_REQUIRED,), fingerprint)
        else:
            binding = self._bindings.get(intent.account_alias) if type(intent) is OrderIntent and valid_id(intent.account_alias) else None
            result = validate_order(intent, binding, policy, account, market, self.book, now=now)
            if result.account_version is not None:
                capture_key = (intent.account_binding_id, account.version)
                prior_capture = self._captures.get(capture_key)
                latest = self._latest.get(intent.account_binding_id)
                if ((prior_capture is not None and prior_capture != account)
                        or (latest is not None and (account.reservation_watermark < latest.reservation_watermark or account.captured_at < latest.captured_at))):
                    result = replace(result, allowed=False, reasons=(ReasonCode.SNAPSHOT_INVALID,), reserve_cash=ZERO, reserve_qty=0, reserve_exposure=ZERO)
                else:
                    self._captures[capture_key] = account
                    self._latest[intent.account_binding_id] = account
        if not result.allowed:
            record = OrderRecord(order_id, OrderState.REJECTED, result, fingerprint, ZERO, 0)
        else:
            self._revision += 1
            self._active[order_id] = Reservation(order_id, intent.account_binding_id, intent.symbol, Side(intent.side),
                                                  result.reserve_cash, result.reserve_qty, result.reserve_exposure, self._revision)
            outcome = self._outcomes[self._count] if self._count < len(self._outcomes) else VirtualOutcome.UNKNOWN
            self._count += 1
            if outcome is VirtualOutcome.BROKER_REJECTED:
                del self._active[order_id]
                self._revision += 1
                cash, qty = ZERO, 0
            else:
                cash, qty = result.reserve_cash, result.reserve_qty
                if outcome is VirtualOutcome.UNKNOWN:
                    self._blocked.add(intent.account_binding_id)
            record = OrderRecord(order_id, OrderState(outcome.value), result, fingerprint, cash, qty)
        binding = self._bindings.get(intent.account_alias) if type(intent) is OrderIntent and valid_id(intent.account_alias) else None
        resolved = (binding is not None and type(intent.account_binding_id) is str and binding.binding_id == intent.account_binding_id
                    and type(intent.binding_version) is str and binding.version == intent.binding_version)
        request_id = intent.client_order_id if type(intent) is OrderIntent and valid_id(intent.client_order_id) else None
        record = replace(record, client_order_id=request_id,
                         account_binding_id=binding.binding_id if resolved else None,
                         binding_version=binding.version if resolved else None,
                         evaluated_at=now if aware(now) else None)
        if key is not None:
            self._records[key] = record
        return record
