"""Synthetic T06c context and importable subprocess workers only."""
from dataclasses import replace
from importlib import import_module
from types import ModuleType, SimpleNamespace
import os
import sys

import pytest

from t06b_order_fixture import case, NOW, D


def api():
    return SimpleNamespace(s=import_module("invest_bot.trading.order_store"), v=import_module("invest_bot.trading.order_service"))


def setup(path, *, c=None):
    c = case() if c is None else c
    a = api()
    store = a.s.OrderStore.bootstrap(path, book_id="book-a", bindings=(c.binding,))
    service = a.v.OrderService(store, clock=lambda: NOW, kill_switch=lambda: False)
    return c, store, service


def context(c, settled=frozenset()):
    return api().v.ValidationContext(c.binding, c.policy, c.account, c.market, settled)


def ack(dispatch):
    return api().v.SubmissionReply(dispatch.order_id, dispatch.account_binding_id, "ACKNOWLEDGED", "broker-" + dispatch.order_id, True)


def evidence(record, kind, *, qty=0, notional="0", seq=1, event="event-1", **changes):
    values = dict(event_id=event, order_id=record.order_id, account_binding_id=record.account_binding_id,
                  broker_order_id=None if kind == "NOT_ACCEPTED" else (record.broker_order_id or "broker-1"),
                  source_id="virtual-query", observed_at=NOW, kind=kind, sequence=seq,
                  cumulative_qty=qty, cumulative_notional=D(notional), confirmed=True)
    values.update(changes)
    return api().v.ReconciliationEvidence(**values)


def start_spawned_worker(process):
    # Streamlit AppTest can leave a generated script in __main__. The
    # importable worker does not need to re-execute any parent entry point.
    with pytest.MonkeyPatch.context() as patch:
        patch.setitem(sys.modules, "__main__", ModuleType("__main__"))
        process.start()


def worker(path, start, queue, marker, *, client_id="order-1", sell=False, crash=False, cash="1000"):
    c = case(); a = api()
    if sell:
        c.intent = replace(c.intent, side=c.d.m.Side.SELL)
        c.account = replace(c.account, positions=(c.d.m.Position("005930", 2, D("200"), D("0")),), account_exposure=D("200"))
    c.intent = replace(c.intent, client_order_id=client_id)
    c.account = replace(c.account, available_cash=D(cash))
    service = a.v.OrderService(a.s.OrderStore.open(path), clock=lambda: NOW, kill_switch=lambda: False)
    def send(dispatch):
        with open(marker, "a") as output:
            output.write(dispatch.order_id + "\n")
        if crash:
            os._exit(23)
        return ack(dispatch)
    start.wait(10)
    result = service.submit(c.intent, context=lambda: context(c), send=send)
    queue.put(result.state)
