"""/api/funding — perpetual funding rate, current + history (req 2).

Funding is the perp-specific signal (positive = longs pay shorts). Mainnet read, so
the rate/basis an agent sees is the real one, not a thin testnet quote.
"""

from __future__ import annotations

from fastapi import APIRouter

from .. import exchange
from ..apiutil import ex_call
from ..pagination import paginate

router = APIRouter(prefix="/api/funding", tags=["funding"])


@router.get("")
def funding(symbol: str = "BTCUSDT") -> dict:
    """Current funding rate (per-interval fraction) + mark/index + next funding time."""
    return ex_call(lambda: exchange.fetch_funding_rate(symbol))


@router.get("/history")
def funding_history(symbol: str = "BTCUSDT", limit: int = 100,
                    start: int | None = None, page: int = 1, page_size: int = 50) -> dict:
    """Historical funding (newest first), paginated."""
    rows = ex_call(lambda: exchange.fetch_funding_history(symbol, since=start, limit=min(limit, 1000)))
    return paginate(list(reversed(rows)), page, page_size)
