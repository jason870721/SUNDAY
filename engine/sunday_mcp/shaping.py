"""Pure shaping: engine JSON → compact, decision-ready tool text (S3/S7).

Everything here is stdlib-only and takes plain dicts from the engine's
documented responses (see GET /manual). The output budget discipline lives
here: callers cap page sizes in their schemas, and these renderers emit one
line per row — together that keeps every tool comfortably under the 60k-char
design budget (evva truncates tool results at 100k).

Rendering conventions (shared by every Phase 2 tool):
  * prices pass the engine's precision through (no rounding policy here)
  * percentages: 2 decimals, explicit sign
  * USD magnitudes: k / M / B suffix
  * missing value: "?"
"""

from __future__ import annotations

MEMO_MAX = 60  # chars of memo echoed per position row (full memo is in the UI)


# ── number rendering ──────────────────────────────────────────────────────────

def fmt_price(v: float | int | None) -> str:
    if v is None:
        return "?"
    s = f"{float(v):.10f}".rstrip("0").rstrip(".")
    return s or "0"


def fmt_pct(v: float | int | None) -> str:
    if v is None:
        return "?"
    return f"{float(v):+.2f}%"


def fmt_usd(v: float | int | None) -> str:
    if v is None:
        return "?"
    n = float(v)
    for cut, suffix in ((1e9, "B"), (1e6, "M"), (1e3, "k")):
        if abs(n) >= cut:
            return f"{n / cut:.2f}{suffix}"
    return fmt_price(n)


def clip(s: str | None, limit: int = MEMO_MAX) -> str | None:
    if s is None:
        return None
    s = " ".join(s.split())  # memos render on one row line
    return s if len(s) <= limit else s[: limit - 1] + "…"


def page_tail(payload: dict) -> str:
    has_more = "true" if payload.get("has_more") else "false"
    return (f"page {payload.get('page', '?')} · total {payload.get('total', '?')}"
            f" · has_more: {has_more}")


# ── /api/markets ──────────────────────────────────────────────────────────────

def shape_markets(payload: dict) -> str:
    rows = payload.get("items") or []
    if not rows:
        return "no markets matched\n" + page_tail(payload)
    lines = [
        f"{r.get('symbol', '?')}  {fmt_price(r.get('last'))}"
        f"  {fmt_pct(r.get('change_pct'))}  {fmt_usd(r.get('quote_volume'))} vol"
        for r in rows
    ]
    return "\n".join(lines) + "\n" + page_tail(payload)


# ── /api/account/positions ────────────────────────────────────────────────────

def protection_str(prot: dict | None) -> str:
    """Render the engine's naked-position verdict. null ≠ "no legs" — it means
    the open-order books couldn't be read, and that uncertainty must survive
    into the agent's view (the engine's own semantics, see /manual)."""
    if prot is None:
        return "TP? SL?(unknown)"
    tp = "TP✓" if prot.get("take_profit") else "TP✗"
    if not prot.get("stop_loss"):
        sl = "SL✗(naked)"
    elif prot.get("sl_qty_covers") is False:
        sl = "SL△(partial)"
    else:
        sl = "SL✓"
    return f"{tp} {sl}"


def _position_line(r: dict) -> str:
    lev = r.get("leverage")
    line = (
        f"{r.get('symbol', '?')} {r.get('side', '?')} {fmt_price(r.get('qty'))}"
        f" @{fmt_price(r.get('entry'))} mark {fmt_price(r.get('mark'))}"
        f" roi {fmt_pct(r.get('roi_pct'))}"
        f" {lev if lev is not None else '?'}x {r.get('margin_mode') or '?'}"
        f" liq {fmt_pct(r.get('liq_distance_pct'))}"
        f" {protection_str(r.get('protection'))}"
    )
    memo = clip(r.get("memo"))
    return f"{line} | {memo}" if memo else line


def shape_positions(payload: dict) -> str:
    rows = payload.get("items") or []
    if not rows:
        return "no open positions"
    out = "\n".join(_position_line(r) for r in rows)
    if payload.get("has_more"):
        out += "\n" + page_tail(payload)
    return out
