from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
AUTO = (ROOT / ".github" / "workflows" / "pr-auto-merge.yml").read_text(encoding="utf-8")
GOVERNANCE = (ROOT / ".github" / "workflows" / "repository-governance.yml").read_text(encoding="utf-8")


def test_duplicate_merge_triggers_are_coalesced_safely():
    assert "cancel-in-progress: true" in AUTO
    assert "merged_main_sha" in AUTO


def test_auto_merge_revalidates_the_exact_merged_main_sha():
    assert "actions: write" in AUTO
    assert 'git/ref/heads/main' in AUTO
    assert 'actions/runs?head_sha=$sha&event=workflow_dispatch&per_page=100' in AUTO
    assert 'actions/workflows/$workflow/dispatches' in AUTO
    for workflow in [
        "email-safety-ci.yml",
        "repo-policy-guard.yml",
        "repository-governance.yml",
        "ai-conflict-resolver.yml",
    ]:
        assert workflow in AUTO


def test_governance_gate_supports_post_merge_dispatch():
    assert "workflow_dispatch:" in GOVERNANCE
