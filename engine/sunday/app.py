"""Sunday HTTP service (milestone 1.0 — T1 skeleton).

T1 wires startup (db pool + redis + migrations) and serves /manual, /status
(stub), /health. Real /status values + the trading endpoints land in T2–T4.
"""

from __future__ import annotations

import logging
import pathlib
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import PlainTextResponse

from . import store

log = logging.getLogger("sunday")
_MANUAL = pathlib.Path(__file__).resolve().parent / "manual.md"


@asynccontextmanager
async def lifespan(app: FastAPI):
    store.connect()
    applied = store.run_migrations()
    log.info("migrations applied: %s", applied or "(up to date)")
    yield
    store.close()


app = FastAPI(title="Sunday", version="0.1.0", lifespan=lifespan)


@app.get("/manual", response_class=PlainTextResponse)
def manual() -> str:
    return _MANUAL.read_text()


@app.get("/status")
def status() -> dict:
    # T1 stub. Real values: strategy/position in T3, heartbeat in T4.
    return {
        "alive": True,
        "mode": "flat",
        "symbol": "BTCUSDT",
        "strategy": "flat",
        "strategy_rationale": "(stub) 尚未接策略引擎",
        "position": None,
        "exposure_usd": 0,
        "leverage": 0,
        "equity": 0,
        "pnl_day": 0,
        "last_event_ts": None,
        "swarm_heartbeat_ok": True,
    }


@app.get("/health")
def health() -> dict:
    db_ok = redis_ok = True
    try:
        assert store.pool is not None
        with store.pool.connection() as conn:
            conn.execute("SELECT 1")
    except Exception:
        db_ok = False
    try:
        assert store.rds is not None
        store.rds.ping()
    except Exception:
        redis_ok = False
    return {"db": db_ok, "redis": redis_ok}
