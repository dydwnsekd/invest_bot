"""Submit and confirm KIS mock orders through an explicitly bound ledger."""
from ..clients.kis_order_client import KISMockBoundaryError, KISMockOrderClient
from .models import valid_id
from .order_service import EvidenceRejected, OrderService, ReconciliationEvidence, ReconcileResult
from .order_store import FillReceipt, LedgerOrder, OrderStore, digest


class KISMockOrders:
    """Public entry point for one explicit mock account, clock and order ledger."""

    def __init__(self, store: OrderStore, client: KISMockOrderClient, *, clock, kill_switch):
        if (type(store) is not OrderStore or store.execution_target != "kis_mock"
                or type(client) is not KISMockOrderClient or store.bindings() != (client.binding,)):
            raise KISMockBoundaryError("MOCK_LEDGER_BINDING_MISMATCH")
        self._service = OrderService(store, clock=clock, kill_switch=kill_switch)
        self._client = client

    def submit(self, intent, *, context) -> LedgerOrder:
        """Claim and reserve the order before allowing the single order POST."""
        return self._service.submit(intent, context=context, send=self._client.submit_claim)

    def refresh(self, order_id: str) -> ReconcileResult | None:
        """Confirm an existing broker identity and apply a newer valid observation."""
        if not valid_id(order_id):
            raise KISMockBoundaryError("INVALID_ORDER_ID")
        claim = self._service._lookup_claim(order_id)
        if claim is None:
            return None
        order, dispatch, sequence = claim
        if dispatch is None:
            return ReconcileResult(order, False)

        observation = self._client.lookup(dispatch, order.broker_order_id)
        if observation is None or self._same_state(order, observation):
            return ReconcileResult(self._service.store.get(order_id), False)

        numerator, denominator = observation.cumulative_notional.as_integer_ratio()
        event_id = "kis-observation-" + digest([
            order_id, observation.broker_order_id, observation.kind,
            observation.cumulative_qty, str(numerator), str(denominator),
        ])
        try:
            return self._service.reconcile(ReconciliationEvidence(
                event_id, order_id, order.account_binding_id, observation.broker_order_id,
                "kis-mock-daily-ccld", observation.observed_at, observation.kind, sequence + 1,
                observation.cumulative_qty, observation.cumulative_notional, True,
            ))
        except EvidenceRejected as error:
            if str(error) == "EVENT_CONFLICT":
                latest = self._service.store.get(order_id)
                if self._same_state(latest, observation):
                    return ReconcileResult(latest, False)
            raise

    @staticmethod
    def _same_state(order, observation):
        return (order.state == observation.kind and order.cumulative_qty == observation.cumulative_qty
                and order.cumulative_notional == observation.cumulative_notional)

    def fill_receipts(self) -> tuple[FillReceipt, ...]:
        """List ledger facts to compare against a separate trusted balance capture."""
        return self._service.store.fill_receipts(self._client.binding.binding_id)
