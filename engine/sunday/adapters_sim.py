"""Sim adapters — implement the same ports as the live edge, for backtesting.

ReplayMarket / SimBroker / MemLedger / CollectSink / SimClock satisfy the ports
in ports.py, so the SAME Engine that trades live runs over historical bars here.
The backtest therefore exercises the real strategy + execution + risk core, not a
reimplementation — which is the whole point of the G2.1 decoupling.

Pure stdlib (no ccxt/DB), so a backtest runs anywhere. SimBroker models a linear
USDⓈ-M perp: taker fee per fill, stop-trigger on the bar's high/low, optional
periodic funding, mark-to-market equity. Deliberate first-cut fidelity gaps
(documented for G2.2 hardening): close-fill (not next-bar-open), stop fills at the
stop price (no gap/slippage), no liquidation/margin model, single position per
symbol, constant funding. These are why a backtest number is a hypothesis, not a
promise (see docs/prd/milestone-2/feasibility-analysis.md §4.4).
"""

from __future__ import annotations

from datetime import datetime, timezone

from .market import Candles


class ReplayMarket:
    """MarketData over a fixed historical tape, gated by a cursor (no lookahead).

    `ohlcv(limit)` returns only bars up to and including `cursor`; the runner
    advances `cursor` one bar at a time, so the engine never sees the future.
    """

    def __init__(self, candles: Candles, symbol: str) -> None:
        self.full = candles
        self.symbol = symbol
        self.cursor = len(candles) - 1

    def ohlcv(self, symbol: str, tf: str, limit: int) -> Candles:
        f = self.full
        lo = max(0, self.cursor + 1 - limit)
        hi = self.cursor + 1
        return Candles(f.times[lo:hi], f.opens[lo:hi], f.highs[lo:hi],
                       f.lows[lo:hi], f.closes[lo:hi], f.volumes[lo:hi])

    def ticker(self, symbol: str) -> float:
        return self.full.closes[self.cursor]

    def funding_rate(self, symbol: str) -> float | None:
        return None


class SimBroker:
    """Broker with a simulated fill model (linear USDⓈ-M perp, USDT-margined)."""

    def __init__(self, starting_cash: float = 10_000.0, fee_rate: float = 0.0004) -> None:
        self.start = starting_cash
        self.fee_rate = fee_rate
        self.realized = 0.0
        self.fees = 0.0
        self.funding = 0.0
        self.side: str | None = None
        self.qty = 0.0
        self.entry = 0.0
        self.stop: float | None = None
        self.mark_price = 0.0
        self.n_entries = 0
        self.trade_log: list[dict] = []

    # --- runner-driven state ---
    def mark(self, price: float) -> None:
        self.mark_price = price

    def _unrealized(self) -> float:
        if not self.side:
            return 0.0
        diff = self.mark_price - self.entry
        return diff * self.qty if self.side == "long" else -diff * self.qty

    def wallet(self) -> float:
        return self.start + self.realized - self.fees - self.funding

    # --- Broker port ---
    def current_side(self, symbol: str) -> str | None:
        return self.side

    def exposure_usd(self) -> float:
        return self.qty * self.mark_price if self.side else 0.0

    def equity(self) -> float:
        return self.wallet() + self._unrealized()

    def unrealized_total(self) -> float:
        return self._unrealized()

    def capture_realized(self, symbol: str) -> float:
        return self._unrealized()

    def place_market(self, symbol: str, side: str, qty: float) -> dict:
        # engine always closes before flipping, so this opens from flat.
        self.fees += qty * self.mark_price * self.fee_rate
        self.side = "long" if side == "buy" else "short"
        self.qty = qty
        self.entry = self.mark_price
        self.n_entries += 1
        return {"id": self.n_entries, "status": "filled"}

    def set_leverage(self, symbol: str, leverage: int) -> None:
        pass  # first cut: leverage affects only liquidation, which we don't model yet

    def set_stop(self, symbol: str, close_side: str, qty: float, stop_price: float):
        self.stop = stop_price

    def close(self, symbol: str):
        if not self.side:
            return None
        pnl = self._unrealized()
        self.realized += pnl
        self.fees += self.qty * self.mark_price * self.fee_rate
        self.trade_log.append({"side": self.side, "entry": self.entry, "exit": self.mark_price,
                               "qty": self.qty, "pnl": pnl})
        self.side, self.qty, self.entry, self.stop = None, 0.0, 0.0, None
        return {"status": "closed"}

    def cancel_stops(self, symbol: str) -> None:
        self.stop = None

    # --- runner helpers (not part of the port) ---
    def check_stops(self, high: float, low: float) -> bool:
        """Trigger the protective stop if the bar's range crossed it. Fills at the stop."""
        if not self.side or self.stop is None:
            return False
        hit = (self.side == "long" and low <= self.stop) or (self.side == "short" and high >= self.stop)
        if hit:
            self.mark_price = self.stop          # fill at the stop price (no gap modelled)
            self.close("")
            return True
        return False

    def apply_funding(self, rate: float) -> None:
        """Periodic funding: longs pay when rate>0 (cost), shorts receive."""
        if not self.side:
            return
        notional = self.qty * self.mark_price
        self.funding += rate * notional if self.side == "long" else -rate * notional


