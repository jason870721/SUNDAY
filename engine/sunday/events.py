"""Outbound webhook events: Sunday → evva swarm (RP-9 ``POST /api/swarm/{ref}/event``).

PURE + stdlib (urllib, no httpx): builders assemble the ``{title, body, data, to}``
payload the swarm webapi expects; ``post`` fires it and NEVER raises (Sunday must keep
serving even when the swarm is down). Milestone-6 carries two event kinds — a
position's PnL crossing a step (req 5) and a price alert firing (req 6). Both are
**self-sufficient**: the payload includes the structured numbers + a suggested next
action so a woken agent can act on its first turn without a round-trip.
"""

from __future__ import annotations

import json
import urllib.request
from typing import Any


def build_event(title: str, body: str, data: dict | None = None, to: str = "leader") -> dict:
    """Assemble the swarm webhook payload: {title, body, data, to}."""
    return {"title": title, "body": body, "data": data or {}, "to": to}


def position_pnl_event(symbol: str, side: str, roi_pct: float, upnl: float | None,
                       mark: float | None, entry: float | None, step_pct: float,
                       to: str = "leader") -> dict:
    """`position_pnl`: an open position's ROI% crossed a `step_pct` boundary (req 5)."""
    arrow = "▲" if roi_pct >= 0 else "▼"
    title = f"{symbol} {side} ROI {arrow}{roi_pct:+.1f}%"
    body = (f"{symbol}（{side}）未實現損益 {roi_pct:+.1f}%"
            f"（uPnL={upnl}, mark={mark}, entry={entry}）— 每 {step_pct:.0f}% 通報一次。")
    return build_event(title, body, data={
        "event_type": "position_pnl",
        "symbol": symbol, "side": side, "roi_pct": round(roi_pct, 2),
        "unrealized_pnl": upnl, "mark": mark, "entry": entry,
        "suggested_action": "查 GET /api/account/positions 對帳，評估調整 TP/SL 或加減倉。",
    }, to=to)


def price_alert_event(alert: dict, price: float, to: str = "leader") -> dict:
    """`price_alert`: a user/agent alert condition fired (req 6)."""
    kind, sym, thr = alert.get("kind"), alert.get("symbol"), alert.get("threshold")
    desc = {
        "price_above": f"{sym} 突破 {thr}（現價 {price}）",
        "price_below": f"{sym} 跌破 {thr}（現價 {price}）",
        "pct_move": f"{sym} 自設定點波動達 ±{thr}%（現價 {price}）",
    }.get(kind, f"{sym} alert（現價 {price}）")
    return build_event(f"alert: {desc}", desc, data={
        "event_type": "price_alert",
        "alert_id": alert.get("id"), "symbol": sym, "kind": kind,
        "threshold": thr, "price": price, "note": alert.get("note"),
        "suggested_action": f"查 GET /api/klines?symbol={sym} 看脈絡，評估進出場或調整部位。",
    }, to=to)


def _build_request(url: str, payload: dict) -> urllib.request.Request:
    """A JSON POST request (data set → method defaults to POST)."""
    req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), method="POST")
    req.add_header("Content-Type", "application/json")
    return req


def post(url: str, payload: dict, timeout: float = 3.0) -> tuple[int | None, bool]:
    """Fire-and-forget POST. Returns (http_status, ok); never raises."""
    try:
        with urllib.request.urlopen(_build_request(url, payload), timeout=timeout) as resp:
            status = getattr(resp, "status", None) or resp.getcode()
            return status, 200 <= status < 300
    except Exception:
        return None, False  # swarm unreachable — caller logs it and carries on
