"""/api/account — positions / PnL / orders / trades on the testnet account (req 3).

Reads come from Binance's signed fapi REST directly (see exchange.py), so every row is
the raw Binance shape — leverage / liquidationPrice / marginType / stopPrice intact.
Lists paginate via the shared envelope. Binance requires a symbol for order/trade history.
"""

from __future__ import annotations

from fastapi import APIRouter

from .. import exchange, store
from ..apiutil import ex_call, require_trade_key, to_float
from ..pagination import paginate

router = APIRouter(prefix="/api/account", tags=["account"])

# Order-journal fields surfaced on a position (the agent's logged decision).
_ORDER_FIELDS = ("order_id", "ts", "side", "type", "qty", "notional_usd", "price",
                 "leverage", "margin_mode", "reduce_only", "take_profit", "stop_loss")


def _leg(order_type: str | None) -> str | None:
    """Classify a Binance order type as a take-profit / stop-loss trigger leg."""
    t = (order_type or "").upper()
    if "TAKE_PROFIT" in t:
        return "take_profit"
    if "STOP" in t:
        return "stop_loss"
    return None


def _safe_leverage() -> dict:
    try:
        return exchange.leverage_by_symbol()
    except Exception:
        return {}


def _position_row(p: dict, journal: dict | None = None) -> dict:
    amt = to_float(p.get("positionAmt")) or 0.0
    mark = to_float(p.get("markPrice"))
    lev = to_float(p.get("leverage"))
    upnl = to_float(p.get("unRealizedProfit"))
    notional = abs(amt * (mark or 0.0))
    margin = notional / lev if (lev and notional) else None
    roi = (upnl / margin * 100.0) if (upnl is not None and margin) else None
    liq = to_float(p.get("liquidationPrice"))
    log = (journal or {}).get(p.get("symbol"))
    return {
        "symbol": p.get("symbol"),
        "side": "long" if amt > 0 else "short",
        "qty": abs(amt),
        "entry": to_float(p.get("entryPrice")),
        "mark": mark,
        "leverage": int(lev) if lev else None,
        "margin_mode": (p.get("marginType") or "").lower() or None,
        "notional": notional,
        "unrealized_pnl": upnl,
        "roi_pct": round(roi, 2) if roi is not None else None,
        # Binance reports 0 for a cross position (liquidation is account-wide) → none.
        "liquidation_price": liq if liq else None,
        # joined from the order journal — the agent's rationale + params for this symbol
        "memo": log.get("memo") if log else None,
        "order": {k: log.get(k) for k in _ORDER_FIELDS} if log else None,
    }


def _order_row(o: dict, lev_by_symbol: dict | None = None) -> dict:
    typ = (o.get("type") or "").upper()
    trig = to_float(o.get("stopPrice"))
    amount = to_float(o.get("origQty")) or 0.0
    filled = to_float(o.get("executedQty")) or 0.0
    return {
        "id": str(o.get("orderId")),
        "symbol": o.get("symbol"),
        "type": typ.lower(),
        "side": (o.get("side") or "").lower(),
        "price": to_float(o.get("price")) or None,
        "amount": amount,
        "filled": filled,
        "remaining": amount - filled,
        "status": (o.get("status") or "").lower(),
        "reduce_only": o.get("reduceOnly"),
        "trigger_price": trig if trig else None,
        "tp_sl": _leg(typ),
        "leverage": (lev_by_symbol or {}).get(o.get("symbol")),
        "ts": o.get("time"),
        "client_order_id": o.get("clientOrderId"),
    }


def _trade_row(t: dict) -> dict:
    return {
        "id": str(t.get("id")), "order": str(t.get("orderId")), "symbol": t.get("symbol"),
        "side": (t.get("side") or "").lower(), "price": to_float(t.get("price")),
        "amount": to_float(t.get("qty")), "cost": to_float(t.get("quoteQty")),
        "fee": to_float(t.get("commission")), "fee_currency": t.get("commissionAsset"),
        "realized_pnl": to_float(t.get("realizedPnl")), "ts": t.get("time"),
    }


@router.get("/positions")
def positions(page: int = 1, page_size: int = 50) -> dict:
    """Open positions with ROI%, leverage, liquidation price + the agent's order memo."""
    require_trade_key()
    raw = ex_call(exchange.fetch_positions)
    journal = {p.get("symbol"): store.latest_order(p.get("symbol")) for p in raw}
    return paginate([_position_row(p, journal) for p in raw], page, page_size)


@router.get("/balance")
def balance() -> dict:
    """Account equity / free / used margin + total unrealized PnL (USDT)."""
    require_trade_key()
    a = ex_call(exchange.fetch_account)
    return {
        "equity": to_float(a.get("totalMarginBalance")),
        "wallet": to_float(a.get("totalWalletBalance")),
        "free": to_float(a.get("availableBalance")),
        "used": to_float(a.get("totalPositionInitialMargin")),
        "unrealized_pnl": to_float(a.get("totalUnrealizedProfit")),
    }


@router.get("/pnl")
def pnl() -> dict:
    """Account PnL: equity + total unrealized + per-position breakdown.
    Per-symbol realized PnL is available via /api/account/trades."""
    require_trade_key()
    raw = ex_call(exchange.fetch_positions)
    acct = ex_call(exchange.fetch_account)
    journal = {p.get("symbol"): store.latest_order(p.get("symbol")) for p in raw}
    return {
        "equity": to_float(acct.get("totalMarginBalance")),
        "unrealized_pnl": to_float(acct.get("totalUnrealizedProfit")),
        "positions": [_position_row(p, journal) for p in raw],
    }


@router.get("/orders/open")
def open_orders(symbol: str | None = None, page: int = 1, page_size: int = 50) -> dict:
    """Open (resting) orders, newest first — each annotated with its symbol's leverage
    and a tp_sl classification (take_profit / stop_loss / null)."""
    require_trade_key()
    rows = ex_call(lambda: exchange.fetch_open_orders(symbol))
    lev = _safe_leverage()
    rows = sorted(rows, key=lambda o: o.get("time") or 0, reverse=True)
    return paginate([_order_row(o, lev) for o in rows], page, page_size)


@router.get("/orders")
def order_history(symbol: str, start: int | None = None, limit: int = 100,
                  page: int = 1, page_size: int = 50) -> dict:
    """Order history for `symbol` (required by Binance fapi), newest first, paginated."""
    require_trade_key()
    rows = ex_call(lambda: exchange.fetch_orders(symbol, since=start, limit=min(limit, 1000)))
    lev = _safe_leverage()
    return paginate([_order_row(o, lev) for o in reversed(rows)], page, page_size)


@router.get("/trades")
def trade_history(symbol: str, start: int | None = None, limit: int = 100,
                  page: int = 1, page_size: int = 50) -> dict:
    """Fill history for `symbol` (required by Binance fapi), newest first, paginated.
    Each fill carries realized PnL where the exchange reports it."""
    require_trade_key()
    rows = ex_call(lambda: exchange.fetch_my_trades(symbol, since=start, limit=min(limit, 1000)))
    return paginate([_trade_row(t) for t in reversed(rows)], page, page_size)
