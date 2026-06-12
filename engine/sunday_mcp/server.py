"""FastMCP server assembly — the ONLY module that imports the `mcp` SDK (S7).

Tools are deliberately thin: input is already schema-validated by the SDK,
so a tool body is `client.call → shaping/errors pure functions → str`.
Read tools carry readOnlyHint annotations (no effect under the swarm's
bypass permission mode today; hygiene for any stricter future host).
"""

from __future__ import annotations

import os
from typing import Annotated, Literal

from mcp.server.fastmcp import FastMCP
from mcp.server.fastmcp.exceptions import ToolError
from mcp.types import ToolAnnotations
from pydantic import Field
from starlette.requests import Request
from starlette.responses import JSONResponse

from . import __version__, client, errors, shaping

_READONLY = ToolAnnotations(readOnlyHint=True)


def _call(method: str, path: str, **kw) -> client.Reply:
    """client.call with the unreachable case mapped to a tool error (S6 hint)."""
    try:
        return client.call(method, path, **kw)
    except client.EngineUnreachable as e:
        raise ToolError(errors.UNREACHABLE_TEXT) from e


def build_server() -> FastMCP:
    port = int(os.environ.get("SUNDAY_MCP_PORT", "7780"))
    mcp = FastMCP("sunday", host="127.0.0.1", port=port)

    @mcp.tool(annotations=_READONLY)
    def ping() -> str:
        """Sidecar liveness + Sunday engine reachability probe (no market data)."""
        eng = client.probe_health()
        state = (f"engine reachable ({eng['status']})" if eng["reachable"]
                 else "engine UNREACHABLE — check GET /health (RUNBOOK.md)")
        return f"sunday-mcp {__version__} ok · {state}"

    @mcp.tool(annotations=_READONLY)
    def markets_list(
        sort: Literal["volume", "change", "symbol", "last"] = "volume",
        order: Literal["desc", "asc"] = "desc",
        search: str | None = None,
        page: Annotated[int, Field(ge=1)] = 1,
        page_size: Annotated[int, Field(ge=1, le=20)] = 10,
    ) -> str:
        """Tradeable USDⓈ-M perp markets, one line each: SYMBOL last 24h% volume
        (mainnet prices). `search` filters by symbol substring (e.g. "BTC").
        Full API contract: GET /manual on the engine."""
        q: dict = {"sort": sort, "order": order, "page": page, "page_size": page_size}
        if search:
            q["symbol"] = search
        r = _call("GET", "/api/markets", query=q)
        if errors.is_error(r):
            return errors.upstream_error_text(r)
        return shaping.shape_markets(r.json or {})

    @mcp.tool(annotations=_READONLY)
    def positions() -> str:
        """Open testnet positions, one line each: side/qty/entry/mark/ROI%/leverage/
        margin mode/liquidation distance/TP-SL protection verdict/memo.
        SL✗(naked) or SL△(partial) means the position is not fully protected."""
        r = _call("GET", "/api/account/positions", query={"page_size": 50})
        if errors.is_error(r):
            return errors.upstream_error_text(r)
        return shaping.shape_positions(r.json or {})

    @mcp.custom_route("/healthz", methods=["GET"])
    async def healthz(_: Request) -> JSONResponse:
        # Always 200; the body tells the truth (sidecar up, engine maybe not).
        return JSONResponse({"ok": True, "version": __version__,
                             "engine": client.probe_health()})

    return mcp


def main() -> None:
    build_server().run(transport="streamable-http")
