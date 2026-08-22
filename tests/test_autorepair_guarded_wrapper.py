from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def test_autorepair_service_uses_runtime_guard_and_nonstop_supervisor():
    service = (ROOT / "deploy/systemd/mei-mg-email-autorepair.service").read_text(encoding="utf-8")
    assert "scripts/runtime_policy_guard.py" in service
    assert "scripts/nonstop_supervisor_15m.py" in service
    assert "autocorrigir_envios_guarded.py" not in service

def test_supervisor_never_bypasses_sender_block():
    source = (ROOT / "scripts/nonstop_supervisor_15m.py").read_text(encoding="utf-8")
    assert "sender_blocked.pause" in source
    assert "worker_stopped_for_current_sender_block" in source
    assert "unlink(" not in source
    assert "provider.send" not in source
