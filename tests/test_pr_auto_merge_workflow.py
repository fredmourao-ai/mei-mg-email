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


def test_auto_merge_reacts_to_every_pull_request_gate():
    workflow = WORKFLOW.read_text(encoding="utf-8")

    assert "- Email Safety CI" in workflow
    assert "- Repository Policy Guard" in workflow
    assert "- Repository Governance Gate" in workflow
    assert "- AI Conflict Resolver" in workflow


def test_auto_merge_can_read_legacy_commit_statuses():
    workflow = WORKFLOW.read_text(encoding="utf-8")

    assert "statuses: read" in workflow


def test_auto_merge_requires_always_on_pr_workflows_before_merge():
    workflow = WORKFLOW.read_text(encoding="utf-8")

    assert 'repos/$REPO/actions/runs?head_sha=$HEAD_SHA&event=pull_request&per_page=100' in workflow
    for name in ["Repository Policy Guard", "Repository Governance Gate", "AI Conflict Resolver"]:
        assert f"'{name}'" in workflow
    assert "all($required[];" in workflow
    assert "Canonical pull-request workflows are not all complete and green yet." in workflow


def test_auto_merge_pins_main_pr_to_exact_validated_head_and_uses_rest_merge():
    workflow = WORKFLOW.read_text(encoding="utf-8")

    assert '.base.ref == "main"' in workflow
    assert '.head.sha == $sha' in workflow
    assert 'repos/$REPO/pulls/$pr_number' in workflow
    assert 'repos/$REPO/pulls/$PR_NUMBER/merge' in workflow
    assert '-f sha="$HEAD_SHA"' in workflow
    assert "gh pr merge" not in workflow
