from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "pr-auto-merge.yml"


def test_auto_merge_gate_uses_rest_checks_instead_of_gh_pr_checks():
    workflow = WORKFLOW.read_text(encoding="utf-8")

    assert 'repos/$REPO/commits/$HEAD_SHA/check-runs?filter=latest&per_page=100' in workflow
    assert 'repos/$REPO/commits/$HEAD_SHA/status' in workflow
    assert '.status == "completed"' in workflow
    assert '.conclusion == "success"' in workflow
    assert '.conclusion == "skipped"' in workflow
    assert '.conclusion == "neutral"' in workflow
    assert "gh pr checks" not in workflow
