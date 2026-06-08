"""Postgres pool + redis client + a tiny migration runner + the 1.0 DAO.

Runtime state (mode/rationale/heartbeat/regime) lives in redis; the trade ledger
(strategy_state/signals/orders/positions/risk_events/webhook_log) lives in postgres.
The exchange remains the source of truth for actual positions — these tables are
our attribution/audit record (modeling-grade).
"""

from __future__ import annotations

import json
import pathlib
import time

import redis
from psycopg.types.json import Jsonb
from psycopg_pool import ConnectionPool

from .config import settings

_MIGRATIONS_DIR = pathlib.Path(__file__).resolve().parent.parent / "migrations"

pool: ConnectionPool | None = None
rds: redis.Redis | None = None

_HEARTBEAT_KEY = "sunday:swarm_heartbeat_ts"


def connect() -> None:
    """Open the postgres pool and redis client. Idempotent."""
    global pool, rds
    if pool is None:
        pool = ConnectionPool(settings.database_url, min_size=1, max_size=8, open=False)
        pool.open(wait=True, timeout=10)
    if rds is None:
        rds = redis.Redis.from_url(settings.redis_url, decode_responses=True)
    rds.ping()


def close() -> None:
    global pool, rds
    if pool is not None:
        pool.close()
        pool = None
    if rds is not None:
        rds.close()
        rds = None


def run_migrations() -> list[str]:
    """Apply un-applied migrations/*.sql in filename order, once each."""
    assert pool is not None, "call connect() first"
    with pool.connection() as conn:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS schema_migrations ("
            " version TEXT PRIMARY KEY,"
            " applied_at TIMESTAMPTZ NOT NULL DEFAULT now())"
        )
        done = {row[0] for row in conn.execute("SELECT version FROM schema_migrations")}

    applied: list[str] = []
    for path in sorted(_MIGRATIONS_DIR.glob("*.sql")):
        if path.name in done:
            continue
        with pool.connection() as conn:  # one transaction per migration
            conn.execute(path.read_text())
            conn.execute("INSERT INTO schema_migrations (version) VALUES (%s)", (path.name,))
        applied.append(path.name)
    return applied


# --- runtime state (redis) -------------------------------------------------

def get_mode() -> str:
    return (rds.get("sunday:mode") if rds else None) or "active"


def set_mode(mode: str) -> None:
    if rds:
        rds.set("sunday:mode", mode)


def get_rationale() -> str | None:
    return rds.get("sunday:rationale") if rds else None


def set_rationale(text: str) -> None:
    if rds:
        rds.set("sunday:rationale", text)


def set_heartbeat() -> None:
    if rds:
        rds.set("sunday:heartbeat_ts", time.time())


def heartbeat_age() -> float | None:
    """Seconds since the last swarm heartbeat, or None if never seen."""
    v = rds.get("sunday:heartbeat_ts") if rds else None
    return (time.time() - float(v)) if v else None


def get_last_regime(symbol: str) -> str | None:
    return rds.get(f"sunday:last_regime:{symbol}") if rds else None


def set_last_regime(symbol: str, regime: str) -> None:
    if rds:
        rds.set(f"sunday:last_regime:{symbol}", regime)


def get_last_event_ts() -> str | None:
    return rds.get("sunday:last_event_ts") if rds else None


def set_last_event_ts(ts_iso: str) -> None:
    if rds:
        rds.set("sunday:last_event_ts", ts_iso)


def get_last_notable(symbol: str) -> str | None:
    """The last notable driver Sunday woke the desk on for this symbol (debounce)."""
    return rds.get(f"sunday:notable:{symbol}") if rds else None


def set_last_notable(symbol: str, driver: str | None) -> None:
    if not rds:
        return
    key = f"sunday:notable:{symbol}"
    if driver:
        rds.set(key, driver)
    else:
        rds.delete(key)


def get_or_set_first_prices(current: dict[str, float]) -> dict[str, float]:
    """First-seen price per symbol (set once), the buy-hold shadow's cost basis."""
    if not rds:
        return dict(current)
    key = "sunday:bh_first_prices"
    existing = rds.hgetall(key) or {}
    out: dict[str, float] = {}
    for sym, px in current.items():
        if sym in existing:
            out[sym] = float(existing[sym])
        else:
            rds.hset(key, sym, px)
            out[sym] = px
    return out


