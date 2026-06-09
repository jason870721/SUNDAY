"""Local durable state — a single SQLite file (milestone-6).

The proxy is almost stateless: the exchange is the source of truth for the book,
mainnet for market data. The only thing Sunday must remember across restarts is
**alerts** (req 6) plus a little monitor config (req 5). So Postgres + Redis are
gone; this is stdlib ``sqlite3``, one file, created on boot.

Concurrency (load-bearing): FastAPI serves sync endpoints from a threadpool, so the
one connection is shared across threads (``check_same_thread=False``). A single
SQLite connection is NOT safe for concurrent use, and concurrent writers deadlock /
raise "database is locked". So **every** access — reads included — is serialized
through one write mutex ``_LOCK``. It is a ``RLock`` (reentrant) on purpose: a write
helper such as ``create_alert`` re-reads via ``get_alert`` while still holding the
lock, which a plain ``Lock`` would self-deadlock on. WAL + ``busy_timeout`` add a
second line of defence (readers never block the writer; contention waits, not errors).

``connect(path)`` takes the path explicitly (rather than importing config) so the
alert/monitor logic stays unit-testable against ``:memory:``.
"""

from __future__ import annotations

import sqlite3
import threading
from datetime import datetime, timezone

_conn: sqlite3.Connection | None = None
_LOCK = threading.RLock()  # reentrant write mutex — serializes ALL connection access

