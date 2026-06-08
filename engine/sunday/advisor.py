"""advisor.py — the agent's decision-support panel (the "best tool to make money").

Pure + unit-testable. Given a tape (+ the perp funding rate), it returns, for one
symbol:

- the **regime** read (trending / ranging / volatile) from ADX + realized vol,
- each candidate strategy's **vote** (momentum / mean_reversion) with the indicators
  behind it, a confidence, and a rationale,
- the **funding context** (a perps-specific edge: who pays whom, annualised),
- a data-driven **recommendation** (which strategy the regime + signals + funding
  favour, and why).

friday/analyst read this (`GET /advisor`) to decide *whether to switch and to what*
over the engine's own computed features — instead of eyeballing raw OHLCV. Per the
PRD (§2.1) the swarm's alpha lives in the *switching policy*, so this panel is the
single highest-leverage tool to invest in. It never trades; it only informs.
"""

from __future__ import annotations

from . import indicators as ind
from . import regime as rg
from .market import Candles

# mean_reversion thresholds (shared with strategy.py's selectable strategy)
MR_Z_BAND = 1.0
MR_RSI_OS = 35.0
MR_RSI_OB = 65.0
MOM_FLAT_SPREAD_PCT = 0.05   # EMA spread tighter than this = no real trend

# Binance USDⓈ-M funding settles every 8h → 3×/day. These gate the funding "bias".
_FUNDING_HOT = 0.0005    # |rate| ≥ this (0.05%/8h ≈ 55%/yr) is a meaningful tilt


def _clamp01(x: float) -> float:
    return 0.0 if x < 0.0 else 1.0 if x > 1.0 else x


def momentum_vote(closes: list[float], fast: int = 20, slow: int = 50) -> dict:
    ef, es = ind.ema(closes, fast), ind.ema(closes, slow)
    if ef is None or es is None:
        return {"strategy": "momentum", "vote": "neutral", "confidence": 0.0,
                "indicators": {}, "rationale": f"資料不足（需 ≥{slow} 根）"}
    spread = (ef - es) / es * 100.0 if es else 0.0
    inds = {"ema_fast": round(ef, 2), "ema_slow": round(es, 2), "spread_pct": round(spread, 3)}
    if abs(spread) < MOM_FLAT_SPREAD_PCT:
        return {"strategy": "momentum", "vote": "neutral", "confidence": 0.0,
                "indicators": inds, "rationale": f"EMA 糾結（spread {spread:+.2f}%），無趨勢"}
    side = "long" if spread > 0 else "short"
    return {"strategy": "momentum", "vote": side, "confidence": round(_clamp01(abs(spread) / 2.0), 3),
            "indicators": inds,
            "rationale": f"EMA{fast}{'>' if side == 'long' else '<'}EMA{slow}（spread {spread:+.2f}%）→ 順勢{side}"}


def mean_reversion_vote(closes: list[float]) -> dict:
    bb, rsi = ind.bollinger(closes, 20, 2.0), ind.rsi(closes, 14)
    if bb is None or rsi is None:
        return {"strategy": "mean_reversion", "vote": "neutral", "confidence": 0.0,
                "indicators": {}, "rationale": "資料不足（需 ≥21 根）"}
    z = bb["z"]
    inds = {"rsi14": round(rsi, 1), "bb_z": round(z, 2)}
    if z <= -MR_Z_BAND and rsi <= MR_RSI_OS:
        return {"strategy": "mean_reversion", "vote": "long", "confidence": round(_clamp01(abs(z) / 2.0), 3),
                "indicators": inds, "rationale": f"超賣 z={z:.2f}、RSI {rsi:.0f} → 逆勢偏多"}
    if z >= MR_Z_BAND and rsi >= MR_RSI_OB:
        return {"strategy": "mean_reversion", "vote": "short", "confidence": round(_clamp01(abs(z) / 2.0), 3),
                "indicators": inds, "rationale": f"超買 z={z:.2f}、RSI {rsi:.0f} → 逆勢偏空"}
    return {"strategy": "mean_reversion", "vote": "neutral", "confidence": 0.0,
            "indicators": inds, "rationale": f"未觸帶邊 z={z:.2f}、RSI {rsi:.0f}（中性）"}


def funding_context(funding_rate: float | None) -> dict:
    """Interpret the perp funding rate (per-8h fraction). Positive = longs pay shorts."""
    if funding_rate is None:
        return {"rate": None, "annualized_pct": None, "bias": "unknown",
                "note": "無 funding 資料"}
    annual = funding_rate * 3 * 365 * 100.0
    if funding_rate >= _FUNDING_HOT:
        bias, note = "favors_short", f"多單付高 funding（年化 {annual:+.0f}%），持多成本高、偏空有利"
    elif funding_rate <= -_FUNDING_HOT:
        bias, note = "favors_long", f"空單付 funding（年化 {annual:+.0f}%），持多反而收 funding、偏多有利"
    else:
        bias, note = "neutral", f"funding 中性（年化 {annual:+.0f}%）"
    return {"rate": round(funding_rate, 6), "annualized_pct": round(annual, 1), "bias": bias, "note": note}


def recommend(regime_label: str, votes: list[dict], funding: dict) -> dict:
    """Data-driven hint: which strategy the regime + signals + funding favour."""
    by_name = {v["strategy"]: v for v in votes}
    if regime_label == "volatile":
        return {"strategy": "flat", "direction": None,
                "why": "高波動盤 → 建議 flat 觀望，避免被掃"}
    if regime_label == "trending":
        mv = by_name.get("momentum", {})
        rec = {"strategy": "momentum", "direction": mv.get("vote"),
               "why": f"趨勢盤（{mv.get('rationale', '')}）"}
    else:  # ranging / unknown
        rv = by_name.get("mean_reversion", {})
        if rv.get("vote") in ("long", "short"):
            rec = {"strategy": "mean_reversion", "direction": rv.get("vote"),
                   "why": f"震盪盤且觸帶邊（{rv.get('rationale', '')}）"}
        else:
            rec = {"strategy": "flat", "direction": None,
                   "why": "震盪盤但未觸帶邊 → 無明確 edge，建議 flat 等訊號"}
    # funding caveat: warn when the recommended direction fights the funding tilt
    d = rec.get("direction")
    if d == "long" and funding.get("bias") == "favors_short":
        rec["funding_caveat"] = funding["note"]
    elif d == "short" and funding.get("bias") == "favors_long":
        rec["funding_caveat"] = funding["note"]
    return rec


def advise(candles: Candles, funding_rate: float | None, active: str,
           symbol: str = "", fast: int = 20, slow: int = 50) -> dict:
    """Assemble the full decision-support panel (the /advisor body)."""
    closes = candles.closes
    regime = rg.classify(candles)
    votes = [momentum_vote(closes, fast, slow), mean_reversion_vote(closes)]
    funding = funding_context(funding_rate)
    return {
        "symbol": symbol or "",
        "active": active,
        "regime": regime.as_dict(),
        "funding": funding,
        "votes": votes,
        "recommendation": recommend(regime.label, votes, funding),
    }
