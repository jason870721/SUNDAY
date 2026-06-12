"""Error rendering for tool results (S7, stdlib-only).

Two distinct shapes, mirroring the http_request philosophy the swarm already
knows:

  * upstream HTTP 4xx/5xx → a NORMAL tool result, body passed through verbatim
    — the engine's error text is the actionable part (it explains -4016,
    wrong-side triggers, precision violations…). Phase 2 adds the known-code
    hint lines on top.
  * connection-layer failure → a tool ERROR (the caller raises with
    UNREACHABLE_TEXT) so the agent knows to degrade, not to re-parse.
"""

from __future__ import annotations

from .client import Reply

UNREACHABLE_TEXT = ("sunday engine unreachable after retry — check GET /health; "
                    "fall back to http_request if urgent (see RUNBOOK.md)")


def is_error(reply: Reply) -> bool:
    return reply.status >= 400


def upstream_error_text(reply: Reply) -> str:
    return f"[sunday {reply.status}] {reply.text.strip()}"
