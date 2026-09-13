#!/usr/bin/env bash
set -Eeuo pipefail
root="$(git rev-parse --show-toplevel)"; cd "$root"
bash scripts/agent-continuity-validate.sh
python3 -m compileall -q app worker scripts tests
python3 -m pytest -q
