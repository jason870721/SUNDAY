# RP-B — Per-event routing + a scoped (narrow) lever for a non-leader

> Draft for `../evva` ｜ source: Sunday milestone-3 (PRD §5 / §12.3 / §12.7) ｜ 2026-06-08
> Status: proposal

## Problem (observed)

In Sunday, **all** webhook events default to the leader (RP-9 `to:"leader"`) and **only**
the leader pulls levers. Crypto is highly correlated: a crash makes every symbol fire
`risk_breach` at once, and they all funnel into one leader run (drain B folds them). The
Sunday PRD calls this acceptable *only because the fast path is deterministic Python*
(§7.3) — but it explicitly warns "any design that leans on the leader for a fast reaction
is bad" (§5), and lists relief as open (§12.3/§12.7).

## Proposal

Two small, complementary swarm-runtime capabilities:

1. **Per-event-type default recipient** is already a 1-field change on the Sunday side
   (`to: "risk-monitor"`), but the *useful* version needs the recipient to be able to
   **act**, which today only the leader can. So:
2. **A scoped lever grant**: let the operator authorise a *specific* member to call a
   *narrow* set of dangerous actions (e.g. `risk-monitor` may `POST /halt` but not
   `/strategy`). Mechanism options for evva to weigh: a per-member permission allow-rule
   scope, or a role between "leader" and "consulting".

## Why evva (not Sunday)

Routing + who-may-act is **swarm topology**, not trading logic. Sunday only emits events
and exposes HTTP; it must not encode "who is allowed to halt".

## Acceptance

- A non-leader member can be granted exactly one dangerous action via config; other levers
  still ask/deny for it.
- `risk_breach` can be delivered to `risk-monitor`, which halts deterministically without a
  leader round-trip; the leader is still notified.
- The task-ledger leader-only invariant is untouched (this is about *levers*, not the ledger).

## Notes

- Keep it minimal — this is a relief valve for the correlated-burst case, not a general
  re-architecture. The leader remains the default authority.