_SCHEMA = """
CREATE TABLE IF NOT EXISTS alerts (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol          TEXT NOT NULL,
    kind            TEXT NOT NULL,          -- price_above | price_below | pct_move
    threshold       REAL NOT NULL,          -- price (above/below) or |pct| (pct_move)
    ref_price       REAL,                   -- pct_move: price captured at creation
    note            TEXT,
    status          TEXT NOT NULL DEFAULT 'active',  -- active | triggered
    created_at      TEXT NOT NULL,
    triggered_at    TEXT,
    triggered_price REAL
);
CREATE INDEX IF NOT EXISTS idx_alerts_active ON alerts (symbol) WHERE status = 'active';

CREATE TABLE IF NOT EXISTS kv (
    k TEXT PRIMARY KEY,
    v TEXT
);

-- Order journal (req): the agent's rationale ("memo") + the exact params for every
-- order it places, so the position query can join it back and show the User WHY.
CREATE TABLE IF NOT EXISTS order_log (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    ts           TEXT NOT NULL,
    symbol       TEXT NOT NULL,
    order_id     TEXT,
    side         TEXT,
    type         TEXT,
    qty          REAL,
    notional_usd REAL,
    price        REAL,
    leverage     INTEGER,
    margin_mode  TEXT,
    reduce_only  INTEGER,        -- 0 / 1
    take_profit  REAL,
    stop_loss    REAL,
    memo         VARCHAR(300)    -- length enforced at the API layer (sqlite ignores it)
);
CREATE INDEX IF NOT EXISTS idx_order_log_symbol ON order_log (symbol, id DESC);

-- Work journal (req): the reviewer's daily reports, persisted so the User can read
-- the team's work log in the dashboard. Body is markdown; `date` is the logical
-- report day (a report may be written just after midnight for the prior session).
CREATE TABLE IF NOT EXISTS journal (
    id     INTEGER PRIMARY KEY AUTOINCREMENT,
    ts     TEXT NOT NULL,                       -- created (server UTC, ISO)
    date   TEXT,                                -- logical report date (YYYY-MM-DD)
    author TEXT NOT NULL DEFAULT 'reviewer',
    title  TEXT,
    body   TEXT NOT NULL                        -- markdown report
);
CREATE INDEX IF NOT EXISTS idx_journal_recent ON journal (id DESC);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def connect(path: str) -> None:
    global _conn
    with _LOCK:
        _conn = sqlite3.connect(path, check_same_thread=False)
        _conn.row_factory = sqlite3.Row
        _conn.execute("PRAGMA journal_mode=WAL")    # readers don't block the single writer
        _conn.execute("PRAGMA busy_timeout=5000")   # wait up to 5s on contention, don't error
        _conn.executescript(_SCHEMA)
        _conn.commit()


def close() -> None:
    global _conn
    with _LOCK:
        if _conn is not None:
            _conn.close()
            _conn = None


def _db() -> sqlite3.Connection:
    if _conn is None:
        raise RuntimeError("store not connected — call connect() first")
    return _conn


# --------------------------------------------------------------------------
# Alerts (req 6)
# --------------------------------------------------------------------------

def create_alert(symbol: str, kind: str, threshold: float,
                 ref_price: float | None = None, note: str | None = None) -> dict:
    with _LOCK:
        cur = _db().execute(
            "INSERT INTO alerts (symbol, kind, threshold, ref_price, note, status, created_at) "
            "VALUES (?,?,?,?,?, 'active', ?)",
            (symbol, kind, threshold, ref_price, note, _now()),
        )
        _db().commit()
        return get_alert(cur.lastrowid)  # reentrant: still inside _LOCK


def get_alert(alert_id: int) -> dict | None:
    with _LOCK:
        row = _db().execute("SELECT * FROM alerts WHERE id = ?", (alert_id,)).fetchone()
        return dict(row) if row else None


def list_alerts(status: str | None = None) -> list[dict]:
    with _LOCK:
        if status:
            rows = _db().execute(
                "SELECT * FROM alerts WHERE status = ? ORDER BY id DESC", (status,)).fetchall()
        else:
            rows = _db().execute("SELECT * FROM alerts ORDER BY id DESC").fetchall()
        return [dict(r) for r in rows]


def active_alerts() -> list[dict]:
    """Alerts the realtime engine must still evaluate."""
    return list_alerts(status="active")


def delete_alert(alert_id: int) -> bool:
    with _LOCK:
        cur = _db().execute("DELETE FROM alerts WHERE id = ?", (alert_id,))
        _db().commit()
        return cur.rowcount > 0


def mark_triggered(alert_id: int, price: float) -> None:
    with _LOCK:
        _db().execute(
            "UPDATE alerts SET status='triggered', triggered_at=?, triggered_price=? WHERE id=?",
            (_now(), price, alert_id),
        )
        _db().commit()


# --------------------------------------------------------------------------
# kv — small monitor/config flags
# --------------------------------------------------------------------------

def kv_get(k: str, default: str | None = None) -> str | None:
    with _LOCK:
        row = _db().execute("SELECT v FROM kv WHERE k = ?", (k,)).fetchone()
        return row["v"] if row else default


def kv_set(k: str, v: str) -> None:
    with _LOCK:
        _db().execute(
            "INSERT INTO kv (k, v) VALUES (?, ?) ON CONFLICT(k) DO UPDATE SET v = excluded.v",
            (k, v),
        )
        _db().commit()


# --------------------------------------------------------------------------
# Order journal — agent rationale + params per order (req)
# --------------------------------------------------------------------------

def record_order(symbol: str, order_id: str | None, memo: str | None, order: dict) -> None:
    """Log an order's params (one column each) + the agent's memo (req)."""
    with _LOCK:
        _db().execute(
            "INSERT INTO order_log (ts, symbol, order_id, side, type, qty, notional_usd, price, "
            "leverage, margin_mode, reduce_only, take_profit, stop_loss, memo) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (_now(), symbol, str(order_id) if order_id is not None else None,
             order.get("side"), order.get("type"), order.get("qty"), order.get("notional_usd"),
             order.get("price"), order.get("leverage"), order.get("margin_mode"),
             1 if order.get("reduce_only") else 0, order.get("take_profit"), order.get("stop_loss"),
             memo),
        )
        _db().commit()


def latest_order(symbol: str) -> dict | None:
    """The most recent logged order for a symbol (memo + params) — what the position
    query joins to surface the agent's rationale to the User."""
    with _LOCK:
        row = _db().execute(
            "SELECT * FROM order_log WHERE symbol = ? ORDER BY id DESC LIMIT 1", (symbol,)).fetchone()
    if not row:
        return None
    d = dict(row)
    d["reduce_only"] = bool(d.get("reduce_only"))
    return d


# --------------------------------------------------------------------------
# Work journal — reviewer's daily reports, shown to the User (req)
# --------------------------------------------------------------------------

def add_journal(body: str, title: str | None = None,
                date: str | None = None, author: str | None = "reviewer") -> dict:
    """Persist one work-log entry (markdown body). `date` defaults to today (UTC)."""
    with _LOCK:
        cur = _db().execute(
            "INSERT INTO journal (ts, date, author, title, body) VALUES (?,?,?,?,?)",
            (_now(), date or _now()[:10], author or "reviewer", title, body),
        )
        _db().commit()
        return get_journal(cur.lastrowid)  # reentrant: still inside _LOCK


def get_journal(entry_id: int) -> dict | None:
    with _LOCK:
        row = _db().execute("SELECT * FROM journal WHERE id = ?", (entry_id,)).fetchone()
        return dict(row) if row else None


def list_journal(author: str | None = None) -> list[dict]:
    """All work-log entries newest-first (optionally one author), for the paged UI."""
    with _LOCK:
        if author:
            rows = _db().execute(
                "SELECT * FROM journal WHERE author = ? ORDER BY id DESC", (author,)).fetchall()
        else:
            rows = _db().execute("SELECT * FROM journal ORDER BY id DESC").fetchall()
        return [dict(r) for r in rows]
