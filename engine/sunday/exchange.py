"""Binance USDⓈ-M adapter — the proxy's spine (milestone-6).

Two ccxt instances, on purpose (the locked topology decision):

  * ``market_ex()`` — **mainnet**, public, no key. All read-only market data
    (tickers, klines, funding, OI) goes here so agents decide on REAL prices.
  * ``trade_ex()``  — **testnet** (``set_sandbox_mode``), keyed. All account +
    order flow goes here so execution is fake-money-safe.

Both are ``ccxt.binanceusdm`` with ``defaultType: future``. Symbol normalization is
per-instance (markets are loaded lazily on first use). Every function is a thin pass
to ccxt; the HTTP layer wraps these in a clean-502 helper.
"""

from __future__ import annotations

import ccxt

from .config import settings

_market: ccxt.binanceusdm | None = None
_trade: ccxt.binanceusdm | None = None


def market_ex() -> ccxt.binanceusdm:
    """Mainnet, public (no key) — source of truth for market data."""
    global _market
    if _market is None:
        _market = ccxt.binanceusdm({
            "enableRateLimit": True,
            "options": {"defaultType": "future"},
        })
    return _market


def trade_ex() -> ccxt.binanceusdm:
    """Testnet (sandbox), keyed — source of truth for the account/book."""
    global _trade
    if _trade is None:
        ex = ccxt.binanceusdm({
            "apiKey": settings.binance_testnet_key or None,
            "secret": settings.binance_testnet_secret or None,
            "enableRateLimit": True,
            "options": {"defaultType": "future", "disableFuturesSandboxWarning": True},
        })
        ex.set_sandbox_mode(True)
        _trade = ex
    return _trade


def _sym(ex: ccxt.binanceusdm, symbol: str) -> str:
    """Map an exchange id (BTCUSDT) to ccxt's unified symbol (BTC/USDT:USDT)."""
    if not ex.markets:
        ex.load_markets()
    if symbol in ex.markets:
        return symbol
    m = ex.markets_by_id.get(symbol)
    if m:
        return (m[0] if isinstance(m, list) else m)["symbol"]
    return symbol


def unify(symbol: str) -> str:
    """Public: id → unified symbol on the MARKET (mainnet) instance."""
    return _sym(market_ex(), symbol)


def unify_trade(symbol: str) -> str:
    """Public: id → unified symbol on the TRADE (testnet) instance — used to match
    a user-supplied id against position/order rows from the testnet book."""
    return _sym(trade_ex(), symbol)


def _f(v) -> float | None:
    try:
        return float(v) if v is not None else None
    except (TypeError, ValueError):
        return None


# --------------------------------------------------------------------------
# Market data (mainnet)
# --------------------------------------------------------------------------

def is_perp(market: dict) -> bool:
    """A tradeable USDⓈ-M linear perpetual (what /api/markets lists)."""
    return bool(
        market.get("swap") and market.get("linear") and market.get("active")
        and market.get("quote") in ("USDT", "USDC")
    )


def list_perp_tickers() -> list[dict]:
    """All USDⓈ-M perpetual tickers (mainnet), normalized for the markets table.

    One ``fetch_tickers`` call (callers cache it). Each row: id + last + 24h
    volume/change/high/low — exactly the fields the markets list sorts/filters on.
    """
    ex = market_ex()
    if not ex.markets:
        ex.load_markets()
    tickers = ex.fetch_tickers()
    out: list[dict] = []
    for unified, t in tickers.items():
        mkt = ex.markets.get(unified)
        if not mkt or not is_perp(mkt):
            continue
        out.append({
            "symbol": mkt["id"],                       # BTCUSDT (what agents pass back)
            "unified": unified,
            "last": _f(t.get("last")),
            "high": _f(t.get("high")),
            "low": _f(t.get("low")),
            "change_pct": _f(t.get("percentage")),     # 24h % change
            "quote_volume": _f(t.get("quoteVolume")),  # 24h USDT volume
            "base_volume": _f(t.get("baseVolume")),
        })
    return out


def fetch_ticker(symbol: str) -> dict:
    return market_ex().fetch_ticker(unify(symbol))


def market_info(symbol: str) -> dict:
    """Static market metadata (precision / limits / leverage cap) for one symbol."""
    ex = market_ex()
    if not ex.markets:
        ex.load_markets()
    m = ex.markets.get(unify(symbol)) or {}
    return {
        "symbol": m.get("id"),
        "unified": m.get("symbol"),
        "base": m.get("base"),
        "quote": m.get("quote"),
        "active": m.get("active"),
        "contract_size": m.get("contractSize"),
        "precision": m.get("precision"),
        "limits": m.get("limits"),
        "max_leverage": (m.get("limits", {}).get("leverage", {}) or {}).get("max"),
        "taker": m.get("taker"),
        "maker": m.get("maker"),
    }


