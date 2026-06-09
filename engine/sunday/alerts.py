"""Price-alert engine (req 6).

``should_fire`` is the pure rule (stdlib, unit-tested): a price crossing an
above/below threshold, or moving ±pct from a reference captured at creation. The
``AlertEngine`` holds an in-memory snapshot of the active alerts (grouped by symbol)
that the price hub evaluates on each tick; a fired alert is marked ``triggered`` in
SQLite (one-shot) and dropped from the snapshot so it can't re-fire before the next
refresh. Heavy imports (store/events/config) are lazy so ``should_fire`` tests alone.
"""

from __future__ import annotations

import logging
import threading
from typing import Callable

log = logging.getLogger("sunday.alerts")

KINDS = ("price_above", "price_below", "pct_move")


def _default_alert_notify(alert: dict, price: float) -> None:
    """Production notifier: POST the price-alert event to the evva swarm webhook, and (if
    configured) push it to the User's Telegram. Both sinks are fire-and-forget — never raise."""
    from . import events, telegram
    from .config import settings
    events.post(settings.evva_webhook_url, events.price_alert_event(alert, price))
    telegram.send(telegram.alert_text(alert, price))


def should_fire(kind: str, threshold: float, ref_price: float | None, price: float | None) -> bool:
    """The pure trigger rule. pct_move needs a reference price (captured at creation)."""
    if price is None:
        return False
    if kind == "price_above":
        return price >= threshold
    if kind == "price_below":
        return price <= threshold
    if kind == "pct_move":
        if not ref_price:
            return False
        return abs((price - ref_price) / ref_price * 100.0) >= threshold
    return False


class AlertEngine:
    """Thread-safe snapshot of active alerts, evaluated on every price tick."""

    def __init__(self, notify: Callable[[dict, float], None] | None = None) -> None:
        self._by_symbol: dict[str, list[dict]] = {}
        self._lock = threading.RLock()
        self._notify = notify or _default_alert_notify

    def refresh(self) -> None:
        """Reload the active-alert snapshot from SQLite (called on boot, periodically,
        and after a create/delete)."""
        from . import store
        grouped: dict[str, list[dict]] = {}
        for a in store.active_alerts():
            grouped.setdefault(a["symbol"], []).append(a)
        with self._lock:
            self._by_symbol = grouped

    def symbols(self) -> list[str]:
        with self._lock:
            return list(self._by_symbol.keys())

    def on_price(self, symbol: str, price: float) -> None:
        with self._lock:
            candidates = list(self._by_symbol.get(symbol, []))
        for a in candidates:
            if should_fire(a["kind"], a["threshold"], a.get("ref_price"), price):
                self._fire(a, price)

    def _fire(self, alert: dict, price: float) -> None:
        from . import store
        store.mark_triggered(alert["id"], price)
        with self._lock:  # drop from the snapshot so it can't re-fire this cycle
            remaining = [x for x in self._by_symbol.get(alert["symbol"], []) if x["id"] != alert["id"]]
            if remaining:
                self._by_symbol[alert["symbol"]] = remaining
            else:  # last alert for this symbol gone → drop the key so the hub unsubscribes
                self._by_symbol.pop(alert["symbol"], None)
        self._notify(alert, price)
        log.info("price_alert #%s %s @ %s fired", alert["id"], alert["symbol"], price)
