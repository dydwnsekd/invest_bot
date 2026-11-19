"""Explicit synthetic policy/data, using the normal public module paths."""
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from importlib import import_module
from types import SimpleNamespace

NOW = datetime(2026, 11, 18, 3, tzinfo=UTC)
D = Decimal


def domain():
    return SimpleNamespace(
        m=import_module("invest_bot.trading.models"),
        v=import_module("invest_bot.risk.order_validation"),
        dry=import_module("invest_bot.trading.dry_run"),
    )


def case():
    d = domain()
    binding = d.m.AccountBinding("paper", "binding-a", "binding-v1", "mock", "dry_run")
    intent = d.m.OrderIntent(
        1, "order-1", "dry_run", "mock", "paper", "binding-a", "binding-v1",
        "005930", d.m.Side.BUY, 2, D("100"), "KRW", "domestic_stock", "LIMIT", "signal-1",
        NOW - timedelta(seconds=1), NOW + timedelta(seconds=10),
    )
    policy = d.m.RiskPolicy(
        "policy-v1", "dry_run", "mock", frozenset({"005930", "000660"}),
        frozenset({"domestic_stock"}), frozenset({"virtual-open"}),
        D("1000"), D("2000"), D("3000"), D("100"), 5,
        D("0.01"), D("0.02"), D("0"), D("0"), D("1"),
        timedelta(seconds=20), timedelta(seconds=30), timedelta(seconds=10),
        timedelta(seconds=10), timedelta(seconds=10),
    )
    account = d.m.AccountSnapshot(
        "account-v1", "dry_run", "mock", "paper", "binding-a", "binding-v1", "KRW", NOW,
        True, True, D("1000"), (), D("0"), 0, NOW, "virtual-mark-v1", "book-a", 0, frozenset(),
    )
    market = d.m.MarketSnapshot(
        "market-v1", "dry_run", "mock", "005930", "domestic_stock", "KRW", NOW,
        True, True, "virtual-open", "virtual-calendar", "calendar-v1", D("1"), D("1"), D("1000"),
    )
    book = d.m.ReservationBook("book-a", 0, ())
    return SimpleNamespace(d=d, binding=binding, intent=intent, policy=policy, account=account, market=market, book=book)


def validate(c, **changes):
    args = dict(intent=c.intent, binding=c.binding, policy=c.policy, account=c.account, market=c.market, book=c.book, now=NOW)
    args.update(changes)
    return c.d.v.validate_order(**args)


def broker(c, outcomes=None):
    return c.d.dry.DryRunBroker(
        bindings=(c.binding,), book_id="book-a",
        outcomes=(c.d.m.VirtualOutcome.ACKNOWLEDGED,) if outcomes is None else outcomes,
    )


def execute(b, c, **changes):
    args = dict(intent=c.intent, policy=c.policy, account=c.account, market=c.market, now=NOW, received_at=NOW)
    args.update(changes)
    return b.execute(**args)
