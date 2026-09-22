#!/usr/bin/env bash
set -Eeuo pipefail
root="$(git rev-parse --show-toplevel)"
cd "$root"
bash scripts/absolute-audit-governance-validate.sh "${1:-manual}"

resolve_python() {
  local common_dir common_root candidate
  local -a candidates=()

  if [ -n "${GOVERNANCE_PYTHON:-}" ]; then
    candidates+=("$GOVERNANCE_PYTHON")
  fi
  if [ -n "${VIRTUAL_ENV:-}" ]; then
    candidates+=("$VIRTUAL_ENV/bin/python" "$VIRTUAL_ENV/Scripts/python.exe")
  fi
  candidates+=("$root/.venv/bin/python" "$root/.venv/Scripts/python.exe")

  common_dir="$(git rev-parse --git-common-dir)"
  case "$common_dir" in
    /*) ;;
    *) common_dir="$root/$common_dir" ;;
  esac
  common_dir="$(cd "$common_dir" && pwd)"
  common_root="$(dirname "$common_dir")"
  if [ "$common_root" != "$root" ]; then
    candidates+=("$common_root/.venv/bin/python" "$common_root/.venv/Scripts/python.exe")
  fi
  if command -v python3 >/dev/null 2>&1; then
    candidates+=("$(command -v python3)")
  fi

  for candidate in "${candidates[@]}"; do
    [ -x "$candidate" ] || continue
    if "$candidate" -c "import pytest" >/dev/null 2>&1; then
      printf "%s\n" "$candidate"
      return 0
    fi
  done
  return 1
}

PYTHON_BIN="$(resolve_python)" || {
  echo "BLOCKED: no Python interpreter with pytest is available for repository governance validation." >&2
  exit 43
}

bash scripts/agent-continuity-validate.sh
"$PYTHON_BIN" -m compileall -q app worker scripts tests
"$PYTHON_BIN" -m pytest -q