def fetch_ohlcv(symbol: str, tf: str = "1h", limit: int = 200, since: int | None = None) -> list[list]:
    return market_ex().fetch_ohlcv(unify(symbol), timeframe=tf, since=since, limit=limit)


def fetch_funding_rate(symbol: str) -> dict:
    """Current funding (per-8h fraction) + mark/index + next funding time — normalized."""
    fr = market_ex().fetch_funding_rate(unify(symbol))
    return {
        "symbol": symbol,
        "rate": _f(fr.get("fundingRate")),
        "mark": _f(fr.get("markPrice")),
        "index": _f(fr.get("indexPrice")),
        "next_funding_ts": fr.get("fundingTimestamp") or fr.get("nextFundingTime"),
        "interval_hours": fr.get("interval"),
    }


def fetch_funding_history(symbol: str, since: int | None = None, limit: int = 100) -> list[dict]:
    rows = market_ex().fetch_funding_rate_history(unify(symbol), since=since, limit=limit)
    return [{"symbol": symbol, "ts": r.get("timestamp"),
             "rate": _f(r.get("fundingRate"))} for r in rows]


def fetch_open_interest(symbol: str) -> float | None:
    try:
        oi = market_ex().fetch_open_interest(unify(symbol))
        return _f(oi.get("openInterestValue")) or _f(oi.get("openInterestAmount"))
    except Exception:
        return None


def supported_timeframes() -> list[str]:
    ex = market_ex()
    return list((ex.timeframes or {}).keys())


# --------------------------------------------------------------------------
# Account + orders (testnet)
# --------------------------------------------------------------------------

def fetch_balance() -> dict:
    return trade_ex().fetch_balance()


def fetch_positions() -> list[dict]:
    """Open positions only (non-zero contracts)."""
    return [p for p in trade_ex().fetch_positions() if p.get("contracts")]


def fetch_open_orders(symbol: str | None = None) -> list[dict]:
    ex = trade_ex()
    return ex.fetch_open_orders(unify_trade(symbol)) if symbol else ex.fetch_open_orders()


def fetch_orders(symbol: str, since: int | None = None, limit: int = 100) -> list[dict]:
    """Order history (Binance fapi requires a symbol)."""
    return trade_ex().fetch_orders(unify_trade(symbol), since=since, limit=limit)


def fetch_my_trades(symbol: str, since: int | None = None, limit: int = 100) -> list[dict]:
    """Fill history (Binance fapi requires a symbol)."""
    return trade_ex().fetch_my_trades(unify_trade(symbol), since=since, limit=limit)


def amount_to_precision(symbol: str, amount: float) -> float:
    return float(trade_ex().amount_to_precision(unify_trade(symbol), amount))


def price_to_precision(symbol: str, price: float) -> float:
    return float(trade_ex().price_to_precision(unify_trade(symbol), price))


def set_leverage(symbol: str, leverage: int) -> None:
    trade_ex().set_leverage(int(leverage), unify_trade(symbol))


def set_margin_mode(symbol: str, mode: str) -> None:
    """mode: 'isolated' (逐倉) | 'cross' (全倉)."""
    trade_ex().set_margin_mode(mode.lower(), unify_trade(symbol))


def create_order(symbol: str, type_: str, side: str, amount: float,
                 price: float | None = None, params: dict | None = None) -> dict:
    return trade_ex().create_order(unify_trade(symbol), type_, side, amount, price, params or {})


def place_stop(symbol: str, close_side: str, qty: float, trigger_price: float,
               take_profit: bool = False) -> dict:
    """A reduce-only trigger leg: TAKE_PROFIT_MARKET (tp) or STOP_MARKET (sl).

    ``close_side`` is opposite the position side. Used to attach TP/SL to an entry.
    """
    order_type = "TAKE_PROFIT_MARKET" if take_profit else "STOP_MARKET"
    return trade_ex().create_order(
        unify_trade(symbol), order_type, close_side, qty,
        params={"stopPrice": trigger_price, "reduceOnly": True},
    )


def cancel_order(order_id: str, symbol: str) -> dict:
    return trade_ex().cancel_order(order_id, unify_trade(symbol))


def cancel_all_orders(symbol: str) -> None:
    trade_ex().cancel_all_orders(unify_trade(symbol))


def close_position(symbol: str) -> dict | None:
    """Flatten one symbol with a reduce-only market order. None if no open position."""
    target = unify_trade(symbol)
    for p in fetch_positions():
        if p["symbol"] == target and p.get("contracts"):
            close_side = "sell" if p["side"] == "long" else "buy"
            return create_order(symbol, "market", close_side, p["contracts"],
                                params={"reduceOnly": True})
    return None
