from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_main_guard_has_fail_closed_external_evidence_fallback():
    workflow = (ROOT / ".github/workflows/absolute-audit-main-guard.yml").read_text()

    assert "id: github_artifact" in workflow
    assert "continue-on-error: true" in workflow
    assert "steps.github_artifact.outcome == 'failure'" in workflow
    assert "scripts/publish-main-guard-evidence-oci.sh" in workflow
    assert "Require published main-guard evidence" in workflow


def test_oci_evidence_publisher_is_fail_closed():
    script = (ROOT / "scripts/publish-main-guard-evidence-oci.sh").read_text()

    assert "set -Eeuo pipefail" in script
    assert "--auth instance_principal" in script
    assert "os object put" in script
    assert "os object head" in script
    assert "sha256sum" in script
    assert "cmp -s" in script
    assert "verification.json" in script
