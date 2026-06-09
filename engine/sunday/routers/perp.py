"""/api/perp — perpetual order flow on the testnet account (req 1).

The agent places orders here like a human would on Binance: market/limit entries
sized by contracts or USD notional, with optional leverage, margin mode (isolated/
cross 逐倉/全倉), and attached take-profit / stop-loss. TP/SL are placed as reduce-only
TAKE_PROFIT_MARKET / STOP_MARKET legs after the entry — the same primitive the
exchange uses for native brackets.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from .. import exchange, store
from ..apiutil import ex_call, require_trade_key, to_float

router = APIRouter(prefix="/api/perp", tags=["perp"])


class OrderReq(BaseModel):
    symbol: str
    side: str                              # buy | sell
    type: str = "market"                   # market | limit
    qty: float | None = None               # contracts; or use notional_usd
    notional_usd: float | None = None      # sized to qty via current price
    price: float | None = None             # required for limit
    leverage: int | None = None            # set before the entry if given
    margin_mode: str | None = None         # isolated | cross
    reduce_only: bool = False
    take_profit: float | None = None       # trigger price → reduce-only TP leg
    stop_loss: float | None = None         # trigger price → reduce-only SL leg
    memo: str | None = Field(default=None, max_length=300)  # agent's rationale; shown to the User


class LeverageReq(BaseModel):
    symbol: str
    leverage: int


class MarginModeReq(BaseModel):
    symbol: str
    mode: str                              # isolated | cross


class CloseReq(BaseModel):
    symbol: str


def _norm_order(o: dict) -> dict:
    return {
        "id": o.get("id"), "symbol": o.get("symbol"), "type": o.get("type"),
        "side": o.get("side"), "status": o.get("status"),
        "price": to_float(o.get("price")), "amount": to_float(o.get("amount")),
        "filled": to_float(o.get("filled")), "reduce_only": o.get("reduceOnly"),
        "trigger_price": to_float(o.get("triggerPrice")), "ts": o.get("timestamp"),
    }


def _set_margin_mode_safe(symbol: str, mode: str) -> str:
    """Set margin mode, tolerating Binance's two benign rejections and reporting which:
      'set'       — changed;
      'unchanged' — already that mode (-4046 'No need to change margin type');
      'blocked'   — can't change while a position / open orders exist (-4047).
    Only genuinely unexpected errors raise. Callers decide whether 'blocked' is fatal."""
    try:
        exchange.set_margin_mode(symbol, mode)
        return "set"
    except Exception as e:
        s = str(e).lower()
        if "-4046" in s or "no need to change" in s:
            return "unchanged"
        if "-4047" in s or "cannot be changed if there exists" in s:
            return "blocked"
        raise HTTPException(502, f"set_margin_mode failed: {type(e).__name__}: {str(e)[:200]}")


def _resolve_qty(req: OrderReq) -> float:
    if req.qty and req.qty > 0:
        return ex_call(lambda: exchange.amount_to_precision(req.symbol, req.qty))
    if req.notional_usd and req.notional_usd > 0:
        price = req.price if (req.type == "limit" and req.price) else \
            ex_call(lambda: to_float(exchange.fetch_ticker(req.symbol).get("last")))
        if not price:
            raise HTTPException(502, "could not resolve a price to size notional_usd")
        return ex_call(lambda: exchange.amount_to_precision(req.symbol, req.notional_usd / price))
    raise HTTPException(400, "provide qty (contracts) or notional_usd")


def _place_entry(req: "OrderReq", qty: float, params: dict) -> dict:
    """Place the entry order; turn Binance's PERCENT_PRICE rejection (-4016/-4017) into a
    clear 400 explaining the limit must sit within the symbol's % band of the mark."""
    try:
        return exchange.create_order(req.symbol, req.type, req.side, qty, req.price, params)
    except HTTPException:
        raise
    except Exception as e:
        msg = str(e)
        if any(t in msg for t in ("-4016", "-4017", "PERCENT_PRICE", "Limit price can")):
            raise HTTPException(400,
                f"limit price rejected by Binance's PERCENT_PRICE filter: {msg[:140]}. "
                "A limit price must stay within the symbol's allowed % band around the mark — "
                "move it closer to the current price, or use type=market.")
        raise HTTPException(502, f"exchange error: {type(e).__name__}: {msg[:300]}")