# --- strategy state --------------------------------------------------------

def set_strategy(symbol: str, strategy: str, reason: str, set_by: str) -> None:
    with pool.connection() as conn:
        conn.execute(
            "INSERT INTO strategy_state (symbol, strategy, reason, set_by) VALUES (%s,%s,%s,%s)",
            (symbol, strategy, reason, set_by),
        )


def current_strategy(symbol: str) -> str:
    with pool.connection() as conn:
        row = conn.execute(
            "SELECT strategy FROM strategy_state WHERE symbol=%s ORDER BY set_at DESC LIMIT 1",
            (symbol,),
        ).fetchone()
    return row[0] if row else "flat"


# --- risk envelope (the leader's /envelope lever; latest row = active caps) ----

def set_envelope(max_position_usd: float, max_total_exposure_usd: float, max_leverage: float,
                 max_drawdown_pct: float, stop_pct: float, reason: str | None, set_by: str) -> None:
    with pool.connection() as conn:
        conn.execute(
            "INSERT INTO risk_envelope (max_position_usd, max_total_exposure_usd, max_leverage,"
            " max_drawdown_pct, stop_pct, reason, set_by) VALUES (%s,%s,%s,%s,%s,%s,%s)",
            (max_position_usd, max_total_exposure_usd, max_leverage, max_drawdown_pct, stop_pct, reason, set_by),
        )


def current_envelope() -> dict | None:
    """The active envelope (latest row), or None if none set yet (engine uses defaults)."""
    with pool.connection() as conn:
        row = conn.execute(
            "SELECT max_position_usd, max_total_exposure_usd, max_leverage, max_drawdown_pct, stop_pct"
            " FROM risk_envelope ORDER BY set_at DESC LIMIT 1"
        ).fetchone()
    if not row:
        return None
    return {"max_position_usd": float(row[0]), "max_total_exposure_usd": float(row[1]),
            "max_leverage": float(row[2]), "max_drawdown_pct": float(row[3]), "stop_pct": float(row[4])}


# --- thesis / outcome ledger (milestone-4 T3) ------------------------------

_THESIS_COLS = ("id, created_at, created_by, symbol, direction, conviction, horizon,"
                " invalidation, invalidation_price, evidence, rationale, status,"
                " closed_at, outcome_pnl, outcome_note")


def _thesis_row(r) -> dict:
    return {
        "id": int(r[0]), "created_at": r[1].isoformat(), "created_by": r[2], "symbol": r[3],
        "direction": r[4], "conviction": float(r[5]), "horizon": r[6],
        "invalidation": r[7], "invalidation_price": _num(r[8]), "evidence": r[9],
        "rationale": r[10], "status": r[11],
        "closed_at": r[12].isoformat() if r[12] else None,
        "outcome_pnl": _num(r[13]), "outcome_note": r[14],
    }


def set_thesis(symbol: str, direction: str, conviction: float, rationale: str, created_by: str,
               horizon: str | None = None, invalidation: str | None = None,
               invalidation_price: float | None = None, evidence=None) -> int:
    """Supersede the symbol's active thesis (if any) and insert a new active one. Returns id."""
    with pool.connection() as conn:
        conn.execute("UPDATE theses SET status='superseded', closed_at=now()"
                     " WHERE symbol=%s AND status='active'", (symbol,))
        row = conn.execute(
            "INSERT INTO theses (created_by, symbol, direction, conviction, horizon,"
            " invalidation, invalidation_price, evidence, rationale)"
            " VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id",
            (created_by, symbol, direction, conviction, horizon, invalidation,
             invalidation_price, Jsonb(evidence) if evidence is not None else None, rationale),
        ).fetchone()
    return int(row[0])


def current_thesis(symbol: str) -> dict | None:
    with pool.connection() as conn:
        row = conn.execute(
            f"SELECT {_THESIS_COLS} FROM theses WHERE symbol=%s AND status='active'"
            " ORDER BY created_at DESC LIMIT 1", (symbol,)).fetchone()
    return _thesis_row(row) if row else None


