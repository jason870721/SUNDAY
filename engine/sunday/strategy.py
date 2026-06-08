"""Strategy engine — Gate-1's deliberately-simple strategies (PRD §7.2).

Each strategy can *evaluate* a tape into a Vote WITHOUT placing an order. That
split is the whole point of the milestone-3 ``/signals`` panel (PRD §7.9): the
engine can show an agent every candidate strategy's current read — indicators +
vote + rationale — so the agent decides "switch or not" over the engine's own
computed features instead of re-deriving them from raw OHLCV by hand. The live
decision path uses the *active* strategy's ``target_side``; the panel uses
``vote_all``. Both read the same ``indicators`` module (DRY → the panel is honest).

Gate-1 quality is deliberately not the point (PRD §2.1): these are EMA-cross and
Bollinger/RSI, on purpose. Alpha is Gate-2's problem, and lives in the *switching
policy*, not here.
"""

from __future__ import annotations

from dataclasses import dataclass

from . import indicators as ind
from .market import Candles

VALID_STRATEGIES: tuple[str, ...] = ("momentum", "mean_reversion", "flat")

# mean_reversion thresholds (Gate-1 defaults; deliberately simple)
_Z_BAND = 1.0      # |z| beyond 1σ is "stretched"
_RSI_OS = 35.0     # oversold
_RSI_OB = 65.0     # overbought
# momentum: ignore an EMA spread tighter than this (chop, not a real cross)
_FLAT_SPREAD_PCT = 0.05


@dataclass
class Vote:
    strategy: str
    vote: str                # "long" | "short" | "neutral"
    confidence: float        # 0..1
    indicators: dict
    rationale: str

    def as_dict(self) -> dict:
        return {
            "strategy": self.strategy,
            "vote": self.vote,
            "confidence": round(self.confidence, 3),
            "indicators": {k: (round(v, 4) if isinstance(v, float) else v) for k, v in self.indicators.items()},
            "rationale": self.rationale,
        }


def _clamp01(x: float) -> float:
    return 0.0 if x < 0.0 else 1.0 if x > 1.0 else x


def _neutral(strategy: str, reason: str, indicators: dict | None = None) -> Vote:
    return Vote(strategy, "neutral", 0.0, indicators or {}, reason)


def evaluate_momentum(c: Candles) -> Vote:
    ema20 = ind.ema(c.closes, 20)
    ema50 = ind.ema(c.closes, 50)
    if ema20 is None or ema50 is None:
        return _neutral("momentum", "資料不足（需 ≥50 根）")
    spread_pct = (ema20 - ema50) / ema50 * 100.0 if ema50 else 0.0
    indicators = {"ema20": ema20, "ema50": ema50, "spread_pct": spread_pct}
    if abs(spread_pct) < _FLAT_SPREAD_PCT:
        return _neutral("momentum", f"EMA 糾結（spread {spread_pct:+.2f}%），無趨勢", indicators)
    side = "long" if spread_pct > 0 else "short"
    conf = _clamp01(abs(spread_pct) / 2.0)  # ~2% spread → full confidence
    arrow = ">" if side == "long" else "<"
    rationale = f"EMA20({ema20:.1f}) {arrow} EMA50({ema50:.1f})，spread {spread_pct:+.2f}% → 順勢{'多' if side == 'long' else '空'}"
    return Vote("momentum", side, conf, indicators, rationale)


def evaluate_mean_reversion(c: Candles) -> Vote:
    bb = ind.bollinger(c.closes, 20, 2.0)
    rsi = ind.rsi(c.closes, 14)
    if bb is None or rsi is None:
        return _neutral("mean_reversion", "資料不足（需 ≥21 根）")
    z = bb["z"]
    indicators = {"rsi14": rsi, "bb_z": z, "bb_upper": bb["upper"], "bb_lower": bb["lower"]}
    if z <= -_Z_BAND and rsi <= _RSI_OS:
        conf = _clamp01(abs(z) / 2.0)
        return Vote("mean_reversion", "long", conf, indicators,
                    f"超賣：z={z:.2f}（<-{_Z_BAND}）、RSI {rsi:.0f}（≤{_RSI_OS:.0f}）→ 逆勢偏多")
    if z >= _Z_BAND and rsi >= _RSI_OB:
        conf = _clamp01(abs(z) / 2.0)
        return Vote("mean_reversion", "short", conf, indicators,
                    f"超買：z={z:.2f}（>{_Z_BAND}）、RSI {rsi:.0f}（≥{_RSI_OB:.0f}）→ 逆勢偏空")
    return _neutral("mean_reversion", f"未觸帶邊：z={z:.2f}、RSI {rsi:.0f}（中性）", indicators)


def evaluate_flat(_: Candles) -> Vote:
    # flat is a deliberate stance, not an absence of opinion — confidence 1.0.
    return Vote("flat", "neutral", 1.0, {}, "flat：空手，不進場（既有倉平掉）")


_EVALUATORS = {
    "momentum": evaluate_momentum,
    "mean_reversion": evaluate_mean_reversion,
    "flat": evaluate_flat,
}


def evaluate(strategy: str, c: Candles) -> Vote:
    """Vote for one strategy without trading."""
    fn = _EVALUATORS.get(strategy)
    if fn is None:
        raise ValueError(f"unknown strategy: {strategy!r}")
    return fn(c)


def vote_all(c: Candles) -> list[Vote]:
    """The /signals decision panel: the opinionated candidates (momentum +
    mean_reversion). flat is omitted — it always abstains, so it adds no signal."""
    return [evaluate_momentum(c), evaluate_mean_reversion(c)]


def target_side(strategy: str, c: Candles) -> str | None:
    """The side the *active* strategy wants the book to hold: 'long' | 'short' |
    None (flat / no entry). The executor turns this into a sized order under the
    envelope; risk.py has the final say."""
    if strategy == "flat":
        return None
    v = evaluate(strategy, c)
    return None if v.vote == "neutral" else v.vote