class MemLedger:
    """In-memory Ledger for backtests (fast, disposable). Same interface as LiveLedger."""

    def __init__(self, strategy: str = "flat", envelope=None) -> None:
        self._strategy = strategy
        self._mode = "active"
        self._regime: str | None = None
        self._envelope = envelope
        self._realized = 0.0
        self._peak: float | None = None
        self.signals: list = []
        self.orders: list = []
        self.positions: list = []
        self.risk_events: list = []
        self.pnl: list = []
        self.strategy_sets: list = []
        self.rationale: str | None = None

    def current_strategy(self, symbol): return self._strategy
    def set_strategy(self, symbol, strategy, reason, set_by):
        self._strategy = strategy
        self.strategy_sets.append((strategy, reason, set_by))
    def record_signal(self, symbol, strategy, indicators, action): self.signals.append((strategy, action))
    def set_rationale(self, text): self.rationale = text
    def get_mode(self): return self._mode
    def set_mode(self, mode): self._mode = mode
    def close_open_positions(self, symbol, realized_pnl=None):
        if realized_pnl:
            self._realized += realized_pnl
        self.positions.append(("close", symbol, realized_pnl))
    def record_order(self, *a): self.orders.append(a)
    def record_position_open(self, *a, **kw): self.positions.append(("open",) + a)
    def record_risk_event(self, type_, detail, action_taken): self.risk_events.append((type_, action_taken))
    def get_last_regime(self, symbol): return self._regime
    def set_last_regime(self, symbol, regime): self._regime = regime
    def current_thesis(self, symbol): return None          # backtest doesn't drive directed
    def close_thesis(self, *a, **kw): pass
    def heartbeat_age(self): return None          # no dead-man in a backtest
    def realized_total(self): return self._realized
    def equity_peak(self): return self._peak
    def record_pnl_snapshot(self, equity, realized, unrealized, drawdown_pct):
        self.pnl.append((equity, drawdown_pct))
        self._peak = equity if self._peak is None else max(self._peak, equity)
    def get_envelope(self): return self._envelope
    def set_envelope(self, env, reason, set_by): self._envelope = env


class CollectSink:
    """EventSink that just collects emitted events (for assertions / inspection)."""

    def __init__(self) -> None:
        self.events: list = []

    def emit(self, event: dict):
        self.events.append(event)
        return {"collected": True}


class SimClock:
    """Clock driven by the replay's current bar time."""

    def __init__(self, market: ReplayMarket) -> None:
        self.market = market

    def now(self) -> datetime:
        ms = self.market.full.times[self.market.cursor]
        return datetime.fromtimestamp(ms / 1000, tz=timezone.utc)