def list_theses(since=None, limit: int = 100) -> list[dict]:
    with pool.connection() as conn:
        if since is not None:
            rows = conn.execute(f"SELECT {_THESIS_COLS} FROM theses WHERE created_at >= %s"
                                " ORDER BY created_at DESC LIMIT %s", (since, limit)).fetchall()
        else:
            rows = conn.execute(f"SELECT {_THESIS_COLS} FROM theses ORDER BY created_at DESC LIMIT %s",
                                (limit,)).fetchall()
    return [_thesis_row(r) for r in rows]


def close_thesis(thesis_id: int, status: str, outcome_pnl: float | None = None,
                 outcome_note: str | None = None) -> None:
    """Mark a thesis closed/invalidated/superseded + persist its outcome (attribution)."""
    with pool.connection() as conn:
        conn.execute("UPDATE theses SET status=%s, closed_at=now(),"
                     " outcome_pnl=COALESCE(%s, outcome_pnl), outcome_note=COALESCE(%s, outcome_note)"
                     " WHERE id=%s", (status, outcome_pnl, outcome_note, thesis_id))


# --- ledger ----------------------------------------------------------------

def record_signal(symbol: str, strategy: str, indicators: dict, action: str) -> None:
    with pool.connection() as conn:
        conn.execute(
            "INSERT INTO signals (symbol, strategy, indicators_json, action) VALUES (%s,%s,%s,%s)",
            (symbol, strategy, Jsonb(indicators), action),
        )


def record_order(
    symbol: str, side: str, type_: str, qty: float, price: float | None,
    status: str, exchange_order_id: str | None, strategy: str, intent: str | None,
) -> None:
    with pool.connection() as conn:
        conn.execute(
            "INSERT INTO orders (symbol, side, type, qty, price, status, exchange_order_id, strategy, intent)"
            " VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)",
            (symbol, side, type_, qty, price, status, exchange_order_id, strategy, intent),
        )


def record_position_open(
    symbol: str, side: str, qty: float, entry: float, stop: float | None,
    strategy: str, entry_reason: str | None, thesis_id: int | None = None,
) -> None:
    with pool.connection() as conn:
        conn.execute(
            "INSERT INTO positions (symbol, side, qty, entry_price, stop_price, strategy, entry_reason, thesis_id)"
            " VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
            (symbol, side, qty, entry, stop, strategy, entry_reason, thesis_id),
        )


def close_open_positions(symbol: str, realized_pnl: float | None = None) -> None:
    """Mark open rows closed; persist realized_pnl (for per-strategy attribution).

    realized_pnl is captured by the caller from the position's unrealizedPnl the
    instant before closing — the accurate proxy ccxt gives us on testnet without
    fill-by-fill reconciliation. 1.0/1.1 hold ≤1 open row per symbol, so the
    single captured value maps cleanly onto the row.
    """
    with pool.connection() as conn:
        conn.execute(
            "UPDATE positions SET closed_at=now(), realized_pnl=COALESCE(%s, realized_pnl)"
            " WHERE symbol=%s AND closed_at IS NULL",
            (realized_pnl, symbol),
        )


def record_risk_event(type_: str, detail: dict, action_taken: str) -> None:
    with pool.connection() as conn:
        conn.execute(
            "INSERT INTO risk_events (type, detail, action_taken) VALUES (%s,%s,%s)",
            (type_, Jsonb(detail), action_taken),
        )


def record_webhook(
    event_type: str, to_member: str, title: str | None, body: str | None,
    http_status: int | None, message_id: str | None,
) -> None:
    with pool.connection() as conn:
        conn.execute(
            "INSERT INTO webhook_log (event_type, to_member, title, body, http_status, message_id)"
            " VALUES (%s,%s,%s,%s,%s,%s)",
            (event_type, to_member, title, body, http_status, message_id),
        )


# --- dashboard data (milestone 2.0) ----------------------------------------

def record_pnl_snapshot(equity: float, realized: float, unrealized: float, drawdown_pct: float | None) -> None:
    """One point on the equity curve. Written by the watcher tick (skip on exchange error)."""
    with pool.connection() as conn:
        conn.execute(
            "INSERT INTO pnl_snapshots (equity, realized, unrealized, drawdown_pct) VALUES (%s,%s,%s,%s)",
            (equity, realized, unrealized, drawdown_pct),
        )


