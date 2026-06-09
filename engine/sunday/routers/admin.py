"""/api/admin — destructive test-reset utilities.

A single ``POST /api/admin/reset`` that returns Sunday to a clean slate between test
runs: it cancels every resting order (incl. TP/SL legs), closes every open position at
market, then wipes the local SQLite store (alerts, order log, work journal, monitor
config). The running realtime hub is nudged to drop its now-stale alert snapshot and
position book immediately, so it won't keep evaluating gone state until the next poll.

Testnet only (``require_trade_key``). This is an operator/testing affordance — it is
intentionally NOT advertised in the agent ``/manual``.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter

from .. import exchange, runtime, store
from ..apiutil import ex_call, require_trade_key

log = logging.getLogger("sunday.admin")

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.post("/reset")
def reset() -> dict:
    """Flatten the testnet account + wipe the local DB. Irreversible.

    Order matters: cancel resting orders FIRST (so the reduce-only TP/SL legs don't
    reject as the position goes flat), then close positions, then clear SQLite."""
    require_trade_key()
    cancelled = ex_call(exchange.cancel_all_open_orders)
    closed = ex_call(exchange.close_all_positions)
    db_cleared = store.reset()
    # Drop the now-stale in-memory snapshots at once (don't wait for the poll loop). Best
    # effort: a transient exchange hiccup here must not fail an otherwise-complete reset —
    # the poll loop reconciles within monitor_poll_sec regardless.
    if runtime.realtime is not None:
        try:
            runtime.realtime.monitor.refresh_book(seed=True)   # seed=True → rebuild silently, no fire
        except Exception as e:
            log.warning("post-reset monitor refresh: %s", e)
        try:
            runtime.realtime.alerts.refresh()
        except Exception as e:
            log.warning("post-reset alerts refresh: %s", e)
    return {"ok": True, "cancelled_orders": cancelled, "closed_positions": closed, "db_cleared": db_cleared}
