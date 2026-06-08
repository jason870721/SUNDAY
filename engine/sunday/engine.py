"""Live engine glue — the IO-bound trading loop, built on the pure core.

The *decisions* are pure and tested elsewhere:
  - what side the strategy wants  → strategy.target_side(candles)
  - hold / open / close / flip     → execution.plan_transition(current, target)
  - may this order pass the caps?  → risk.check_order(...)
  - has drawdown breached?         → risk.check_drawdown(...)

This module is the one place that talks to the outside world (ccxt exchange,
postgres/redis store, webhook). It fetches the candles, runs the pure decisions,
and applies the result to the live book under the deterministic risk fuses. The
Gate-2 backtest reuses the SAME pure decisions against a sim broker; this file is
the *live adapter wiring* that the sim path will mirror. (G2.1 next step: lift the
exchange/store/clock behind injected ports so engine.* is itself backtestable.)
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from . import events, exchange, execution, regime, risk, store, strategy
from .config import settings
from .market import Candles

log = logging.getLogger("sunday")


def envelope() -> risk.Envelope:
    """The live hard caps, from settings (the leader's /envelope lever will set these)."""
    return risk.Envelope(
        max_position_usd=settings.max_position_usd,
        max_total_exposure_usd=settings.max_total_exposure_usd,
        max_leverage=settings.max_leverage,
        max_drawdown_pct=settings.max_drawdown_pct,
        stop_pct=settings.stop_pct,
    )


def _candles(symbol: str, limit: int | None = None) -> Candles:
    n = limit or (settings.ema_slow + 50)
    return Candles.from_klines(exchange.fetch_ohlcv(symbol, settings.timeframe, n))


def _current_side(symbol: str) -> str | None:
    """Live book side for `symbol`: 'long' | 'short' | None (flat)."""
    for p in exchange.fetch_positions():
        if p["symbol"] == exchange._sym(symbol) and p.get("contracts"):
            return p["side"]
    return None


def _exposure_usd() -> float:
    total = 0.0
    for p in exchange.fetch_positions():
        if p.get("contracts"):
            total += abs(float(p["contracts"]) * float(p.get("markPrice") or p.get("entryPrice") or 0))
    return total


def _capture_realized(symbol: str) -> float:
    """unrealizedPnl of open positions — the realized PnL the instant we close them."""
    total = 0.0
    for p in exchange.fetch_positions():
        if p["symbol"] == exchange._sym(symbol) and p.get("contracts"):
            total += float(p.get("unrealizedPnl") or 0)
    return total


def _equity() -> float:
    bal = exchange.fetch_balance()
    return float((bal.get("total") or {}).get("USDT") or 0.0)


def _status_snapshot(symbol: str) -> dict:
    """A tiny status blob for self-sufficient webhook payloads (best-effort)."""
    try:
        return {"mode": store.get_mode(), "strategy": store.current_strategy(symbol)}
    except Exception:
        return {}


def notify(event: dict) -> dict:
    """Fire a webhook event (built by events.*), log it to webhook_log, stamp last_event. Never raises."""
    http_status, ok = events.post(settings.evva_webhook_url, event)
    data = event.get("data") or {}
    store.record_webhook(data.get("event_type") or "event", event.get("to") or "leader",
                         event.get("title"), event.get("body"), http_status, None)
    store.set_last_event_ts(datetime.now(timezone.utc).isoformat())
    return {"event_type": data.get("event_type"), "http_status": http_status, "ok": ok}


# --- lever paths (called by app.py) ----------------------------------------

def reconcile(symbol: str, set_by: str = "system") -> dict:
    """Make the live book match the active strategy's target (pure decisions, live effects)."""
    strat = store.current_strategy(symbol)
    candles = _candles(symbol)
    vote = strategy.evaluate(strat, candles)
    target = strategy.target_side(strat, candles)          # 'long' | 'short' | None
    store.record_signal(symbol, strat, vote.indicators,
                        {"long": "open_long", "short": "open_short", None: "go_flat"}[target])
    store.set_rationale(vote.rationale)

    current = _current_side(symbol)
    action = execution.plan_transition(current, target)
    if action == execution.HOLD:
        return {"action": "noop", "side": current, "rationale": vote.rationale}

    if action in (execution.CLOSE, execution.FLIP_LONG, execution.FLIP_SHORT):
        realized = _capture_realized(symbol)
        exchange.close_position(symbol)
        exchange.cancel_all_orders(symbol)
        store.close_open_positions(symbol, realized_pnl=realized)

    if target is None:
        return {"action": "flat", "rationale": vote.rationale}

    mode = store.get_mode()
    if mode in ("safe", "halted"):                          # frozen: no new entries
        return {"action": "frozen_no_entry", "mode": mode, "rationale": vote.rationale}

    return _open(symbol, target, strat, vote.rationale)


def _open(symbol: str, side: str, strat: str, reason: str) -> dict:
    price = float(exchange.fetch_ticker(symbol)["last"])
    qty = round(settings.target_notional_usd / price, 3)
    order = risk.OrderProposal(symbol, "buy" if side == "long" else "sell", qty, price,
                               has_stop=True, is_entry=True)
    ctx = risk.RiskContext(equity=_equity(), current_exposure_usd=_exposure_usd())
    decision = risk.check_order(order, ctx, envelope())
    if not decision.allowed:                                # final line of defence — blocks any over-line order
        store.record_risk_event(decision.type or "rejected",
                                {"symbol": symbol, "qty": qty, "price": price, "violations": decision.violations},
                                action_taken="order_rejected")
        raise risk.RiskRejected(f"{decision.type}: {decision.violations}")

    exchange.set_leverage(symbol, settings.leverage)
    od = exchange.place_market(symbol, order.side, qty)
    store.record_order(symbol, order.side, "market", qty, price, od.get("status") or "new",
                       str(od.get("id")), strat, reason)
    stop_px = risk.stop_price(side, price, settings.stop_pct)
    exchange.set_stop(symbol, "sell" if side == "long" else "buy", qty, stop_px)
    store.record_position_open(symbol, side, qty, price, stop_px, strat, reason)
    return {"action": f"opened_{side}", "qty": qty, "entry": price, "stop": stop_px, "rationale": reason}


def halt(mode: str, reason: str) -> dict:
    """flat = close everything + cancel stops; safe = freeze new entries (keep existing)."""
    if mode == "flat":
        realized = _capture_realized(settings.symbol)
        exchange.close_position(settings.symbol)
        exchange.cancel_all_orders(settings.symbol)
        store.close_open_positions(settings.symbol, realized_pnl=realized)
        store.set_strategy(settings.symbol, "flat", f"halt(flat): {reason}", "system")
        store.set_mode("halted")
    elif mode == "safe":
        store.set_mode("safe")
    return {"mode": store.get_mode()}


# --- watcher tick: regime detect + drawdown breaker + dead-man watchdog -----

def _detect_regime_and_notify(symbol: str) -> dict:
    """Emit regime_shift via the proper regime classifier (ADX+vol), debounced by is_shift."""
    try:
        candles = _candles(symbol, limit=200)
    except Exception as e:  # exchange/indicator failure → tell the leader
        notify(events.engine_degraded_event(f"無法取得行情/指標：{e}"))
        return {"degraded": str(e)}
    rr = regime.classify(candles)
    prev = store.get_last_regime()
    if regime.is_shift(prev, rr.label):
        store.set_last_regime(rr.label)
        notify(events.regime_shift_event(prev, rr, status=_status_snapshot(symbol)))
        return {"regime": rr.label, "shifted": True, "prev": prev}
    if prev is None and rr.label != "unknown":
        store.set_last_regime(rr.label)  # set the baseline without emitting
    return {"regime": rr.label, "shifted": False}


def _watchdog_check() -> dict:
    """If the swarm stopped heartbeating, enter safe-mode (freeze new entries)."""
    age = store.heartbeat_age()
    if age is not None and age > settings.heartbeat_timeout_sec and store.get_mode() == "active":
        store.set_mode("safe")
        notify(events.safe_mode_event(
            f"swarm heartbeat 逾時 {int(age)}s（>{settings.heartbeat_timeout_sec}s），凍結新倉",
            status=_status_snapshot(settings.symbol)))
        return {"safe_mode": True, "age": age}
    return {"safe_mode": False, "age": age}


def _record_pnl_snapshot() -> dict:
    """One equity-curve point + the deterministic drawdown breaker (DEBT-5 / PRD §7.3)."""
    try:
        equity = _equity()
        unrealized = sum(float(p.get("unrealizedPnl") or 0) for p in exchange.fetch_positions())
    except Exception as e:
        return {"recorded": False, "error": str(e)}
    realized = store.realized_total()
    peak = store.equity_peak()
    peak = max(peak, equity) if peak is not None else equity
    dd = risk.check_drawdown(equity, peak, envelope())
    store.record_pnl_snapshot(equity, realized, unrealized, dd.drawdown_pct)
    if dd.breached and store.get_mode() == "active":  # circuit breaker: flatten + lock, then alert
        halt("flat", f"drawdown {dd.drawdown_pct:.2f}% ≥ {settings.max_drawdown_pct}%")
        store.record_risk_event("drawdown",
                                {"equity": equity, "peak": peak, "drawdown_pct": dd.drawdown_pct},
                                action_taken=dd.action or "flatten_and_lock")
        notify(events.risk_breach_event(
            f"drawdown {dd.drawdown_pct:.2f}% 觸發熔斷，已 flatten+lock",
            status=_status_snapshot(settings.symbol)))
    return {"recorded": True, "equity": equity, "drawdown_pct": dd.drawdown_pct, "breached": dd.breached}


def tick() -> dict:
    """One periodic self-check (regime + watchdog + equity snapshot), run by the watcher loop."""
    sym = settings.symbol
    return {
        "regime": _detect_regime_and_notify(sym),
        "watchdog": _watchdog_check(),
        "pnl_snapshot": _record_pnl_snapshot(),
    }
