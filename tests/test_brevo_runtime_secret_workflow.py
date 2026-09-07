from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "brevo-runtime-secret.yml"
SCRIPT = ROOT / "scripts" / "materialize_brevo_runtime_secret.py"


def test_brevo_secret_workflow_is_manual_local_and_bounded():
    assert WORKFLOW.exists()
    source = WORKFLOW.read_text(encoding="utf-8")
    assert "workflow_dispatch:" in source
    assert "self-hosted" in source
    assert "Linux" in source
    assert "ARM64" in source
    assert "mei-backend" in source
    assert "mei-ci" not in source
    assert "secrets.BREVO_API_KEY" in source
    assert "timeout-minutes: 5" in source
    assert "MATERIALIZE_BREVO_RUNTIME" in source
    assert "echo $BREVO_API_KEY" not in source
    assert 'echo "$BREVO_API_KEY"' not in source
    assert "set -x" not in source


def test_cutover_uses_full_history_and_safe_local_fast_forward():
    source = WORKFLOW.read_text(encoding="utf-8")
    assert "fetch-depth: 0" in source
    assert "/home/ubuntu/mei-mg-email" in source
    assert "git diff --quiet" in source
    assert "git diff --cached --quiet" in source
    assert "git fetch \"$GITHUB_WORKSPACE\" main" in source
    assert "git merge --ff-only FETCH_HEAD" in source
    assert "git reset --hard" not in source


def test_materializer_is_fail_closed_and_preserves_backup():
    assert SCRIPT.exists()
    source = SCRIPT.read_text(encoding="utf-8")
    assert "always-free-arm-1787907847-26" in source
    assert "/home/ubuntu/mei-mg-email/.env" in source
    assert "/home/ubuntu/.shopvivaliz/backups/mei-mg-email" in source
    assert "BREVO_API_KEY" in source
    assert "EMAIL_PROVIDER" in source
    assert "MAX_ENVIOS_POR_DIA" in source
    assert "META_ENVIOS_POR_DIA" in source
    assert "backend_brevo_key_present" in source
    assert "secret" not in source.split("print(", 1)[-1].casefold()
