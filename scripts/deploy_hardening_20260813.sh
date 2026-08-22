#!/usr/bin/env bash
set -euo pipefail

echo "RETIRED_DEPLOY_BLOCKED: deploy_hardening_20260813 used obsolete migration/filter policy."
echo "Use the current deployment path only after scripts/repo_policy_guard.py passes."
exit 64
