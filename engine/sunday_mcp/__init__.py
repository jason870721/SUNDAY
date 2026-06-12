"""sunday_mcp — the Sunday MCP sidecar (milestone-9).

A stateless typed-tool adapter between the evva swarm and the Sunday engine:
a FastMCP server (streamable HTTP, :7780) whose tools call the engine's HTTP
API on :7777 and render compact, decision-ready text.

Invariants (docs/prd/milestone-9/README.md, S-series):
  S1  no keys, no state — only ever talks to the local engine over HTTP
  S5  non-idempotent writes are NEVER auto-retried (GET-only retry, once)
  S7  pure logic (shaping / errors) is stdlib-only and unit-testable without
      the `mcp` SDK; server.py is the only module that imports it
"""

__version__ = "0.1.0"
