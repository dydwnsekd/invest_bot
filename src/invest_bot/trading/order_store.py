"""Explicit, local SQLite ledger for synthetic virtual orders only.

Bootstrap and reopen are separate operations. The seal detects accidental loss
or edits; it is not authentication against an operator able to replace/seal a
database. All participants must use this file and the cooperating service.
"""
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
import fcntl
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import stat
from urllib.parse import quote
import uuid

from .models import AccountBinding, ReasonCode, Reservation, ReservationBook, RiskDecision, Side, valid_id
from ..risk.order_validation import _binding_valid


class LedgerUnavailable(RuntimeError):
    """No dispatch may follow an unsuccessful ledger operation."""


class SenderActive(RuntimeError):
    """A cooperating synchronous sender still owns the liveness barrier."""


@dataclass(frozen=True, slots=True)
class LedgerOrder:
    order_id: str | None
    state: str
    decision: RiskDecision
    fingerprint: str | None
    client_order_id: str | None = None
    account_binding_id: str | None = None
    binding_version: str | None = None
    evaluated_at: datetime | None = None
    broker_order_id: str | None = None
    reserved_cash: Decimal = Decimal(0)
    reserved_qty: int = 0
    reserved_exposure: Decimal = Decimal(0)
    remaining_qty: int = 0
    cumulative_qty: int = 0
    cumulative_notional: Decimal = Decimal(0)
    execution_target: str = "dry_run"


SCHEMA = {
    "meta": "CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)",
    "bindings": "CREATE TABLE bindings (alias TEXT PRIMARY KEY, binding_id TEXT NOT NULL UNIQUE, version TEXT NOT NULL, mode TEXT NOT NULL CHECK(mode='mock'), target TEXT NOT NULL CHECK(target='dry_run'))",
    "orders": "CREATE TABLE orders (order_id TEXT PRIMARY KEY, scope TEXT NOT NULL UNIQUE, binding_id TEXT REFERENCES bindings(binding_id), state TEXT NOT NULL, sender_active INTEGER NOT NULL CHECK(sender_active IN (0,1)), payload TEXT NOT NULL)",
    "captures": "CREATE TABLE captures (binding_id TEXT NOT NULL REFERENCES bindings(binding_id), version TEXT NOT NULL, digest TEXT NOT NULL, captured_at TEXT NOT NULL, watermark INTEGER NOT NULL, PRIMARY KEY(binding_id,version))",
    "events": "CREATE TABLE events (event_key TEXT PRIMARY KEY, order_id TEXT NOT NULL REFERENCES orders(order_id), binding_id TEXT NOT NULL REFERENCES bindings(binding_id), event_id TEXT NOT NULL, digest TEXT NOT NULL, revision INTEGER NOT NULL, filled INTEGER NOT NULL CHECK(filled IN (0,1)), payload TEXT NOT NULL)",
    "audits": "CREATE TABLE audits (revision INTEGER PRIMARY KEY, order_id TEXT NOT NULL REFERENCES orders(order_id), action TEXT NOT NULL, at TEXT, proof_digest TEXT)",
}
APPLICATION_ID = 0x49424F31


def encode(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=True, separators=(",", ":"))


def digest(value):
    return hashlib.sha256(encode(value).encode("ascii")).hexdigest()


def decision_data(result):
    return dict(allowed=result.allowed, reasons=[r.value for r in result.reasons],
                policy_version=result.policy_version, account_version=result.account_version,
                market_version=result.market_version, fingerprint=result.fingerprint,
                reserve_cash=str(result.reserve_cash), reserve_qty=result.reserve_qty,
                reserve_exposure=str(result.reserve_exposure), book_revision=result.book_revision)


def record(row):
    data = json.loads(row["payload"])
    risk = dict(data["decision"])
    risk["reasons"] = tuple(ReasonCode(r) for r in risk["reasons"])
    for key in ("reserve_cash", "reserve_exposure"):
        risk[key] = Decimal(risk[key])
    return LedgerOrder(
        row["order_id"], row["state"], RiskDecision(**risk), data["fingerprint"],
        data["client_order_id"], row["binding_id"], data["binding_version"],
        datetime.fromisoformat(data["evaluated_at"]) if data["evaluated_at"] else None,
        data["broker_order_id"], Decimal(data["reserved_cash"]), data["reserved_qty"],
        Decimal(data["reserved_exposure"]), data["remaining_qty"], data["cumulative_qty"],
        Decimal(data["cumulative_notional"]),
    )


