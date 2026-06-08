#!/usr/bin/env bash
# Run the engine's pure-logic unit tests (stdlib only — no deps, no DB needed).
#   ./scripts/run-tests.sh
set -eu
cd "$(dirname "$0")/../engine"
python3 -m unittest discover -s tests -t . "$@"
