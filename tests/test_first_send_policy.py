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


def test_no_active_migration_above_v020():
    active = sorted((ROOT / 'db' / 'migrations').glob('V[0-9]*__*.sql'))
    versions = [int(p.name.split('__', 1)[0][1:]) for p in active]
    assert max(versions, default=0) <= 20


def test_queue_manager_applies_canonical_suppression_before_insert():
    src = (ROOT / 'app' / 'queue_manager.py').read_text(encoding='utf-8')
    body = src.split('def repor_fila_automatica', 1)[1]
    assert 'coalesce(e.opt_out, false) = false' in body
    assert 'not mei_email.is_email_suppressed(e.email)' in body
    assert 'not mei_email.is_cnpj_suppressed(e.cnpj::text)' in body


def test_presend_python_guard_checks_suppression_and_external_replay():
    src = (ROOT / 'worker' / 'safe_entrypoint.py').read_text(encoding='utf-8')
    assert 'is_email_suppressed' in src
    assert 'is_cnpj_suppressed' in src
    assert 'envios_externos_cota' in src


def test_repo_guard_hard_blocks_future_active_migrations():
    src = (ROOT / 'scripts' / 'repo_policy_guard.py').read_text(encoding='utf-8')
    assert 'MAX_ACTIVE_MIGRATION = 20' in src
    assert 'active migration above canonical ceiling' in src
