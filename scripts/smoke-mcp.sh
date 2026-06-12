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

echo "→ MCP session (initialize / tools / calls)"
SUNDAY_MCP_URL="$BASE" python3 - <<'EOF'
import asyncio
import os

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

EXPECT = {"ping", "markets_list", "positions"}  # Phase 1 set


async def main() -> None:
    url = os.environ["SUNDAY_MCP_URL"] + "/mcp"
    async with streamablehttp_client(url) as (read, write, _):
        async with ClientSession(read, write) as s:
            await s.initialize()

            tools = {t.name for t in (await s.list_tools()).tools}
            missing = EXPECT - tools
            assert not missing, f"missing tools: {missing} (got {sorted(tools)})"

            r = await s.call_tool("ping", {})
            text = r.content[0].text
            assert "sunday-mcp" in text and "ok" in text, f"ping: {text!r}"
            assert "UNREACHABLE" not in text, f"engine down behind sidecar: {text!r}"
            print("  ping:", text)

            r = await s.call_tool("markets_list", {"page_size": 5})
            text = r.content[0].text
            assert not r.isError, f"markets_list errored: {text!r}"
            assert "has_more" in text and text.strip(), f"markets_list: {text!r}"
            print("  markets_list: %d lines" % len(text.splitlines()))

            r = await s.call_tool("positions", {})
            text = r.content[0].text
            assert not r.isError, f"positions errored: {text!r}"
            print("  positions:", text.splitlines()[0])

            print("smoke-mcp: OK — %d tools advertised" % len(tools))


asyncio.run(main())
EOF
