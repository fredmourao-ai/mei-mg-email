from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "audit_temporary_docker_resources.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("audit_temporary_docker_resources", MODULE_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("unable to load temporary Docker resource auditor")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_restore_container_without_cleanup_or_provenance_is_rejected():
    module = _load_module()
    unsafe = """
run: |
  CONTAINER=mei-restore-backend-20260919
  cleanup(){ docker rm -f "$CONTAINER"; }
  trap cleanup EXIT
  docker run -d --name "$CONTAINER" postgres:16-alpine
  docker exec "$CONTAINER" pg_restore -d restoredb /backup.dump
"""
    findings = module.audit_text(Path(".github/workflows/restore.yml"), unsafe)
    joined = "\n".join(findings)
    assert "missing --rm" in joined
    assert "missing execution_id label" in joined
    assert "missing origin label" in joined


def test_ephemeral_attributed_restore_container_is_allowed():
    module = _load_module()
    safe = """
run: |
  CONTAINER=mei-restore-${GITHUB_RUN_ID}-${GITHUB_RUN_ATTEMPT}
  docker run --rm -d --name "$CONTAINER" \
    --label "execution_id=${GITHUB_RUN_ID}.${GITHUB_RUN_ATTEMPT}" \
    --label "origin=github-actions:${GITHUB_REPOSITORY}:${GITHUB_WORKFLOW}" \
    postgres:16-alpine
  docker exec "$CONTAINER" pg_restore -d restoredb /backup.dump
"""
    assert module.audit_text(Path(".github/workflows/restore.yml"), safe) == []


def test_repository_has_no_unsafe_restore_container_contracts():
    module = _load_module()
    assert module.audit_repository(ROOT) == []
