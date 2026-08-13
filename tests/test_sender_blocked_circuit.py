from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_worker_has_persistent_sender_block_circuit():
    worker = (ROOT / "worker" / "worker.py").read_text(encoding="utf-8").casefold()
    assert "sender_block_sentinel" in worker
    assert "sender_blocked.pause" in worker
    assert "_registrar_sender_blocked_pause" in worker
    assert "_sender_blocked_pause_ativo" in worker
    assert "nenhum novo envio sera tentado" in worker


def test_current_incident_pause_is_runtime_state_not_git_state():
    assert not (ROOT / "runtime" / "sender_blocked.pause").exists()

    incident = (ROOT / "ops" / "incidents" / "2026-08-13-AS42004.md").read_text(
        encoding="utf-8"
    ).casefold()
    assert "naoresponda@dev.shopvivaliz.com.br" in incident
    assert "5.1.8" in incident
    assert "42004" in incident

    deploy = (ROOT / "scripts" / "deploy_hardening_20260813.sh").read_text(
        encoding="utf-8"
    ).casefold()
    assert "/var/lib/mei-mg-email/sender_blocked.pause" in deploy
    assert "deploy_worker_stopped=true" in deploy
    assert "worker_resume_allowed=false" in deploy
