"""User-facing Telegram notifications (milestone-8).

A SECOND outbound channel alongside the evva swarm webhook (``events.py``): where
``events`` talks to AGENTS, this talks to the USER's phone. Same discipline as ``events``
— PURE + stdlib (``urllib``, no httpx) and fire-and-forget: ``send`` NEVER raises and is
a **no-op unless both ``TELEGRAM_BOT_TOKEN`` and ``TELEGRAM_CHAT_ID`` are set**, so an
unconfigured deploy behaves exactly as before (this is how req T3 stays opt-in and how the
milestone-6 invariants survive — keys live engine-side, agents still hold only HTTP).

Three triggers: a friday report (the primary ask), a price alert firing, and a position's
PnL crossing a step. The text builders are pure functions (stdlib, unit-tested without any
network); only ``send`` touches config + the network.
"""

from __future__ import annotations

import json
import ssl
import urllib.request

_API = "https://api.telegram.org/bot{token}/sendMessage"

_REPORT_ICON = {"profit": "🟢", "loss": "🔴", "system": "⚙️", "info": "ℹ️"}
_ALERT_DESC = {
    "price_above": "突破 {thr}（現價 {price}）",
    "price_below": "跌破 {thr}（現價 {price}）",
    "pct_move": "自設定點波動達 ±{thr}%（現價 {price}）",
}

_ssl_cache: ssl.SSLContext | None = None


def _ssl_ctx() -> ssl.SSLContext:
    """TLS context with certifi's CA bundle when available — some Python installs lack a
    usable system CA store and would otherwise CERTIFICATE_VERIFY_FAILED on api.telegram.org."""
    global _ssl_cache
    if _ssl_cache is None:
        try:
            import certifi
            _ssl_cache = ssl.create_default_context(cafile=certifi.where())
        except Exception:
            _ssl_cache = ssl.create_default_context()
    return _ssl_cache


def _esc(s: object) -> str:
    """Escape the three characters Telegram's HTML parse_mode reserves."""
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _clip(s: str, n: int) -> str:
    s = s.strip()
    return s if len(s) <= n else s[: n - 1].rstrip() + "…"


# --------------------------------------------------------------------------
# Pure text builders (no config, no network — unit-tested directly)
# --------------------------------------------------------------------------

def report_text(title: str, body: str, kind: str = "info") -> str:
    """friday's User-facing report → a Telegram message (HTML). Body is trimmed; the full
    markdown lives on the dashboard Reports page."""
    icon = _REPORT_ICON.get(kind, _REPORT_ICON["info"])
    head = f"{icon} <b>{_esc(title)}</b>  <i>({_esc(kind)})</i>"
    return f"{head}\n\n{_esc(_clip(body, 700))}\n\n— Sunday · 完整內容見 dashboard ▸ Reports"


def alert_text(alert: dict, price: float) -> str:
    """A fired price alert → a Telegram message (HTML)."""
    sym = alert.get("symbol")
    desc = _ALERT_DESC.get(str(alert.get("kind")), "提醒（現價 {price}）").format(
        thr=alert.get("threshold"), price=price)
    note = alert.get("note")
    tail = f"\n📝 {_esc(note)}" if note else ""
    return f"🔔 <b>{_esc(sym)}</b> {_esc(desc)}{tail}\n\n— Sunday · 價格提醒"


def position_text(event: dict) -> str:
    """A position-PnL step crossing → a Telegram message (HTML). Reads the already-built
    ``events.position_pnl_event`` payload so the monitor passes its event straight through."""
    d = event.get("data", {})
    roi = d.get("roi_pct")
    sym, side = _esc(d.get("symbol")), _esc(d.get("side"))
    if not isinstance(roi, (int, float)):
        return f"<b>{sym}</b> {side} — {_esc(event.get('title'))}\n\n— Sunday · 持倉損益通報"
    arrow = "▲" if roi >= 0 else "▼"
    return (f"{arrow} <b>{sym}</b> <i>{side}</i>  ROI {roi:+.1f}%\n"
            f"uPnL {d.get('unrealized_pnl')} · mark {d.get('mark')} · entry {d.get('entry')}\n\n"
            f"— Sunday · 持倉損益通報")


# --------------------------------------------------------------------------
# Network sink (config + I/O) — never raises, no-op when unconfigured
# --------------------------------------------------------------------------

def _creds() -> tuple[str, str]:
    """(bot_token, chat_id) read defensively — getattr so a partial/stub settings object
    can't make us raise (the 'never raises' contract holds even off the happy path)."""
    from .config import settings
    return (getattr(settings, "telegram_bot_token", "") or "",
            str(getattr(settings, "telegram_chat_id", "") or ""))


def enabled() -> bool:
    """True only when both a bot token and a chat id are configured."""
    token, chat = _creds()
    return bool(token and chat)


def send(text: str, timeout: float = 4.0) -> tuple[int | None, bool]:
    """Fire-and-forget POST to Telegram. Returns (http_status, ok); NEVER raises. A no-op
    (returns (None, False)) when the bot token / chat id aren't configured."""
    token, chat = _creds()
    if not token or not chat:
        return None, False
    payload = {"chat_id": chat, "text": text[:4096], "parse_mode": "HTML",
               "disable_web_page_preview": True}
    req = urllib.request.Request(
        _API.format(token=token), data=json.dumps(payload).encode("utf-8"),
        method="POST", headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=_ssl_ctx()) as resp:
            status = getattr(resp, "status", None) or resp.getcode()
            return status, 200 <= status < 300
    except Exception:
        return None, False  # Telegram unreachable / bad token — degrade silently
