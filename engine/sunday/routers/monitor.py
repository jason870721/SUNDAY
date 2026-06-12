"""/api/monitor — open-position PnL monitoring (req 5).

Monitoring is automatic for every open position; this surfaces what the hub is
currently tracking (each position's ROI% + step bucket) and lets the step size / on-off
be tuned at runtime. The actual webhooks go to the evva swarm, not through here.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from .. import runtime, store
from ..config import settings

router = APIRouter(prefix="/api/monitor", tags=["monitor"])


class ConfigReq(BaseModel):
    enabled: bool | None = None
    step_pct: float | None = None
    hyst_pct: float | None = None     # anti-chatter dead band; 0 = off


def _config() -> dict:
    return {"enabled": settings.monitor_enabled, "step_pct": settings.monitor_step_pct,
            "hyst_pct": settings.monitor_hyst_pct,
            "poll_sec": settings.monitor_poll_sec, "ws": settings.ws_enabled}


@router.get("")
def monitor_status() -> dict:
    """Current monitor config + the positions being watched (ROI% + step bucket)."""
    rt = runtime.realtime
    return {"config": _config(), "positions": rt.monitor.snapshot() if rt else []}


@router.post("/config")
def set_config(req: ConfigReq) -> dict:
    """Tune the monitor at runtime: toggle it, change the % step that triggers a
    webhook, or resize the anti-chatter dead band (hyst_pct; 0 disables it)."""
    if req.step_pct is not None:
        if req.step_pct <= 0:
            raise HTTPException(400, "step_pct must be positive")
        settings.monitor_step_pct = req.step_pct
        store.kv_set("monitor_step_pct", str(req.step_pct))
    if req.hyst_pct is not None:
        if req.hyst_pct < 0:
            raise HTTPException(400, "hyst_pct must be ≥ 0 (0 = no dead band)")
        settings.monitor_hyst_pct = req.hyst_pct
        store.kv_set("monitor_hyst_pct", str(req.hyst_pct))
    if req.enabled is not None:
        settings.monitor_enabled = req.enabled
        store.kv_set("monitor_enabled", "1" if req.enabled else "0")
    return {"ok": True, "config": _config()}
