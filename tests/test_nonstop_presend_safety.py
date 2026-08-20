from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_worker_unit_uses_bounded_preflight_and_safe_entrypoint():
    unit = (ROOT / "deploy/systemd/mei-mg-email-worker.service").read_text()
    assert "StartLimitIntervalSec=0" in unit
    assert "Restart=always" in unit
    assert "RestartSec=5" in unit
    assert "TimeoutStartSec=30" in unit
    assert "scripts/runtime_sender_preflight.py" in unit
    assert "-m worker.safe_entrypoint" in unit
    assert "scripts/runtime_sender_guard.py" not in unit


def test_preflight_never_bulk_rewrites_queue():
    src = (ROOT / "scripts/runtime_sender_preflight.py").read_text()
    assert "update mei_email.campanhas" in src
    assert "update mei_email.envios" not in src.lower()
    assert "delete from mei_email.envios" not in src.lower()
    assert "marketing_autorizado_origem" in src
    assert "mei_verificado_origem" in src


def test_safe_entrypoint_checks_independent_sources_and_replay_before_graph():
    src = (ROOT / "worker/safe_entrypoint.py").read_text()
    assert "LEGACY_MARKETING_ORIGINS" in src
    assert "LEGACY_MEI_ORIGINS" in src
    assert "email_suppressions" in src
    assert "terminal_history" in src
    assert "envios_externos_cota" in src
    assert "_marcar_envio_em_transito = _safe_mark" in src
    assert "status='submitted'" in src
    assert "resultado Graph incerto" in src
    # Never reinterpret an uncertain dispatch as pending/retryable.
    recovery = src.split("def _safe_recovery", 1)[1].split("def _prune_lot", 1)[0]
    assert "status='pendente'" not in recovery
