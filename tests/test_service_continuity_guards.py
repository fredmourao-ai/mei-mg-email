from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_critical_services_restart_but_remain_maintainable():
    for name in ('mei-mg-email-worker.service', 'mei-mg-email-queue-replenisher.service'):
        text = (ROOT / 'deploy' / 'systemd' / name).read_text(encoding='utf-8')
        assert 'RefuseManualStop=yes' not in text, name
        assert 'Restart=always' in text, name
        assert 'runtime_policy_guard.py' in text, name


def test_brevo_reconciler_is_resident_and_replaces_exchange_ndr_guard():
    unit = ROOT / 'deploy' / 'systemd' / 'mei-mg-email-brevo-reconciler.service'
    assert unit.exists()
    text = unit.read_text(encoding='utf-8')
    assert 'ExecStart=__PYTHON__ scripts/brevo_event_reconciler.py' in text
    assert 'Restart=always' in text
    assert 'runtime_policy_guard.py' in text
    assert '/var/lib/mei-mg-email/brevo_event_state.json' in text

    installer = (ROOT / 'scripts' / 'instalar_monitoramento_vm.sh').read_text(encoding='utf-8')
    assert 'enable --now mei-mg-email-brevo-reconciler.service' in installer
    assert 'disable --now mei-mg-email-ndr-guard.service' in installer


def test_base_sync_uses_rendered_venv_for_policy_guard():
    unit = ROOT / 'deploy' / 'systemd' / 'mei-mg-email-base-sync.service'
    text = unit.read_text(encoding='utf-8')
    assert 'ExecStartPre=__PYTHON__ __APP_DIR__/scripts/runtime_policy_guard.py' in text
    assert '/usr/bin/python3' not in text
    assert '/home/ubuntu/mei-mg-email' not in text
