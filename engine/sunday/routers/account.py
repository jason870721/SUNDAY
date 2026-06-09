"""/api/account — positions / PnL / orders / trades on the testnet account (req 3).

All endpoints read the testnet book (the proxy holds the keys). Lists paginate via
the shared envelope. Binance fapi requires a symbol for order/trade history, so those
two endpoints take a required `symbol`.
"""

from __future__ import annotations

from fastapi import APIRouter

from .. import exchange
from ..apiutil import ex_call, require_trade_key, to_float
from ..monitor import position_roi
from ..pagination import paginate

router = APIRouter(prefix="/api/account", tags=["account"])


def _position_row(p: dict) -> dict:
    contracts = to_float(p.get("contracts"))
    mark = to_float(p.get("markPrice"))
    return {
        "symbol": p.get("symbol"),
        "side": p.get("side"),
        "qty": contracts,
        "entry": to_float(p.get("entryPrice")),
        "mark": mark,
        "leverage": to_float(p.get("leverage")),
        "margin_mode": p.get("marginMode"),
        "notional": abs((contracts or 0) * (mark or 0)),
        "unrealized_pnl": to_float(p.get("unrealizedPnl")),
        "roi_pct": position_roi(p),
        "liquidation_price": to_float(p.get("liquidationPrice")),
    }


def _order_row(o: dict) -> dict:
    return {
        "id": o.get("id"), "symbol": o.get("symbol"), "type": o.get("type"),
        "side": o.get("side"), "price": to_float(o.get("price")),
        "amount": to_float(o.get("amount")), "filled": to_float(o.get("filled")),
        "remaining": to_float(o.get("remaining")), "status": o.get("status"),
        "reduce_only": o.get("reduceOnly"), "trigger_price": to_float(o.get("triggerPrice")),
        "ts": o.get("timestamp"), "client_order_id": o.get("clientOrderId"),
    }


def _trade_row(t: dict) -> dict:
    info = t.get("info") or {}
    fee = t.get("fee") or {}
    return {
        "id": t.get("id"), "order": t.get("order"), "symbol": t.get("symbol"),
        "side": t.get("side"), "price": to_float(t.get("price")),
        "amount": to_float(t.get("amount")), "cost": to_float(t.get("cost")),
        "fee": to_float(fee.get("cost")), "fee_currency": fee.get("currency"),
        "realized_pnl": to_float(info.get("realizedPnl")), "ts": t.get("timestamp"),
    }


@router.get("/positions")
def positions(page: int = 1, page_size: int = 50) -> dict:
    """Open positions with per-position ROI%."""
    require_trade_key()
    raw = ex_call(exchange.fetch_positions)
    return paginate([_position_row(p) for p in raw], page, page_size)


@router.get("/balance")
def balance() -> dict:
    """Account equity + free/used margin (USDT)."""
    require_trade_key()
    bal = ex_call(exchange.fetch_balance)
    total = bal.get("total") or {}
    return {
        "equity": to_float(total.get("USDT")),
        "free": to_float((bal.get("free") or {}).get("USDT")),
        "used": to_float((bal.get("used") or {}).get("USDT")),
        "assets": {k: v for k, v in total.items() if v},
    }


@router.get("/pnl")
def pnl() -> dict:
    """Account PnL summary: equity + total unrealized + per-position breakdown.
    (Per-symbol realized PnL is available via /api/account/trades.)"""
    require_trade_key()
    positions_raw = ex_call(exchange.fetch_positions)
    bal = ex_call(exchange.fetch_balance)
    rows = [_position_row(p) for p in positions_raw]
    return {
        "equity": to_float((bal.get("total") or {}).get("USDT")),
        "unrealized_pnl": sum(r["unrealized_pnl"] or 0 for r in rows),
        "positions": rows,
    }


@router.get("/orders/open")
def open_orders(symbol: str | None = None, page: int = 1, page_size: int = 50) -> dict:
    """Open (resting) orders, optionally for one symbol."""
    require_trade_key()
    rows = ex_call(lambda: exchange.fetch_open_orders(symbol))
    return paginate([_order_row(o) for o in rows], page, page_size)


@router.get("/orders")
def order_history(symbol: str, start: int | None = None, limit: int = 100,
                  page: int = 1, page_size: int = 50) -> dict:
    """Order history for `symbol` (required by Binance fapi), newest first, paginated."""
    require_trade_key()
    rows = ex_call(lambda: exchange.fetch_orders(symbol, since=start, limit=min(limit, 1000)))
    return paginate([_order_row(o) for o in reversed(rows)], page, page_size)


@router.get("/trades")
def trade_history(symbol: str, start: int | None = None, limit: int = 100,
                  page: int = 1, page_size: int = 50) -> dict:
    """Fill history for `symbol` (required by Binance fapi), newest first, paginated.
    Each fill carries realized PnL where the exchange reports it."""
    require_trade_key()
    rows = ex_call(lambda: exchange.fetch_my_trades(symbol, since=start, limit=min(limit, 1000)))
    return paginate([_trade_row(t) for t in reversed(rows)], page, page_size)
