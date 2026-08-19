from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_autorepair_service_uses_guarded_wrapper():
    service = (ROOT / "deploy/systemd/mei-mg-email-autorepair.service").read_text(encoding="utf-8")
    assert "scripts/autocorrigir_envios_guarded.py" in service


def test_guard_restores_worker_without_bypassing_sender_block():
    source = (ROOT / "scripts/autocorrigir_envios_guarded.py").read_text(encoding="utf-8")
    assert "core._sentinel_active()" in source
    assert "core._worker_state() != \"active\"" in source
    assert "core._start_worker()" in source
    assert "return hourly.main()" in source
