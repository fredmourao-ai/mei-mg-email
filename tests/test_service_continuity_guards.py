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


def test_installer_manages_queue_replenisher_as_required_service():
    installer = (ROOT / 'scripts' / 'instalar_monitoramento_vm.sh').read_text(encoding='utf-8')
    assert 'render_unit "$APP_DIR/deploy/systemd/mei-mg-email-queue-replenisher.service"' in installer
    assert 'enable --now mei-mg-email-queue-replenisher.service' in installer
    assert 'is-active mei-mg-email-queue-replenisher.service' in installer
    assert 'is-enabled mei-mg-email-queue-replenisher.service' in installer
    assert 'systemctl restart mei-mg-email-worker.service' in installer
    assert 'systemctl restart mei-mg-email-queue-replenisher.service' in installer


def test_api_restart_restores_public_reverse_tunnel():
    api = (ROOT / 'deploy' / 'systemd' / 'mei-mg-email-api.service').read_text(encoding='utf-8')
    tunnel = (ROOT / 'deploy' / 'systemd' / 'mei-mg-email-site-tunnel.service').read_text(encoding='utf-8')
    installer = (ROOT / 'scripts' / 'instalar_monitoramento_vm.sh').read_text(encoding='utf-8')
    assert 'Wants=mei-mg-email-site-tunnel.service' in api
    assert 'Requires=mei-mg-email-api.service' in tunnel
    assert 'PartOf=mei-mg-email-api.service' in tunnel
    assert 'After=network-online.target mei-mg-email-api.service' in tunnel
    assert 'Restart=always' in tunnel
    assert '-R 127.0.0.1:18010:127.0.0.1:8010' in tunnel
    assert 'render_unit \"$APP_DIR/deploy/systemd/mei-mg-email-site-tunnel.service\"' in installer
    assert 'enable --now mei-mg-email-site-tunnel.service' in installer
    assert 'restart mei-mg-email-site-tunnel.service' in installer
    assert 'is-active mei-mg-email-site-tunnel.service' in installer
