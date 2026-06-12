"""/api/memory — the team's PUBLICATION boards (User-facing, read by teammates over HTTP).

Since evva wave-5 (RP-25) every swarm member keeps its private working memory natively in
evva (``agents/{main,sub}/<name>/memory/``); this endpoint is no longer a per-agent warehouse.
What remains here are the two docs that are deliberately PUBLISHED — cross-agent contracts the
User also reads on the dashboard Memory tab:

- ``friday``     — the team constitution: risk consensus, watchlist, position theses, standing
                   rules. friday pre-flights his own orders against it, risk-monitor patrols against it.
- ``researcher`` — the research log: dated leads/ideas the User and friday browse.

Pattern unchanged: ``GET`` the whole doc, edit, ``PUT`` it back (whole-doc overwrite).

``AGENTS`` pins the publishing roster: the dashboard index stays deterministic and typo'd
names are rejected so the store can't accumulate junk rows.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from .. import store

router = APIRouter(prefix="/api/memory", tags=["memory"])

AGENTS = ("friday", "researcher")


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