class OrderStore:
    """One immutable registry, book and ledger identity per explicit file.

    Each operation verifies schema, SQLite integrity and the complete logical
    seal in a single snapshot. No opening path creates, migrates or repairs DBs.
    """

    def __init__(self, path, identity):
        self.path, self._identity, self._ledger_id = path, identity, None
        self.barrier_path = path.with_name(path.name + ".sender-lock")

    @classmethod
    def bootstrap(cls, path, *, book_id, bindings):
        if (not valid_id(book_id) or type(bindings) is not tuple or not bindings
                or not all(_binding_valid(b) for b in bindings)
                or len({b.alias for b in bindings}) != len(bindings)
                or len({b.binding_id for b in bindings}) != len(bindings)):
            raise LedgerUnavailable("invalid virtual ledger bootstrap")
        path = Path(path).absolute()
        try:
            fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o600)
            os.close(fd)
            store = cls(path, cls._file_identity(path))
            con = store._connect()
            try:
                con.execute("BEGIN IMMEDIATE")
                for statement in SCHEMA.values():
                    con.execute(statement)
                con.execute(f"PRAGMA application_id={APPLICATION_ID}")
                con.execute("PRAGMA user_version=1")
                ledger_id = uuid.uuid4().hex
                lock_fd = os.open(store.barrier_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o600)
                try:
                    os.write(lock_fd, ledger_id.encode("ascii"))
                    os.fsync(lock_fd)
                    lock_info = os.fstat(lock_fd)
                finally:
                    os.close(lock_fd)
                values = dict(schema="1", book_id=book_id, ledger_id=ledger_id, revision="0", seal="",
                              barrier_identity=encode([lock_info.st_dev, lock_info.st_ino]))
                con.executemany("INSERT INTO meta VALUES (?,?)", values.items())
                con.executemany("INSERT INTO bindings VALUES (?,?,?,?,?)", [
                    (b.alias, b.binding_id, b.version, b.mode, b.execution_target) for b in bindings])
                store._seal(con)
                store._commit(con)
            finally:
                con.close()
            return cls.open(path)
        except Exception:
            # A failed bootstrap leaves the explicit path for operator review.
            raise LedgerUnavailable("virtual ledger bootstrap failed") from None

    @classmethod
    def open(cls, path):
        try:
            path = Path(path).absolute()
            store = cls(path, cls._file_identity(path))
            with store.transaction() as con:
                store._ledger_id = store._meta(con, "ledger_id")
            return store
        except Exception:
            raise LedgerUnavailable("virtual ledger cannot be opened") from None

    @staticmethod
    def _file_identity(path):
        info = path.lstat()
        if not stat.S_ISREG(info.st_mode):
            raise LedgerUnavailable("ledger must be a regular file")
        return info.st_dev, info.st_ino

    def _check_identity(self):
        if self._file_identity(self.path) != self._identity:
            raise LedgerUnavailable("ledger identity changed")

    def _connect(self):
        self._check_identity()
        con = sqlite3.connect("file:" + quote(str(self.path), safe="/") + "?mode=rw",
                              uri=True, timeout=5, isolation_level=None)
        con.row_factory = sqlite3.Row
        try:
            con.execute("PRAGMA foreign_keys=ON")
            con.execute("PRAGMA synchronous=FULL")
            self._check_identity()
            return con
        except Exception:
            con.close()
            raise

    @staticmethod
    def _meta(con, key):
        return con.execute("SELECT value FROM meta WHERE key=?", (key,)).fetchone()[0]

    @staticmethod
    def _logical_digest(con):
        result = {}
        for table in sorted(SCHEMA):
            rows = [list(row) for row in con.execute(f"SELECT * FROM {table}")]
            if table == "meta":
                rows = [row for row in rows if row[0] != "seal"]
            result[table] = sorted(rows, key=encode)
        return digest(result)

    def _verify(self, con):
        actual = {row["name"]: row["sql"] for row in con.execute(
            "SELECT name,sql FROM sqlite_master WHERE name NOT LIKE 'sqlite_autoindex_%'")}
        if actual != SCHEMA or con.execute("PRAGMA application_id").fetchone()[0] != APPLICATION_ID:
            raise LedgerUnavailable("ledger schema mismatch")
        if con.execute("PRAGMA user_version").fetchone()[0] != 1:
            raise LedgerUnavailable("ledger version mismatch")
        if [row[0] for row in con.execute("PRAGMA quick_check")] != ["ok"] or con.execute("PRAGMA foreign_key_check").fetchone():
            raise LedgerUnavailable("ledger integrity failure")
        meta = dict(con.execute("SELECT * FROM meta"))
        if (set(meta) != {"schema", "book_id", "ledger_id", "revision", "seal", "barrier_identity"}
                or meta["schema"] != "1" or not valid_id(meta["book_id"]) or not valid_id(meta["ledger_id"])
                or (self._ledger_id is not None and meta["ledger_id"] != self._ledger_id)
                or meta["seal"] != self._logical_digest(con)):
            raise LedgerUnavailable("ledger state mismatch")
        if (encode(self._file_identity(self.barrier_path)) != meta["barrier_identity"]
                or self.barrier_path.read_bytes() != meta["ledger_id"].encode("ascii")):
            raise LedgerUnavailable("sender barrier identity changed")
        revision = int(meta["revision"])
        if revision < 0 or [r[0] for r in con.execute("SELECT revision FROM audits ORDER BY revision")] != list(range(1, revision + 1)):
            raise LedgerUnavailable("ledger audit gap")

    def _seal(self, con):
        con.execute("UPDATE meta SET value=? WHERE key='seal'", (self._logical_digest(con),))

    def _commit(self, con):
        con.commit()

    @contextmanager
    def transaction(self, *, write=False):
        con = None
        try:
            con = self._connect()
            con.execute("BEGIN IMMEDIATE" if write else "BEGIN")
            self._verify(con)
            yield con
            self._check_identity()
            if write:
                self._seal(con)
                self._commit(con)
            else:
                con.commit()
        except Exception as error:
            if con is not None:
                try:
                    con.rollback()
                except sqlite3.Error:
                    pass
            # Domain evidence errors must remain fixed-code errors to callers.
            if getattr(type(error), "_ledger_domain_error", False):
                raise
            raise LedgerUnavailable("virtual ledger operation failed") from None
        finally:
            if con is not None:
                con.close()

    @contextmanager
    def sender_barrier(self, *, exclusive=False):
        fd = None
        try:
            self._check_identity()
            # A separate inode avoids flock/SQLite byte-lock interference on BSD.
            # It is created only by bootstrap and pinned in the sealed metadata.
            lock_identity = self._file_identity(self.barrier_path)
            fd = os.open(self.barrier_path, os.O_RDONLY | os.O_NOFOLLOW)
            if (os.fstat(fd).st_dev, os.fstat(fd).st_ino) != lock_identity:
                raise LedgerUnavailable("ledger identity changed")
            try:
                fcntl.flock(fd, (fcntl.LOCK_EX | fcntl.LOCK_NB) if exclusive else fcntl.LOCK_SH)
            except BlockingIOError:
                raise SenderActive("synchronous sender is active") from None
            yield
        except (SenderActive, LedgerUnavailable):
            raise
        except Exception as error:
            if getattr(type(error), "_ledger_domain_error", False):
                raise
            raise LedgerUnavailable("sender barrier failed") from None
        finally:
            if fd is not None:
                os.close(fd)

    @staticmethod
    def _find(con, order_id):
        return con.execute("SELECT * FROM orders WHERE order_id=?", (order_id,)).fetchone()

    def get(self, order_id):
        with self.transaction() as con:
            row = self._find(con, order_id)
            return record(row) if row else None

    def orders(self):
        with self.transaction() as con:
            return tuple(record(row) for row in con.execute("SELECT * FROM orders ORDER BY order_id"))

    def _book(self, con):
        entries = []
        for row in con.execute("SELECT * FROM orders ORDER BY order_id"):
            data = json.loads(row["payload"])
            if data["remaining_qty"] and data["reservation_sequence"]:
                entries.append(Reservation(row["order_id"], row["binding_id"], data["symbol"], Side(data["side"]),
                                           Decimal(data["reserved_cash"]), data["reserved_qty"],
                                           Decimal(data["reserved_exposure"]), data["reservation_sequence"]))
        return ReservationBook(self._meta(con, "book_id"), int(self._meta(con, "revision")), tuple(entries))

    def book(self):
        with self.transaction() as con:
            return self._book(con)

    def _audit(self, con, order_id, action, at, proof_digest=None):
        revision = int(self._meta(con, "revision")) + 1
        con.execute("UPDATE meta SET value=? WHERE key='revision'", (str(revision),))
        con.execute("INSERT INTO audits VALUES (?,?,?,?,?)", (revision, order_id, action, at, proof_digest))
        return revision

    @staticmethod
    def _binding(con, alias):
        row = con.execute("SELECT * FROM bindings WHERE alias=?", (alias,)).fetchone()
        return AccountBinding(row["alias"], row["binding_id"], row["version"], row["mode"], row["target"]) if row else None

    @staticmethod
    def _update(con, order_id, state, active, data):
        con.execute("UPDATE orders SET state=?,sender_active=?,payload=? WHERE order_id=?",
                    (state, int(active), encode(data), order_id))
