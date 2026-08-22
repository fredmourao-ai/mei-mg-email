from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_critical_services_restart_but_remain_maintainable():
    for name in ('mei-mg-email-worker.service', 'mei-mg-email-queue-replenisher.service'):
        text = (ROOT / 'deploy' / 'systemd' / name).read_text(encoding='utf-8')
        assert 'RefuseManualStop=yes' not in text, name
        assert 'Restart=always' in text, name
        assert 'runtime_policy_guard.py' in text, name
