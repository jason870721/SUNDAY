# milestone-3 T6 — evva refine-plan drafts (file these in `../evva`)

Per invariant #4 / D5, capability gaps in the **swarm runtime** are fixed in evva,
not in this repo. These three drafts were surfaced by walking the Sunday loop as an
agent (2026-06-08). They are authored here so the Sunday repo stays self-contained;
**to action them, copy each into `../evva/docs/roadmap/veronica/refine-plan/`** (next
RP numbers) and open as evva work. Sunday is the *requester*, not the implementer.

| draft | theme | one line |
| --- | --- | --- |
| [RP-A](RP-A-http-request-tool.md) | ergonomics | promote a generic `http_request` tool — `curl→python` is the agent's #1 error source |
| [RP-B](RP-B-event-routing-and-scoped-lever.md) | topology | route `risk_breach` → risk-monitor + give it a *narrow* halt lever (relieve the single-leader funnel) |
| [RP-C](RP-C-advice-loop-closure.md) | collaboration | leader replies "adopted / not (why)" to consulting agents — close the advice loop |

None require Sunday-specific code in evva (RP-A is generic infra; RP-B/RP-C are
swarm-runtime mechanics). They are independent of the Sunday engine and can be
filed/opened any time.
