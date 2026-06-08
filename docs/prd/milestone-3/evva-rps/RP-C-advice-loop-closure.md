# RP-C — Close the advice loop: leader replies "adopted / not (why)"

> Draft for `../evva` ｜ source: Sunday milestone-3 (agent-POV walkthrough) ｜ 2026-06-08
> Status: proposal

## Problem (observed)

In a consulting-role swarm (Sunday: analyst/risk/reporter/reviewer advise, only the leader
acts), a consulting agent `send_message`s advice to the leader and then… hears nothing.
Whether the leader adopted the advice, and why, never comes back. The consulting agent is
shouting into a void: it cannot calibrate or improve, and the operator can't see the
*reasoning* link between advice and action. The current worker/leader protocol
(`internal/swarm/teamprompt.go`: `leaderProtocol` / `workerProtocol`) tells workers to
report up, but does not tell the leader to **report the decision back down**.

## Proposal

Strengthen the **leader protocol** (one prompt section, no new mechanism — it reuses
`send_message`) to close the loop:

> When a teammate's advice or report drives (or doesn't drive) a decision, reply to them
> with the outcome and a one-line why ("adopted — switching to mean_reversion" /
> "not yet — waiting for confirmation because …"). A teammate who can't see whether their
> input landed can't improve.

Optionally surface the linkage in the web timeline (advice → decision), but the prompt
change alone delivers the behaviour.

## Why evva (not Sunday)

This is a property of the **swarm collaboration protocol** (mesh + bus + roles), injected
by evva into every member (`teamprompt.go`). Sunday has no say in how teammates talk.

## Acceptance

- After a consulting agent advises, the leader's protocol prompts a brief decision reply;
  e2e shows the reply arriving back to the adviser.
- No regression to existing worker→leader reporting.
- Cheap: a prompt-section addition + an e2e assertion; no new tool, no schema.

## Notes

- Pairs naturally with RP-B (if a non-leader gains a scoped lever, the same "say what you
  did and why" discipline applies to it).
