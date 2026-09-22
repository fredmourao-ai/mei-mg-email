from pathlib import Path
import importlib.util

ROOT = Path(__file__).resolve().parents[1]


def load_guard():
    path = ROOT / "scripts" / "repo_policy_guard.py"
    spec = importlib.util.spec_from_file_location("repo_policy_guard_under_test", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_git_commands_mark_only_canonical_checkout_safe(monkeypatch):
    guard = load_guard()
    calls = []

    def fake_check_output(command, text):
        calls.append(command)
        if "status" in command:
            return ""
        return "scripts/repo_policy_guard.py\n"

    monkeypatch.setattr(guard.subprocess, "check_output", fake_check_output)

    guard.repo_files()
    guard.changed_paths()

    assert len(calls) == 2
    for command in calls:
        assert command[:2] == ["git", "-c"]
        assert command[2] == f"safe.directory={guard.ROOT}"
        assert command[3:5] == ["-C", str(guard.ROOT)]
        assert "--global" not in command
