"""/api/reports — friday's User-facing notices (the dashboard Reports page).

When something important happens — a large profit, a large loss, a system error — friday
POSTs a report here; Sunday persists it and the User reads it on the dashboard, newest first.
Distinct from /api/journal (the reviewer's scheduled daily post-mortems): reports are
event-driven "you should know this now" notices. Body is markdown, unbounded — clarity first.
Token-free like the rest of the proxy.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from .. import store
from ..pagination import paginate

router = APIRouter(prefix="/api/reports", tags=["reports"])

KINDS = ("info", "profit", "loss", "system")   # tags the Reports page color-codes


class ReportReq(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    body: str = Field(min_length=1)                       # markdown, unbounded
    kind: str = "info"                                    # info | profit | loss | system


@router.post("")
def create_report(req: ReportReq) -> dict:
    """Post a report. `kind` outside the known set is stored as 'info'."""
    body = req.body.strip()
    title = req.title.strip()
    if not body or not title:
        raise HTTPException(400, "title and body are required")
    kind = req.kind if req.kind in KINDS else "info"
    return store.add_report(title, body, kind)


@router.get("")
def list_reports(kind: str | None = None, page: int = 1, page_size: int = 20) -> dict:
    """Reports newest first, paginated (optionally filter by `kind`)."""
    return paginate(store.list_reports(kind), page, page_size)


@router.get("/{report_id}")
def get_report(report_id: int) -> dict:
    """One report (full markdown body)."""
    r = store.get_report(report_id)
    if not r:
        raise HTTPException(404, f"no report #{report_id}")
    return r
