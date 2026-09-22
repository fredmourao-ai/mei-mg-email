#!/usr/bin/env bash
set -Eeuo pipefail

root="$(git rev-parse --show-toplevel)"
cd "$root"

python_bin="${PYTHON_BIN:-}"
if [ -z "$python_bin" ]; then
  if command -v python3 >/dev/null 2>&1; then
    python_bin="$(command -v python3)"
  elif command -v python >/dev/null 2>&1; then
    python_bin="$(command -v python)"
  else
    echo "BLOCKED: Python is required for Absolute Audit V5 governance." >&2
    exit 43
  fi
fi

mode="${1:-manual}"
out_root="artifacts"
if [ "$mode" = "ci" ]; then
  mkdir -p     "$out_root/audit-governance-self-test"     "$out_root/global-audit-policy"
fi

"$python_bin" -m py_compile   scripts/certify-audit-manifest.py   scripts/validate-audit-governance.py   scripts/validate-global-audit-policy.py   scripts/validate-main-merge-provenance.py

"$python_bin" -m unittest   tests/test_certify_audit_manifest.py   tests/test_validate_main_merge_provenance.py

if [ "$mode" = "ci" ]; then
  "$python_bin" scripts/validate-audit-governance.py     --output-dir "$out_root/audit-governance-self-test"
  "$python_bin" scripts/validate-global-audit-policy.py     --output-dir "$out_root/global-audit-policy"
  test -s "$out_root/audit-governance-self-test/report.json"
  test -s "$out_root/audit-governance-self-test/report.md"
  test -s "$out_root/global-audit-policy/report.json"
  test -s "$out_root/global-audit-policy/report.md"
else
  "$python_bin" scripts/validate-audit-governance.py
  "$python_bin" scripts/validate-global-audit-policy.py
fi

echo "ABSOLUTE_AUDIT_GOVERNANCE_BRIDGE=PASS"
