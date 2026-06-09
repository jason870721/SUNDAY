"""/api/alerts — price alerts (req 6).

Create / list / delete alerts. A ``pct_move`` alert captures the current price as its
reference at creation. After a create/delete we nudge the running hub to re-read its
snapshot so the new alert is evaluated (and its symbol subscribed) right away.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from .. import exchange, runtime, store
from ..alerts import KINDS
from ..apiutil import ex_call, to_float
from ..pagination import paginate

router = APIRouter(prefix="/api/alerts", tags=["alerts"])


class AlertReq(BaseModel):
    symbol: str
    kind: str                      # price_above | price_below | pct_move
    threshold: float               # price (above/below) or |pct| (pct_move)
    note: str | None = None


@router.post("")
def create_alert(req: AlertReq) -> dict:
    if req.kind not in KINDS:
        raise HTTPException(400, f"kind must be one of: {', '.join(KINDS)}")
    if req.threshold <= 0:
        raise HTTPException(400, "threshold must be positive")
    sym = req.symbol.upper()
    ref = None
    if req.kind == "pct_move":
        ref = ex_call(lambda: to_float(exchange.fetch_ticker(sym).get("last")))
        if not ref:
            raise HTTPException(502, "could not capture a reference price for pct_move")
    alert = store.create_alert(sym, req.kind, req.threshold, ref, req.note)
    if runtime.realtime:
        runtime.realtime.alerts.refresh()
    return alert


@router.get("")
def list_alerts(status: str | None = None, page: int = 1, page_size: int = 50) -> dict:
    """All alerts (or filter `status`=active|triggered), paginated."""
    return paginate(store.list_alerts(status), page, page_size)


@router.delete("/{alert_id}")
def delete_alert(alert_id: int) -> dict:
    ok = store.delete_alert(alert_id)
    if runtime.realtime:
        runtime.realtime.alerts.refresh()
    if not ok:
        raise HTTPException(404, f"no alert #{alert_id}")
    return {"ok": True, "deleted": alert_id}
