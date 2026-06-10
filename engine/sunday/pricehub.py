"""Realtime price hub (req 5/6) — websocket mark-price streams + a poll backstop.

One ``Realtime`` owns:

  * a **poll loop** (every ``monitor_poll_sec``) that re-reads the testnet position
    book (drives the monitor), refreshes the active-alert snapshot, and sweeps alert
    prices over REST — the always-on safety net; and
  * **websocket loops** (lower latency) on Binance combined ``@markPrice@1s`` streams:
    the **testnet** stream feeds the position monitor (positions are testnet, so their
    mark is testnet), the **mainnet** stream feeds the alerts (real market price).

The monitor fires on a bucket *change* and alerts fire *once*, so the ws and poll paths
are idempotent — running both never double-notifies. Streams reconnect with backoff and
re-subscribe whenever the held-position / alerted-symbol set changes.
"""

from __future__ import annotations

import asyncio
import json
import logging

from .alerts import AlertEngine
from .config import settings
from .monitor import Monitor

log = logging.getLogger("sunday.pricehub")

_WS_HOST = {"testnet": "fstream.binancefuture.com", "mainnet": "fstream.binance.com"}


class Realtime:
    def __init__(self) -> None:
        self.monitor = Monitor()
        self.alerts = AlertEngine()
        self._tasks: list[asyncio.Task] = []
        self._stopping = False
        self._last_equity_snap: float | None = None  # time.monotonic() of the last snapshot

    # -- lifecycle --------------------------------------------------------
    async def start(self) -> None:
        await asyncio.to_thread(self._seed)
        self._tasks.append(asyncio.create_task(self._poll_loop()))
        if settings.ws_enabled:
            self._tasks.append(asyncio.create_task(self._ws_loop("testnet")))   # monitor
            self._tasks.append(asyncio.create_task(self._ws_loop("mainnet")))   # alerts
        log.info("realtime started (poll=%ss ws=%s)", settings.monitor_poll_sec, settings.ws_enabled)

    def _seed(self) -> None:
        """Baseline silently so we don't webhook for every position on boot."""
        if settings.monitor_enabled and settings.binance_testnet_key:
            try:
                self.monitor.refresh_book(seed=True)
            except Exception as e:
                log.warning("seed book: %s", e)
        self.alerts.refresh()

    async def stop(self) -> None:
        self._stopping = True
        for t in self._tasks:
            t.cancel()
        for t in self._tasks:
            try:
                await t
            except (asyncio.CancelledError, Exception):
                pass
        self._tasks.clear()

    # -- poll backstop ----------------------------------------------------
    async def _poll_loop(self) -> None:
        while not self._stopping:
            await asyncio.sleep(settings.monitor_poll_sec)
            try:
                await asyncio.to_thread(self._poll_cycle)
            except asyncio.CancelledError:
                break
            except Exception as e:  # never let the loop die
                log.warning("poll cycle: %s", e)

    def _poll_cycle(self) -> None:
        if settings.monitor_enabled and settings.binance_testnet_key:
            self.monitor.refresh_book()        # positions -> monitor evaluation
        self.alerts.refresh()                  # reload active alerts
        self._rest_alert_sweep()               # backstop: evaluate alerts off REST
        self._maybe_snap_equity()              # drawdown high-water mark (throttled)

    def _maybe_snap_equity(self) -> None:
        """Record account equity at most every `equity_snap_sec` so /api/account/drawdown
        has a high-water mark to compare against. Best-effort — never breaks the cycle."""
        import time
        if not settings.binance_testnet_key:
            return
        now = time.monotonic()
        if self._last_equity_snap is not None and now - self._last_equity_snap < settings.equity_snap_sec:
            return
        from . import exchange, store
        try:
            eq = exchange.fetch_account().get("totalMarginBalance")
            if eq is not None:
                store.add_equity_snap(float(eq))
                self._last_equity_snap = now
        except Exception as e:
            log.debug("equity snap: %s", e)

    def _rest_alert_sweep(self) -> None:
        from . import exchange
        for sym in self.alerts.symbols():
            try:
                price = exchange.fetch_ticker(sym).get("last")
                if price is not None:
                    self.alerts.on_price(sym, float(price))
            except Exception as e:
                log.debug("alert sweep %s: %s", sym, e)

    # -- websocket loops --------------------------------------------------
    def _want(self, which: str) -> set[str]:
        return set(self.monitor.symbols()) if which == "testnet" else set(self.alerts.symbols())

    async def _ws_loop(self, which: str) -> None:
        backoff = 1
        while not self._stopping:
            syms = sorted(self._want(which))
            if not syms:
                await asyncio.sleep(3)
                continue
            try:
                await self._consume(which, syms)
                backoff = 1
            except asyncio.CancelledError:
                break
            except Exception as e:
                log.warning("ws %s: %s", which, e)
                await asyncio.sleep(min(backoff, 30))
                backoff *= 2

    async def _consume(self, which: str, syms: list[str]) -> None:
        import websockets  # lazy: a ws hiccup/missing dep degrades to the poll backstop
        streams = "/".join(f"{s.lower()}@markPrice@1s" for s in syms)
        url = f"wss://{_WS_HOST[which]}/stream?streams={streams}"
        want = set(syms)
        async with websockets.connect(url, ping_interval=120, open_timeout=10) as ws:
            log.info("ws %s subscribed to %d symbols", which, len(syms))
            while not self._stopping:
                if self._want(which) != want:        # subscription set changed → reconnect
                    return
                try:
                    msg = await asyncio.wait_for(ws.recv(), timeout=5)
                except asyncio.TimeoutError:
                    continue
                data = json.loads(msg).get("data") or {}
                sym, mark = data.get("s"), data.get("p")
                if not sym or mark is None:
                    continue
                if which == "testnet":
                    self.monitor.on_mark(sym, float(mark))
                else:
                    self.alerts.on_price(sym, float(mark))