def equity_peak() -> float | None:
    """High-water equity over all snapshots (for drawdown_pct)."""
    with pool.connection() as conn:
        row = conn.execute("SELECT MAX(equity) FROM pnl_snapshots").fetchone()
    return float(row[0]) if row and row[0] is not None else None


def realized_total(since=None) -> float:
    """Cumulative realized PnL from closed positions (optionally since a datetime)."""
    with pool.connection() as conn:
        if since is not None:
            row = conn.execute(
                "SELECT COALESCE(SUM(realized_pnl),0) FROM positions"
                " WHERE closed_at IS NOT NULL AND closed_at >= %s",
                (since,),
            ).fetchone()
        else:
            row = conn.execute(
                "SELECT COALESCE(SUM(realized_pnl),0) FROM positions WHERE closed_at IS NOT NULL"
            ).fetchone()
    return float(row[0] or 0)


def open_positions_meta_map() -> dict[str, dict]:
    """symbol -> latest open position's {strategy, entry_reason, stop_price} (for /positions join)."""
    with pool.connection() as conn:
        rows = conn.execute(
            "SELECT DISTINCT ON (symbol) symbol, strategy, entry_reason, stop_price"
            " FROM positions WHERE closed_at IS NULL ORDER BY symbol, opened_at DESC"
        ).fetchall()
    return {
        r[0]: {
            "strategy": r[1],
            "entry_reason": r[2],
            "stop_price": float(r[3]) if r[3] is not None else None,
        }
        for r in rows
    }


# --- commentary (analyst's User-facing market notes; harmless write) -------

def record_commentary(author: str, title: str | None, body: str) -> int:
    with pool.connection() as conn:
        row = conn.execute(
            "INSERT INTO commentary (author, title, body) VALUES (%s,%s,%s) RETURNING id",
            (author, title, body),
        ).fetchone()
    return int(row[0])


