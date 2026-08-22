from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_runtime_policy_guard_checks_repo_and_database_contract():
    path = ROOT / 'scripts' / 'runtime_policy_guard.py'
    assert path.exists(), 'runtime policy guard must exist'
    src = path.read_text(encoding='utf-8')
    required = (
        'repo_policy_guard.py',
        'operational_filter_rejection_reason',
        'enforce_envio_live_eligibility',
        'filter_uf',
        'filter_not_mei',
        'delete from mei_email.envios',
        'zz_empresas_purge_rejected_after_update',
        'flyway_schema_history',
    )
    for token in required:
        assert token in src


def test_every_policy_writing_systemd_unit_runs_guard_before_start():
    names = (
        'mei-mg-email-worker.service',
        'mei-mg-email-queue-replenisher.service',
        'mei-mg-email-autorepair.service',
        'mei-mg-email-autorepair-15min.service',
        'mei-mg-email-base-sync.service',
    )
    for name in names:
        unit = ROOT / 'deploy' / 'systemd' / name
        assert 'runtime_policy_guard.py' in unit.read_text(encoding='utf-8'), name
