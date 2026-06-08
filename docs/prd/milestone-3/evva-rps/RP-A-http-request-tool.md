# RP-A — Promote a generic `http_request` tool (ergonomics hedge)

> Draft for `../evva` ｜ source: Sunday milestone-3 (PRD §6.4) ｜ 2026-06-08
> Status: proposal (Sunday is the requester; evva owns implementation/scheduling)

## Problem (observed)

Sunday's swarm drives an external HTTP system using only generic `bash`+curl. Walking
the loop as the `analyst` agent, the single most error-prone step was **piping `curl`
into `python` to parse JSON / compute over a response** (quoting, missing
`Content-Type`, raw-array indexing). It is also the *load-bearing* path (every
agent↔Sunday interaction), and it inflates tokens (the model re-emits parsing
boilerplate each call). The Sunday PRD already flagged this as risk #1 and sanctioned
the fix as non-Sunday-specific (D12/§6.4).

## Proposal

Add a **generic** `http_request` tool to evva's toolset (e.g. `pkg/tools/web`):

```
http_request { method, url, headers?, body?, query? } → { status, headers, json|text }
```

- Generic + reusable by any HTTP integration — **not** Sunday-specific (no invariant-#4
  issue; Sunday's skills/manual still drive *what* to call).
- Replaces the fragile `curl | python` with structured I/O: the model gets parsed JSON,
  no shell-quoting, no re-emitted parser.
- Permission: gate by `method`/`url` (reads vs writes) — the same intent as the curl
  allow-rules, but on a clean tool surface instead of command-string matching.

## Acceptance

- `http_request` available to swarm members via `tools/active.yml`; GET auto-allows by
  rule, POST/DELETE ask in `default` mode.
- A swarm member can read `/signals` and act on the parsed body without spawning python.
- Downstream-embedder compile test (it's a public `pkg/tools` addition).

## Notes

- Additive, minor version bump. Sunday adopts it by swapping `bash`→`http_request` in
  the two skills + `active.yml`; the architecture (two HTTP boundaries) is unchanged.
