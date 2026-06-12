"""HTTP client for the Sunday engine — stdlib urllib only (invariants S1/S7).

Retry policy (S5): only GETs retry, only once, and only on connection-layer
failures (unreachable / timeout). HTTP 4xx/5xx are NOT failures — they come
back as normal Replies because the error body is exactly what the agent needs
to read (the engine explains -4016, trigger-side 400s, etc. in plain text).
Non-GET methods never retry: a timed-out order may have been accepted, and a
blind resend is how double positions happen.
"""

from __future__ import annotations

import json as _json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass

BASE_URL = os.environ.get("SUNDAY_BASE_URL", "http://127.0.0.1:7777")
TIMEOUT_S = float(os.environ.get("SUNDAY_MCP_UPSTREAM_TIMEOUT_S", "20"))
RETRY_GAP_S = 1.0

# Test seams — tests swap these for fakes (no network, no real sleeping).
opener = urllib.request.urlopen
_sleep = time.sleep


class EngineUnreachable(Exception):
    """Connection-layer failure (after the GET retry, where one applies)."""


@dataclass
class Reply:
    status: int
    json: dict | list | None
    text: str


def call(method: str, path: str, *, query: dict | None = None, body: dict | None = None,
         agent: str | None = None, timeout: float | None = None, retry: bool = True) -> Reply:
    """One engine call. `agent` becomes the X-Agent header (audit ledger, S4).

    `retry=False` opts a GET out of the retry (used by the health probe,
    which must answer fast and never block healthz for ~2s).
    """
    url = BASE_URL + path
    if query:
        pairs = {k: str(v) for k, v in query.items() if v is not None}
        if pairs:
            url += "?" + urllib.parse.urlencode(pairs)

    data = None
    headers = {"Accept": "application/json"}
    if body is not None:
        data = _json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    if agent:
        headers["X-Agent"] = agent

    req = urllib.request.Request(url, data=data, headers=headers, method=method.upper())
    t = TIMEOUT_S if timeout is None else timeout
    attempts = 2 if (req.get_method() == "GET" and retry) else 1

    last_err: Exception | None = None
    for i in range(attempts):
        try:
            with opener(req, timeout=t) as resp:
                return _reply(resp.status, resp.read())
        except urllib.error.HTTPError as e:
            # 4xx/5xx is a real answer, not a transport failure — never retried.
            return _reply(e.code, e.read())
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            last_err = e
            if i + 1 < attempts:
                _sleep(RETRY_GAP_S)

    raise EngineUnreachable(
        f"{req.get_method()} {path}: engine unreachable after {attempts} attempt(s): {last_err}"
    )


def probe_health(timeout: float = 0.5) -> dict:
    """Cheap engine liveness probe for ping / healthz — never raises."""
    try:
        r = call("GET", "/health", timeout=timeout, retry=False)
        return {"reachable": True, "status": r.status}
    except EngineUnreachable:
        return {"reachable": False, "status": None}


def _reply(status: int, raw: bytes) -> Reply:
    text = raw.decode("utf-8", errors="replace")
    try:
        parsed = _json.loads(text)
    except ValueError:
        parsed = None
    if not isinstance(parsed, (dict, list)):
        parsed = None  # scalars aren't useful as .json; the text carries them
    return Reply(status=status, json=parsed, text=text)
