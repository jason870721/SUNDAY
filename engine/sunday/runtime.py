"""Process-wide handle to the running realtime hub.

A tiny module both ``app.py`` (which constructs the hub in lifespan) and the routers
(which nudge it to re-read alerts after a create/delete) can import without a cycle.
``realtime`` is None until the app starts and after it stops.
"""

from __future__ import annotations

from typing import Any

realtime: Any = None  # pricehub.Realtime — set by app lifespan