@router.post("/order")
def place_order(req: OrderReq) -> dict:
    """Place a perp order. side=buy|sell, type=market|limit; size by qty or notional_usd;
    optional leverage / margin_mode / take_profit / stop_loss."""
    require_trade_key()
    if req.side not in ("buy", "sell"):
        raise HTTPException(400, "side must be 'buy' or 'sell'")
    if req.type not in ("market", "limit"):
        raise HTTPException(400, "type must be 'market' or 'limit'")
    if req.type == "limit" and not req.price:
        raise HTTPException(400, "limit orders require a price")

    applied: dict = {}
    if req.margin_mode:
        if req.margin_mode not in ("isolated", "cross"):
            raise HTTPException(400, "margin_mode must be 'isolated' or 'cross'")
        result = _set_margin_mode_safe(req.symbol, req.margin_mode)
        applied["margin_mode"] = req.margin_mode
        if result == "blocked":  # a position/open orders exist → keep current mode, still place the order
            applied["margin_mode_note"] = "unchanged: a position or open orders already exist on this symbol (Binance -4047)"
    if req.leverage:
        ex_call(lambda: exchange.set_leverage(req.symbol, req.leverage))
        applied["leverage"] = req.leverage

    qty = _resolve_qty(req)
    params = {"reduceOnly": True} if req.reduce_only else {}
    entry = _place_entry(req, qty, params)

    # Attach reduce-only TP/SL legs (only meaningful for an opening order).
    legs: dict = {}
    if not req.reduce_only and (req.take_profit or req.stop_loss):
        close_side = "sell" if req.side == "buy" else "buy"
        if req.take_profit:
            legs["take_profit"] = _norm_order(ex_call(lambda: exchange.place_stop(
                req.symbol, close_side, qty, req.take_profit, take_profit=True)))
        if req.stop_loss:
            legs["stop_loss"] = _norm_order(ex_call(lambda: exchange.place_stop(
                req.symbol, close_side, qty, req.stop_loss, take_profit=False)))

    # Journal the decision: params (one column each) + the agent's memo. Joined into
    # /api/account/positions so the User sees WHY this position was opened.
    store.record_order(req.symbol.upper(), entry.get("id"), req.memo, {
        "side": req.side, "type": req.type, "qty": qty,
        "notional_usd": req.notional_usd, "price": req.price,
        "leverage": req.leverage, "margin_mode": req.margin_mode, "reduce_only": req.reduce_only,
        "take_profit": req.take_profit, "stop_loss": req.stop_loss,
    })

    return {"ok": True, "applied": applied, "order": _norm_order(entry), "memo": req.memo, **legs}


@router.post("/leverage")
def set_leverage(req: LeverageReq) -> dict:
    require_trade_key()
    if req.leverage < 1:
        raise HTTPException(400, "leverage must be ≥ 1")
    ex_call(lambda: exchange.set_leverage(req.symbol, req.leverage))
    return {"ok": True, "symbol": req.symbol.upper(), "leverage": req.leverage}


@router.post("/margin-mode")
def set_margin_mode(req: MarginModeReq) -> dict:
    require_trade_key()
    if req.mode not in ("isolated", "cross"):
        raise HTTPException(400, "mode must be 'isolated' or 'cross'")
    result = _set_margin_mode_safe(req.symbol, req.mode)
    if result == "blocked":
        raise HTTPException(409, f"cannot change margin mode for {req.symbol.upper()} while a position or open orders exist")
    return {"ok": True, "symbol": req.symbol.upper(), "margin_mode": req.mode, "result": result}


@router.post("/close")
def close(req: CloseReq) -> dict:
    """Flatten an open position with a reduce-only market order."""
    require_trade_key()
    result = ex_call(lambda: exchange.close_position(req.symbol))
    if result is None:
        raise HTTPException(404, f"no open position for {req.symbol.upper()}")
    return {"ok": True, "closed": _norm_order(result)}


@router.delete("/order/{order_id}")
def cancel_order(order_id: str, symbol: str) -> dict:
    """Cancel one resting order (symbol required by Binance fapi)."""
    require_trade_key()
    ex_call(lambda: exchange.cancel_order(order_id, symbol))
    return {"ok": True, "cancelled": order_id}


@router.delete("/orders")
def cancel_all(symbol: str) -> dict:
    """Cancel all resting orders for a symbol."""
    require_trade_key()
    ex_call(lambda: exchange.cancel_all_orders(symbol))
    return {"ok": True, "symbol": symbol.upper()}
