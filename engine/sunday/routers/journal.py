"""/api/journal — the team's work log (the reviewer's daily reports, shown to the User).

The reviewer POSTs its daily review here and Sunday persists it, so the User can
browse the work log in the dashboard (Journal tab). Read endpoints paginate like
every other list (req 9). Token-free like the rest of the proxy.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from .. import store
from ..pagination import paginate

router = APIRouter(prefix="/api/journal", tags=["journal"])


class JournalReq(BaseModel):
    body: str = Field(min_length=1)                        # the report (markdown)
    title: str | None = Field(default=None, max_length=200)
    date: str | None = None                                # logical day YYYY-MM-DD; defaults to today (UTC)
    author: str | None = Field(default="reviewer", max_length=60)


@router.post("")
def create_entry(req: JournalReq) -> dict:
    """Append a work-log entry (the reviewer's daily report)."""
    body = req.body.strip()
    if not body:
        raise HTTPException(400, "body is required")
    return store.add_journal(body, title=req.title, date=req.date,
                             author=(req.author or "reviewer"))


@router.get("")
def list_entries(author: str | None = None, page: int = 1, page_size: int = 20) -> dict:
    """Work-log entries, newest first, paginated (optionally filter by author)."""
    return paginate(store.list_journal(author), page, page_size)


@router.get("/{entry_id}")
def get_entry(entry_id: int) -> dict:
    """One work-log entry (full markdown body)."""
    entry = store.get_journal(entry_id)
    if not entry:
        raise HTTPException(404, f"no journal entry #{entry_id}")
    return entry
