from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
AUTO = (ROOT / ".github" / "workflows" / "pr-auto-merge.yml").read_text(encoding="utf-8")
GOVERNANCE = (ROOT / ".github" / "workflows" / "repository-governance.yml").read_text(encoding="utf-8")
SAFETY = (ROOT / ".github" / "workflows" / "email-safety-ci.yml").read_text(encoding="utf-8")
AI_RESOLVER = (ROOT / ".github" / "workflows" / "ai-conflict-resolver.yml").read_text(encoding="utf-8")
POLICY = (ROOT / ".github" / "workflows" / "repo-policy-guard.yml").read_text(encoding="utf-8")
WORKFLOWS = ROOT / ".github" / "workflows"
GOVERNANCE_VALIDATOR = (ROOT / "scripts" / "repository-governance-validate.sh").read_text(encoding="utf-8")


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


def test_required_email_safety_gate_is_not_path_filtered():
    assert "\n    paths:" not in SAFETY

def test_ai_resolver_survives_source_branch_deletion_race():
    assert 'ref: ${{ github.event.pull_request.head.sha }}' in AI_RESOLVER
    assert 'git ls-remote --exit-code --heads origin "$HEAD_REF"' in AI_RESOLVER
    assert "if: steps.head.outputs.active == 'true'" in AI_RESOLVER
    assert "refusing to recreate a merged/deleted branch" in AI_RESOLVER


def test_required_policy_gate_rejects_native_auto_merge_bypass():
    assert "allow_auto_merge" in POLICY
    assert "gh api" in POLICY
    assert "GITHUB_REPOSITORY" in POLICY
    assert '= "false"' in POLICY or "= 'false'" in POLICY


def test_workflows_do_not_use_node20_action_generations():
    for path in WORKFLOWS.glob("*.yml"):
        body = path.read_text(encoding="utf-8")
        assert "actions/checkout@v4" not in body, path.name
        assert "actions/setup-python@v5" not in body, path.name


def test_governance_validator_uses_available_project_python_in_worktrees():
    assert "git rev-parse --git-common-dir" in GOVERNANCE_VALIDATOR
    assert ".venv/bin/python" in GOVERNANCE_VALIDATOR
    assert '"$PYTHON_BIN" -m pytest -q' in GOVERNANCE_VALIDATOR
    assert "python3 -m pytest -q" not in GOVERNANCE_VALIDATOR
