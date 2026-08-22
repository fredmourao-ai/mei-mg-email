from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def test_repo_policy_guard_passes():
    r = subprocess.run(['python3', str(ROOT/'scripts/repo_policy_guard.py')], cwd=ROOT, capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr


def test_worker_has_startup_policy_guard():
    unit = (ROOT/'deploy/systemd/mei-mg-email-worker.service').read_text()
    assert 'scripts/runtime_policy_guard.py' in unit
    assert 'worker.safe_entrypoint_v2' in unit
