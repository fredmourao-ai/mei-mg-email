from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_autorepair_service_runs_throughput_supervisor_every_15m():
    service = (ROOT / "deploy/systemd/mei-mg-email-autorepair.service").read_text()
    timer = (ROOT / "deploy/systemd/mei-mg-email-autorepair.timer").read_text()
    assert "scripts/nonstop_supervisor_15m.py" in service
    assert "TimeoutStartSec=90" in service
    assert "OnUnitActiveSec=15min" in timer
    assert "Persistent=true" in timer


def test_supervisor_measures_real_throughput_and_keeps_safety_guards():
    src = (ROOT / "scripts/nonstop_supervisor_15m.py").read_text()
    assert "sender_blocked.pause" in src
    assert "worker_stopped_for_current_sender_block" in src
    assert "sent_24h" in src
    assert "sent_10m" in src
    assert "open_queue" in src
    assert "situacao_cadastral='ATIVA'" in src
    assert "is_valid_email_address" in src
    assert "position('contabil'" in src
    assert "vw_empresas_elegiveis" not in src
    assert "pg_locks" in src
    assert "pg_stat_activity" in src
    assert "repor_fila_automatica_isolada" in src
    assert "bounded_autoqueue_refill_added" in src
    assert "healthy_real_throughput" in src
    assert "degraded_eligibility_query_error" in src
    assert "unlink(" not in src
    assert "remove(" not in src
    assert "provider.send" not in src
    assert ("marketing_" + "autorizado = true") not in src.lower()
    assert "mei_verificado = true" not in src.lower()


def test_supervisor_uses_same_rolling_quota_ledger_as_worker():
    src = (ROOT / "scripts/nonstop_supervisor_15m.py").read_text()
    assert "envios_externos_cota" in src
    assert "quota_24h" in src
    assert "statement_timestamp() - interval '24 hours'" in src
    decision_tail = src.split("below_target =", 1)[1]
    assert 'before["quota_24h"]' in decision_tail
    assert 'after["quota_24h"]' in decision_tail
