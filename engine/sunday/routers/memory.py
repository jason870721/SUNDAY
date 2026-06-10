"""/api/memory — the agent memory warehouse (replaces the file-based MEMORY.md / RESEARCH.md).

Each agent keeps ONE long-term markdown doc here. The pattern, baked into every (non-watchdog)
agent's system prompt: read your doc on wake (``GET /api/memory/{agent}``), then overwrite it at
session end (``PUT /api/memory/{agent}``). Reads are open to any roster agent, so e.g. an analyst
can peek friday's watchlist/consensus. Token-free like the rest of the proxy.

``AGENTS`` is the swarm's memory-bearing roster (watchdog has none). Pinning it keeps the
dashboard index deterministic (every agent shows, even empty) and rejects typo'd names so the
store can't accumulate junk rows.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from .. import store

router = APIRouter(prefix="/api/memory", tags=["memory"])

AGENTS = ("friday", "trader", "analyst-flow", "analyst-news", "researcher", "risk-monitor", "reviewer")


class MemoryReq(BaseModel):
    content: str


def _require_agent(agent: str) -> None:
    if agent not in AGENTS:
        raise HTTPException(404, f"unknown agent '{agent}' — memory agents: {', '.join(AGENTS)}")


@router.get("")
def index() -> dict:
    """One entry per memory-bearing agent (no content — just updated_at + size), so the
    dashboard can list every agent including those that haven't written yet."""
    stored = {m["agent"]: m for m in store.list_memory()}
    items = [{
        "agent": a,
        "updated_at": (stored.get(a) or {}).get("updated_at"),
        "size": len((stored.get(a) or {}).get("content") or ""),
    } for a in AGENTS]
    return {"items": items}


@router.get("/{agent}")
def read(agent: str) -> dict:
    """An agent's full memory doc. Returns an empty doc (not 404) for a known agent that
    hasn't written yet, so the agent's first wake reads cleanly."""
    _require_agent(agent)
    return store.get_memory(agent) or {"agent": agent, "content": "", "updated_at": None}


@router.put("/{agent}")
def write(agent: str, req: MemoryReq) -> dict:
    """Overwrite an agent's memory doc wholesale (read → edit → write back at session end)."""
    _require_agent(agent)
    return store.set_memory(agent, req.content)
