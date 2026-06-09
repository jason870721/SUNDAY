"""/api/markets — tradeable-market discovery (req 0).

Lists every USDⓈ-M perpetual (mainnet) as a paginated table an agent (or a human)
can filter by symbol and sort by 24h volume / change% / symbol. ``fetch_tickers`` is
one big upstream call, so it's cached briefly and served stale-on-error rather than
failing the whole list.
"""

from __future__ import annotations

import time

from fastapi import APIRouter, HTTPException

from .. import exchange
from ..apiutil import ex_call, to_float
from ..pagination import paginate, sort_by

router = APIRouter(prefix="/api/markets", tags=["markets"])

_CACHE: dict = {"ts": 0.0, "rows": []}
_TTL = 10.0  # seconds — tickers move, but 10s spares the upstream under agent fan-out

_SORT_KEYS = {"volume": "quote_volume", "change": "change_pct", "symbol": "symbol", "last": "last"}


def _tickers() -> list[dict]:
    now = time.time()
    if not _CACHE["rows"] or now - _CACHE["ts"] > _TTL:
        try:
            _CACHE["rows"] = exchange.list_perp_tickers()
            _CACHE["ts"] = now
        except Exception as e:
            if _CACHE["rows"]:
                return _CACHE["rows"]  # serve stale rather than fail the table
            raise HTTPException(502, f"exchange error: {type(e).__name__}: {str(e)[:200]}")
    return _CACHE["rows"]


@router.get("")
def list_markets(symbol: str | None = None, sort: str = "volume",
                 order: str = "desc", page: int = 1, page_size: int = 10) -> dict:
    """Paginated tradeable markets. `symbol` = substring filter (e.g. BTC);
    `sort` = volume|change|symbol|last; `order` = desc|asc."""
    rows = _tickers()
    if symbol:
        s = symbol.upper()
        rows = [r for r in rows if s in r["symbol"]]
    rows = sort_by(rows, _SORT_KEYS.get(sort, "quote_volume"), order)
    return paginate(rows, page, page_size)


@router.get("/{symbol}")
def market_detail(symbol: str) -> dict:
    """One market: live ticker + static metadata (precision / limits / max leverage)."""
    t = ex_call(lambda: exchange.fetch_ticker(symbol))
    info = ex_call(lambda: exchange.market_info(symbol))
    return {
        "symbol": symbol.upper(),
        "ticker": {
            "last": to_float(t.get("last")), "bid": to_float(t.get("bid")),
            "ask": to_float(t.get("ask")), "high": to_float(t.get("high")),
            "low": to_float(t.get("low")), "change_pct": to_float(t.get("percentage")),
            "quote_volume": to_float(t.get("quoteVolume")), "base_volume": to_float(t.get("baseVolume")),
        },
        "info": info,
    }
