from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_worker_has_persistent_sender_block_circuit():
    worker = (ROOT / "worker" / "worker.py").read_text(encoding="utf-8").casefold()
    assert "sender_block_sentinel" in worker
    assert "sender_blocked.pause" in worker
    assert "_registrar_sender_blocked_pause" in worker
    assert "_sender_blocked_pause_ativo" in worker
    assert "nenhum novo envio sera tentado" in worker


def test_current_incident_pause_marker_is_versioned():
    marker = (ROOT / "runtime" / "sender_blocked.pause").read_text(encoding="utf-8").casefold()
    assert "naoresponda@dev.shopvivaliz.com.br" in marker
    assert "5.1.8" in marker
    assert "42004" in marker
