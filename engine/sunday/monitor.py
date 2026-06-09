"""Open-position PnL monitor (req 5).

Watches every open testnet position and webhooks the swarm each time a position's
ROI% crosses a ``step_pct`` boundary (±5%, ±10% …). ROI is derived from one source —
the mark price — so the websocket path (``on_mark``, fast) and the poll path
(``refresh_book``, the authority on entry/qty/margin) never disagree and flap a bucket.

Three pure helpers (stdlib, unit-tested, also used by /api/account):
``position_roi`` (ROI from a ccxt position), ``derived_roi`` (ROI from mark + book),
``bucket`` (which step an ROI sits in). The ``Monitor`` class holds the in-memory book
+ baselines and lazy-imports the heavy bits so the helpers test without ccxt.
"""

from __future__ import annotations

import logging
import math
import threading
from typing import Callable

log = logging.getLogger("sunday.monitor")


def _default_position_notify(event: dict) -> None:
    """Production notifier: POST the position-PnL event to the evva swarm webhook."""
    from . import events
    from .config import settings
    events.post(settings.evva_webhook_url, event)


def _f(v) -> float | None:
    try:
        return float(v) if v is not None else None
    except (TypeError, ValueError):
        return None


def position_roi(position: dict) -> float | None:
    """ROI% of a ccxt position. Prefer unified ``percentage`` (ROE%); else derive
    from unrealizedPnl / initialMargin (then / collateral)."""
    pct = _f(position.get("percentage"))
    if pct is not None:
        return pct
    upnl = _f(position.get("unrealizedPnl"))
    margin = _f(position.get("initialMargin")) or _f(position.get("collateral"))
    if upnl is not None and margin:
        return upnl / margin * 100.0
    return None


def derived_roi(entry: float | None, qty_signed: float | None,
                margin: float | None, mark: float | None) -> tuple[float | None, float | None]:
    """(roi_pct, unrealized_pnl) from a mark price and the position book.

    qty_signed is +contracts for a long, −contracts for a short, so
    uPnL = (mark − entry) × qty_signed works for both sides."""
    if entry is None or qty_signed is None or mark is None or not margin:
        return None, None
    upnl = (mark - entry) * qty_signed
    return upnl / margin * 100.0, upnl


def bucket(roi_pct: float, step_pct: float) -> int:
    """Which step the ROI falls in (step 5 → … −1, 0, 1, 2 …). The monitor fires when
    this integer changes for a position, i.e. each `step_pct` move."""
    if step_pct <= 0:
        return 0
    return int(math.floor(roi_pct / step_pct))


class Monitor:
    """Stateful consumer driven by the price hub. Thread-safe (RLock — the refresh
    thread and the ws loop both touch the book; reentrant so refresh→evaluate nests)."""

    def __init__(self, notify: Callable[[dict], None] | None = None,
                 step_pct: float | None = None) -> None:
        self.book: dict[str, dict] = {}      # symbol id (BTCUSDT) -> {side, entry, qty, margin, mark}
        self.buckets: dict[str, int] = {}    # symbol id -> last-notified step bucket
        self._lock = threading.RLock()
        self._notify = notify or _default_position_notify
        self._step_pct = step_pct            # None → read live settings (tests inject a fixed step)

    def _step(self) -> float:
        if self._step_pct is not None:
            return float(self._step_pct)
        from .config import settings
        return float(settings.monitor_step_pct)

    def symbols(self) -> list[str]:
        with self._lock:
            return list(self.book.keys())

    def refresh_book(self, seed: bool = False) -> None:
        """Re-read the testnet position book. New symbols seed their bucket silently;
        closed symbols are dropped. When not seeding, evaluate at the fresh marks so a
        crossing is caught even with the websocket off."""
        from . import exchange
        positions = exchange.fetch_positions()  # raw positionRisk rows
        seen: set[str] = set()
        with self._lock:
            for p in positions:
                amt = _f(p.get("positionAmt")) or 0.0   # signed: + long, − short
                if not amt:
                    continue
                sym = p.get("symbol")                   # "BTCUSDT" — matches the ws stream symbol
                entry, mark = _f(p.get("entryPrice")), _f(p.get("markPrice"))
                lev = _f(p.get("leverage"))
                notional = abs(amt) * (mark or 0.0)
                margin = (notional / lev) if (lev and notional) else None
                self.book[sym] = {"side": "long" if amt > 0 else "short", "entry": entry,
                                  "qty": amt, "margin": margin, "mark": mark}
                seen.add(sym)
                if sym not in self.buckets:
                    roi, _ = derived_roi(entry, self.book[sym]["qty"], margin, mark)
                    self.buckets[sym] = bucket(roi, self._step()) if roi is not None else 0
            for sym in list(self.book.keys()):
                if sym not in seen:
                    self.book.pop(sym, None)
                    self.buckets.pop(sym, None)
        if not seed:
            for sym in seen:
                self._evaluate(sym, self.book[sym]["mark"])

    def on_mark(self, symbol: str, mark: float) -> None:
        """A fresh mark tick from the websocket (symbol id, e.g. BTCUSDT)."""
        self._evaluate(symbol, mark)

    def _evaluate(self, symbol: str, mark: float | None) -> None:
        if mark is None:
            return
        with self._lock:
            b = self.book.get(symbol)
            if not b:
                return
            b["mark"] = mark
            roi, upnl = derived_roi(b["entry"], b["qty"], b["margin"], mark)
            if roi is None:
                return
            new = bucket(roi, self._step())
            if self.buckets.get(symbol) == new:
                return
            self.buckets[symbol] = new
            side, entry = b["side"], b["entry"]
        self._fire(symbol, side, roi, upnl, mark, entry)  # network — outside the lock

    def _fire(self, symbol, side, roi, upnl, mark, entry) -> None:
        from . import events  # pure builder (no config) — keeps the event shape testable
        self._notify(events.position_pnl_event(symbol, side, roi, upnl, mark, entry, self._step()))
        log.info("position_pnl %s %s roi=%+.1f%% fired", symbol, side, roi)

    def snapshot(self) -> list[dict]:
        with self._lock:
            out = []
            for sym, b in self.book.items():
                roi, upnl = derived_roi(b["entry"], b["qty"], b["margin"], b["mark"])
                out.append({"symbol": sym, "side": b["side"],
                            "roi_pct": round(roi, 2) if roi is not None else None,
                            "unrealized_pnl": upnl, "bucket": self.buckets.get(sym),
                            "mark": b["mark"], "entry": b["entry"], "qty": b["qty"]})
            return out
