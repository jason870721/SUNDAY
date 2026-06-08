"""Backtest runner — replay history through the REAL engine over the sim adapters.

This is the L0/L1 layer of the feasibility doc's spectrum:

  - L0 (strategy):     run a FixedPolicy → measure one strategy's edge over history.
  - L1 (integration):  run a SwitchingPolicy → measure the *switching policy* (the
                       swarm's actual job; PRD §2.1 says the alpha lives here). The
                       LLM swarm is one implementation of a SwitchingPolicy; a
                       rule-based one (RegimePolicy) is another — both consume the
                       same panel and emit the same lever, so what we search offline
                       is what the agent should do online.

Because it drives the same Engine + strategy + risk core as live (just with sim
ports), the numbers describe the real engine. Costs (taker fee + optional funding)
and stops are modelled; metrics break out fees/funding so a "profit" can't hide
its costs. A backtest number is a hypothesis to be confirmed out-of-sample, never
a promise (feasibility-analysis.md §4).
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from . import regime, risk
from .adapters_sim import CollectSink, MemLedger, ReplayMarket, SimBroker, SimClock
from .engine import Engine, EngineConfig
from .market import Candles

_BARS_PER_YEAR = {"1h": 24 * 365, "4h": 6 * 365, "1d": 365, "30m": 48 * 365, "15m": 96 * 365}


@dataclass
class BacktestResult:
    equity_curve: list           # [(ts_ms, equity), ...]
    metrics: dict
    trades: list                 # closed round-trips (broker.trade_log)
    final_equity: float
    starting_cash: float


class FixedPolicy:
    """Always run one strategy (L0 — measure a single strategy's edge)."""

    def __init__(self, strategy: str) -> None:
        self.strategy = strategy

    def decide(self, candles: Candles, current: str) -> str:
        return self.strategy


class RegimePolicy:
    """Switch strategy by regime (L1 — the rule-based stand-in for the swarm).

    trending → momentum, ranging → mean_reversion, volatile → flat. This is the
    exact decision the leader agent makes from /advisor; backtesting it here is
    'backtesting the swarm' deterministically, and a sweep over its thresholds is
    a search for the switching-policy alpha (§2.1)."""

    MAP = {"trending": "momentum", "ranging": "mean_reversion", "volatile": "flat", "unknown": None}

    def decide(self, candles: Candles, current: str) -> str:
        return self.MAP.get(regime.classify(candles).label) or current


def run_backtest(candles: Candles, cfg: EngineConfig, policy, *, starting_cash: float = 10_000.0,
                 fee_bps: float = 4.0, funding_rate: float = 0.0, funding_every: int = 8,
                 warmup: int | None = None) -> BacktestResult:
    """Replay `candles` through the engine under `policy`. Returns equity curve + metrics."""
    symbol = cfg.symbol
    market = ReplayMarket(candles, symbol)
    broker = SimBroker(starting_cash, fee_rate=fee_bps / 10_000.0)
    ledger = MemLedger(strategy="flat", envelope=cfg.envelope)
    engine = Engine(market, broker, ledger, CollectSink(), SimClock(market), cfg)

    warmup = warmup if warmup is not None else cfg.slow + 30
    curve: list = []
    for t in range(warmup, len(candles)):
        market.cursor = t
        broker.mark(candles.closes[t])
        broker.check_stops(candles.highs[t], candles.lows[t])      # protective stop may fill
        if funding_rate and t % funding_every == 0:
            broker.apply_funding(funding_rate)
        # the policy (the "swarm") picks the active strategy from the tape it can see…
        window = market.ohlcv(symbol, cfg.timeframe, cfg.candles_limit)
        chosen = policy.decide(window, ledger.current_strategy(symbol))
        if chosen and chosen != ledger.current_strategy(symbol):
            ledger.set_strategy(symbol, chosen, f"policy→{chosen}", "policy")
        # …and the real engine executes it under the real risk fuses.
        try:
            engine.reconcile(symbol)
        except risk.RiskRejected:
            pass  # over-envelope entry blocked (logged) — same fuse as live
        curve.append((candles.times[t], broker.equity()))

    broker.mark(candles.closes[-1])
    broker.close(symbol)                                            # settle any open position at the last close
    final = broker.equity()
    return BacktestResult(curve, _metrics(curve, broker, starting_cash, candles, warmup, cfg.timeframe),
                          broker.trade_log, final, starting_cash)


def _metrics(curve, broker, start, candles, warmup, tf) -> dict:
    if not curve:
        return {}
    eq = [e for _, e in curve]
    total_return = (eq[-1] - start) / start * 100.0

    peak, mdd = eq[0], 0.0
    for e in eq:
        peak = max(peak, e)
        if peak > 0:
            mdd = max(mdd, (peak - e) / peak * 100.0)

    rets = [(eq[i] - eq[i - 1]) / eq[i - 1] for i in range(1, len(eq)) if eq[i - 1] > 0]
    sharpe = 0.0
    if len(rets) > 1:
        mean = sum(rets) / len(rets)
        sd = (sum((r - mean) ** 2 for r in rets) / len(rets)) ** 0.5
        if sd > 0:
            sharpe = mean / sd * math.sqrt(_BARS_PER_YEAR.get(tf, 24 * 365))

    closed = len(broker.trade_log)
    wins = sum(1 for tr in broker.trade_log if tr["pnl"] > 0)
    bh = (candles.closes[-1] - candles.closes[warmup]) / candles.closes[warmup] * 100.0
    return {
        "total_return_pct": round(total_return, 3),
        "buy_hold_return_pct": round(bh, 3),
        "max_drawdown_pct": round(mdd, 3),
        "sharpe": round(sharpe, 3),
        "trades": closed,
        "win_rate": round(wins / closed, 3) if closed else 0.0,
        "fees_paid": round(broker.fees, 4),
        "funding_paid": round(broker.funding, 4),
    }
