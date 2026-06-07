"""Sunday HTTP service.

T1: startup (db pool + redis + migrations), /manual, /status (stub), /health.
T2: /market (public OHLCV), /positions, /pnl (private — need testnet key).
Real /status values + the trading levers land in T3/T4.
"""

from __future__ import annotations

import logging
import pathlib
from contextlib import asynccontextmanager
from typing import Callable, TypeVar

from fastapi import FastAPI, HTTPException
from fastapi.responses import PlainTextResponse

from . import exchange, store
from .config import settings

log = logging.getLogger("sunday")
_MANUAL = pathlib.Path(__file__).resolve().parent / "manual.md"

T = TypeVar("T")


@asynccontextmanager
async def lifespan(app: FastAPI):
    store.connect()
    applied = store.run_migrations()
    log.info("migrations applied: %s", applied or "(up to date)")
    yield
    store.close()


app = FastAPI(title="Sunday", version="0.1.0", lifespan=lifespan)


def _require_key() -> None:
    if not settings.binance_testnet_key:
        raise HTTPException(503, "BINANCE_TESTNET_KEY not set — add it to engine/.env")


def _ex(fn: Callable[[], T]) -> T:
    """Run an exchange call; turn ccxt/network errors into a clean 502."""
    try:
        return fn()
    except HTTPException:
        raise
    except Exception as e:  # external API — surface a clean error, not a 500 traceback
        raise HTTPException(502, f"exchange error: {type(e).__name__}: {str(e)[:300]}")


@app.get("/manual", response_class=PlainTextResponse)
def manual() -> str:
    return _MANUAL.read_text()


@app.get("/status")
def status() -> dict:
    # T1 stub. Real strategy/position values land in T3.
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


@app.get("/market")
def market(symbol: str = "BTCUSDT", tf: str = "1h", limit: int = 200) -> dict:
    ohlcv = _ex(lambda: exchange.fetch_ohlcv(symbol, tf, limit))
    return {"symbol": symbol, "tf": tf, "ohlcv": ohlcv}


@app.get("/positions")
def positions() -> list[dict]:
    _require_key()
    raw = _ex(lambda: exchange.fetch_positions())
    return [
        {
            "symbol": p.get("symbol"),
            "side": p.get("side"),
            "qty": p.get("contracts"),
            "entry": p.get("entryPrice"),
            "mark": p.get("markPrice"),
            "upnl": p.get("unrealizedPnl"),
            "stop": None,        # our own stop is tracked in T3
            "strategy": None,    # ledger tag added in T3
            "entry_reason": None,
        }
        for p in raw
    ]


@app.get("/pnl")
def pnl(since: str | None = None) -> dict:
    _require_key()
    bal = _ex(lambda: exchange.fetch_balance())
    raw = _ex(lambda: exchange.fetch_positions())
    unrealized = sum(float(p.get("unrealizedPnl") or 0) for p in raw)
    equity = (bal.get("total") or {}).get("USDT")
    return {"realized": None, "unrealized": unrealized, "equity": equity, "equity_curve": []}
