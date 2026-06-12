"""`python -m sunday_mcp` — run the sidecar (streamable HTTP on :7780).

The `mcp` SDK is an optional dependency group (engine[mcp], invariant S7):
imported lazily here so the engine and the unit tests never need it, and a
missing install fails with one actionable line instead of a traceback.
"""

from __future__ import annotations

import sys


def main() -> int:
    try:
        from .server import main as run
    except ModuleNotFoundError as e:
        if e.name == "mcp" or (e.name or "").startswith("mcp."):
            print("sunday-mcp: the 'mcp' SDK is not installed — run:"
                  " pip install -e 'engine[mcp]'", file=sys.stderr)
            return 1
        raise
    run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
