#!/usr/bin/env bash
# Smoke the sunday-mcp sidecar end to end (PRD-9.1; extended each phase).
# Needs: a LIVE engine (:7777), a LIVE sidecar (:7780), and the SDK installed
# (pip install -e 'engine[mcp]').
#   ./scripts/smoke-mcp.sh
set -eu
BASE="${SUNDAY_MCP_URL:-http://127.0.0.1:7780}"

echo "→ healthz"
HZ=$(curl -fsS "$BASE/healthz")
echo "$HZ" | grep -q '"ok": *true' || { echo "FAIL: healthz not ok: $HZ"; exit 1; }
echo "$HZ"

echo "→ MCP session (initialize / tools / resource / per-tool calls)"
SUNDAY_MCP_URL="$BASE" python3 - <<'EOF'
import asyncio
import os

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client
from pydantic import AnyUrl

# Phase 2 set: ping + the 13 read-only tools (PRD-9.2). Asserted as an exact
# set so an accidental extra tool fails the smoke too, not just a missing one.
EXPECT = {
    "ping",
    "markets_list", "market_get", "klines", "indicators", "funding", "indices",
    "positions", "balance", "pnl_drawdown", "open_orders", "order_history",
    "trades", "protection_status",
}

BUDGET = 60_000  # S3: design ceiling per tool result (evva truncates at 100k)

# Worst LEGAL inputs where they exist (klines 500 bars, indicators full set at
# limit 400, page sizes at their schema caps) — the live counterpart of the
# unit budget tests. Account-group tools pass on the empty-data path when the
# testnet account is flat.
CALLS = [
    ("ping", {}),
    ("markets_list", {"page_size": 20}),
    ("market_get", {"symbol": "BTCUSDT"}),
    ("klines", {"symbol": "BTCUSDT", "interval": "1h", "limit": 500}),
    ("indicators", {"symbol": "BTCUSDT", "interval": "1h",
                    "set": "rsi,ema,sma,macd,bollinger,adx,atr", "limit": 400}),
    ("funding", {"symbol": "BTCUSDT"}),
    ("funding", {"symbol": "BTCUSDT", "history": True}),
    ("indices", {}),
    ("indices", {"key": "fear-greed"}),
    ("positions", {}),
    ("balance", {}),
    ("pnl_drawdown", {}),
    ("open_orders", {}),
    ("order_history", {"symbol": "BTCUSDT"}),
    ("trades", {"symbol": "BTCUSDT"}),
    ("protection_status", {"symbol": "BTCUSDT"}),
]


async def main() -> None:
    url = os.environ["SUNDAY_MCP_URL"] + "/mcp"
    async with streamablehttp_client(url) as (read, write, _):
        async with ClientSession(read, write) as s:
            await s.initialize()

            tools = {t.name for t in (await s.list_tools()).tools}
            assert tools == EXPECT, (
                f"tool set drift: extra={sorted(tools - EXPECT)}"
                f" missing={sorted(EXPECT - tools)}")

            uris = {str(r.uri) for r in (await s.list_resources()).resources}
            assert "sunday://manual" in uris, f"manual resource missing: {uris}"
            manual = await s.read_resource(AnyUrl("sunday://manual"))
            text = manual.contents[0].text
            assert len(text) > 5_000 and "## " in text, (
                f"manual looks wrong: {len(text)} chars")
            print(f"  resource sunday://manual: {len(text)} chars")

            for name, args in CALLS:
                r = await s.call_tool(name, args)
                text = r.content[0].text
                assert not r.isError, f"{name} errored: {text!r}"
                assert len(text) < BUDGET, f"{name}: {len(text)} chars ≥ {BUDGET}"
                # a normal-result 5xx passthrough means the engine side is sick
                assert "[sunday 5" not in text, f"{name} upstream 5xx: {text!r}"
                if name == "ping":
                    assert "UNREACHABLE" not in text, f"engine down: {text!r}"
                # * = the second variant of a twice-called tool (history / one key)
                label = name + ("*" if (args.get("history") or args.get("key")) else "")
                print(f"  {label:<18} {len(text):>6} chars · "
                      + text.splitlines()[0][:90])

            # worst-case combo really came back whole (acceptance: no truncation)
            r = await s.call_tool("klines", {"symbol": "BTCUSDT", "interval": "1h",
                                             "limit": 500})
            lines = r.content[0].text.splitlines()
            bars = sum(1 for l in lines if l.split(",")[0].isdigit())  # ts-first rows
            assert bars == 500, f"klines 500-bar pull came back short: {bars}"

            print(f"smoke-mcp: OK — {len(tools)} tools, manual resource,"
                  f" {len(CALLS)} calls within budget")


asyncio.run(main())
EOF
