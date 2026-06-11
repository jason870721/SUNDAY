"""Binance Algo-Service (conditional order) compatibility — pure mapping (PRD-003).

On 2025-12-09 Binance moved USDⓈ-M conditional orders (STOP_MARKET / TAKE_PROFIT_MARKET /
STOP / TAKE_PROFIT / TRAILING_STOP_MARKET) out of the regular order book into a separate
Algo Service: ``POST /fapi/v1/order`` rejects those types (-4120), untriggered legs are
only visible via ``GET /fapi/v1/openAlgoOrders`` (keyed by ``algoId``), and the legacy
DELETE endpoints can't cancel them. ccxt ≥ 4.5 transparently *places* conditional orders
through the algo endpoints — so Sunday's writes kept working while its raw reads went
blind: TP/SL legs vanished from /api/account/orders/open, positions reported a false
naked state, and cancel-all left orphan algo legs (the -4047 margin-mode mystery).

This module is the stdlib-only reshaping layer (invariant 6): an algo row becomes the
legacy ``/fapi/v1/openOrders`` row shape the routers already consume, tagged
``algo: True`` so callers know the id lives in the algo book. exchange.py does the I/O.
"""

from __future__ import annotations


def normalize_algo_order(a: dict) -> dict:
    """Map one /fapi/v1 algo (conditional) row to the legacy openOrders shape.

    Field translations: algoId→orderId, clientAlgoId→clientOrderId, orderType→type,
    algoStatus→status, triggerPrice→stopPrice, quantity→origQty, createTime→time.
    ``executedQty`` is pinned "0": an untriggered leg has no fills — once it fires the
    fills live on the spawned regular order (``actualOrderId``)."""
    return {
        "algo": True,
        "orderId": a.get("algoId"),
        "clientOrderId": a.get("clientAlgoId"),
        "symbol": a.get("symbol"),
        "status": a.get("algoStatus"),
        "type": a.get("orderType"),
        "side": a.get("side"),
        "positionSide": a.get("positionSide"),
        "timeInForce": a.get("timeInForce"),
        "price": a.get("price"),
        "stopPrice": a.get("triggerPrice"),
        "origQty": a.get("quantity"),
        "executedQty": "0",
        "reduceOnly": a.get("reduceOnly"),
        "closePosition": a.get("closePosition"),
        "workingType": a.get("workingType"),
        "priceProtect": a.get("priceProtect"),
        "time": a.get("createTime"),
        "updateTime": a.get("updateTime"),
        "actualOrderId": a.get("actualOrderId"),
    }


def is_unknown_order(msg: str) -> bool:
    """Whether an exchange error says the id isn't in the regular order book (-2011) —
    the cue to retry a cancel against the algo book, where TP/SL legs now live."""
    s = (msg or "").lower()
    return "-2011" in s or "unknown order" in s