def list_commentary(since=None, limit: int = 50) -> list[dict]:
    with pool.connection() as conn:
        if since is not None:
            rows = conn.execute(
                "SELECT ts, author, title, body FROM commentary WHERE ts >= %s ORDER BY ts DESC LIMIT %s",
                (since, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT ts, author, title, body FROM commentary ORDER BY ts DESC LIMIT %s",
                (limit,),
            ).fetchall()
    return [{"ts": r[0].isoformat(), "author": r[1], "title": r[2], "body": r[3]} for r in rows]


# --- dashboard read aggregations (milestone 2.0 / T2) ----------------------

def equity_curve(since=None) -> list[list]:
    """[[ts_ms, equity], ...] from pnl_snapshots, oldest first."""
    with pool.connection() as conn:
        if since is not None:
            rows = conn.execute(
                "SELECT EXTRACT(EPOCH FROM ts)*1000, equity FROM pnl_snapshots"
                " WHERE ts >= %s ORDER BY ts",
                (since,),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT EXTRACT(EPOCH FROM ts)*1000, equity FROM pnl_snapshots ORDER BY ts"
            ).fetchall()
    return [[int(r[0]), float(r[1])] for r in rows]


def performance(since=None) -> list[dict]:
    """Per-strategy attribution from closed positions (+ open_qty from open ones)."""
    clause = "AND closed_at >= %s" if since is not None else ""
    params = (since,) if since is not None else ()
    with pool.connection() as conn:
        closed = conn.execute(
            "SELECT strategy, COALESCE(SUM(realized_pnl),0), COUNT(*),"
            " COUNT(*) FILTER (WHERE realized_pnl > 0), AVG(realized_pnl)"
            f" FROM positions WHERE closed_at IS NOT NULL {clause} GROUP BY strategy",
            params,
        ).fetchall()
        open_rows = conn.execute(
            "SELECT strategy, COALESCE(SUM(qty),0) FROM positions"
            " WHERE closed_at IS NULL GROUP BY strategy"
        ).fetchall()
    open_qty = {r[0]: float(r[1]) for r in open_rows}
    out, seen = [], set()
    for strat, realized, n, wins, avg in closed:
        seen.add(strat)
        out.append({
            "strategy": strat,
            "realized_pnl": round(float(realized), 4),
            "n_trades": int(n),
            "win_rate": round(wins / n, 4) if n else 0.0,
            "avg_pnl": round(float(avg), 4) if avg is not None else 0.0,
            "open_qty": open_qty.get(strat, 0.0),
        })
    for strat, qty in open_qty.items():  # strategies with only open (no closed) trades
        if strat not in seen:
            out.append({"strategy": strat, "realized_pnl": 0.0, "n_trades": 0,
                        "win_rate": 0.0, "avg_pnl": 0.0, "open_qty": qty})
    return out


def strategy_history(since=None) -> list[dict]:
    """strategy_state timeline (for the equity-curve switch overlay), oldest first."""
    with pool.connection() as conn:
        if since is not None:
            rows = conn.execute(
                "SELECT EXTRACT(EPOCH FROM set_at)*1000, symbol, strategy, reason, set_by"
                " FROM strategy_state WHERE set_at >= %s ORDER BY set_at",
                (since,),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT EXTRACT(EPOCH FROM set_at)*1000, symbol, strategy, reason, set_by"
                " FROM strategy_state ORDER BY set_at"
            ).fetchall()
    return [
        {"set_at_ms": int(r[0]), "symbol": r[1], "strategy": r[2], "reason": r[3], "set_by": r[4]}
        for r in rows
    ]


# --- audit reads (User dashboard: /risk, /trades, /events) -----------------
# Pure SELECTs over tables we already write — no new data logic, just exposing
# the captured audit trail (risk_events / orders / webhook_log) to the operator.

def latest_pnl_snapshot() -> dict | None:
    """Most recent equity-curve point (lets /risk render equity+drawdown offline)."""
    with pool.connection() as conn:
        row = conn.execute(
            "SELECT ts, equity, realized, unrealized, drawdown_pct FROM pnl_snapshots"
            " ORDER BY ts DESC LIMIT 1"
        ).fetchone()
    if not row:
        return None
    return {"ts": row[0].isoformat(), "equity": float(row[1]), "realized": float(row[2]),
            "unrealized": float(row[3]), "drawdown_pct": float(row[4]) if row[4] is not None else None}


def recent_risk_events(limit: int = 50) -> list[dict]:
    """Deterministic-fuse log (size_cap / exposure_cap / leverage_cap / drawdown), newest first."""
    with pool.connection() as conn:
        rows = conn.execute(
            "SELECT ts, type, detail, action_taken FROM risk_events ORDER BY ts DESC LIMIT %s",
            (limit,),
        ).fetchall()
    return [{"ts": r[0].isoformat(), "type": r[1], "detail": r[2], "action_taken": r[3]} for r in rows]


def recent_orders(since=None, limit: int = 100) -> list[dict]:
    """Order ledger / blotter (the /trades feed), newest first."""
    with pool.connection() as conn:
        if since is not None:
            rows = conn.execute(
                "SELECT ts, symbol, side, type, qty, price, status, strategy, intent FROM orders"
                " WHERE ts >= %s ORDER BY ts DESC LIMIT %s",
                (since, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT ts, symbol, side, type, qty, price, status, strategy, intent FROM orders"
                " ORDER BY ts DESC LIMIT %s",
                (limit,),
            ).fetchall()
    return [{"ts": r[0].isoformat(), "symbol": r[1], "side": r[2], "type": r[3],
             "qty": float(r[4]), "price": float(r[5]) if r[5] is not None else None,
             "status": r[6], "strategy": r[7], "intent": r[8]} for r in rows]


def _num(x):
    return float(x) if x is not None else None


# --- information layer (milestone-4 T1: perp_metrics) ----------------------

_METRIC_COLS = ("funding_rate", "funding_annual_pct", "open_interest",
                "long_short_ratio", "basis_bps", "liq_long_usd", "liq_short_usd")


def record_perp_metrics(m: dict) -> None:
    """Persist one perp_metrics row (m has 'symbol' + the metric columns)."""
    with pool.connection() as conn:
        conn.execute(
            "INSERT INTO perp_metrics (symbol, funding_rate, funding_annual_pct, open_interest,"
            " long_short_ratio, basis_bps, liq_long_usd, liq_short_usd)"
            " VALUES (%(symbol)s,%(funding_rate)s,%(funding_annual_pct)s,%(open_interest)s,"
            " %(long_short_ratio)s,%(basis_bps)s,%(liq_long_usd)s,%(liq_short_usd)s)",
            m,
        )


def _metric_row(r) -> dict:
    d = {"symbol": r[0], "ts": r[1].isoformat()}
    for i, col in enumerate(_METRIC_COLS, start=2):
        d[col] = _num(r[i])
    return d


def latest_perp_metrics_all() -> dict[str, dict]:
    """symbol -> latest perp_metrics row (for the /desk basket panel)."""
    with pool.connection() as conn:
        rows = conn.execute(
            "SELECT DISTINCT ON (symbol) symbol, ts, funding_rate, funding_annual_pct, open_interest,"
            " long_short_ratio, basis_bps, liq_long_usd, liq_short_usd"
            " FROM perp_metrics ORDER BY symbol, ts DESC"
        ).fetchall()
    return {r[0]: _metric_row(r) for r in rows}


def record_shadow(baseline: str, equity: float) -> None:
    with pool.connection() as conn:
        conn.execute("INSERT INTO shadow_equity (baseline, equity) VALUES (%s,%s)", (baseline, equity))


def last_shadow_equity(baseline: str) -> float | None:
    with pool.connection() as conn:
        row = conn.execute("SELECT equity FROM shadow_equity WHERE baseline=%s ORDER BY ts DESC LIMIT 1",
                           (baseline,)).fetchone()
    return float(row[0]) if row else None


def shadow_curve(baseline: str, since=None) -> list[list]:
    """[[ts_ms, equity], ...] for a shadow baseline, oldest first."""
    with pool.connection() as conn:
        if since is not None:
            rows = conn.execute("SELECT EXTRACT(EPOCH FROM ts)*1000, equity FROM shadow_equity"
                                " WHERE baseline=%s AND ts >= %s ORDER BY ts", (baseline, since)).fetchall()
        else:
            rows = conn.execute("SELECT EXTRACT(EPOCH FROM ts)*1000, equity FROM shadow_equity"
                                " WHERE baseline=%s ORDER BY ts", (baseline,)).fetchall()
    return [[int(r[0]), float(r[1])] for r in rows]


def realized_by_symbol(since=None) -> dict[str, float]:
    """Realized PnL per symbol from closed positions (for the info-ON/OFF ablation split)."""
    clause = "AND closed_at >= %s" if since is not None else ""
    params = (since,) if since is not None else ()
    with pool.connection() as conn:
        rows = conn.execute(
            "SELECT symbol, COALESCE(SUM(realized_pnl),0) FROM positions"
            f" WHERE closed_at IS NOT NULL {clause} GROUP BY symbol", params).fetchall()
    return {r[0]: float(r[1]) for r in rows}


def perp_metrics_recent(symbol: str, limit: int = 30) -> list[dict]:
    """Last `limit` perp_metrics rows for one symbol, newest first (for Δ / trend)."""
    with pool.connection() as conn:
        rows = conn.execute(
            "SELECT symbol, ts, funding_rate, funding_annual_pct, open_interest,"
            " long_short_ratio, basis_bps, liq_long_usd, liq_short_usd"
            " FROM perp_metrics WHERE symbol=%s ORDER BY ts DESC LIMIT %s",
            (symbol, limit),
        ).fetchall()
    return [_metric_row(r) for r in rows]


def recent_webhooks(since=None, limit: int = 100) -> list[dict]:
    """Outbound wake events Sunday sent the swarm (the /events feed), newest first."""
    with pool.connection() as conn:
        if since is not None:
            rows = conn.execute(
                "SELECT ts, event_type, to_member, title, body, http_status FROM webhook_log"
                " WHERE ts >= %s ORDER BY ts DESC LIMIT %s",
                (since, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT ts, event_type, to_member, title, body, http_status FROM webhook_log"
                " ORDER BY ts DESC LIMIT %s",
                (limit,),
            ).fetchall()
    return [{"ts": r[0].isoformat(), "event_type": r[1], "to_member": r[2],
             "title": r[3], "body": r[4], "http_status": r[5]} for r in rows]
