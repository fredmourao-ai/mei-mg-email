from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_all_replenishment_paths_share_15k_buffer_200_batch_and_lock():
    config = (ROOT / "app" / "config.py").read_text(encoding="utf-8")
    manager = (ROOT / "app" / "queue_manager.py").read_text(encoding="utf-8")
    replenisher = (ROOT / "scripts" / "queue_replenisher.py").read_text(encoding="utf-8")

    assert 'QUEUE_MIN_PENDING", "14800"' in config
    assert 'QUEUE_TARGET_PENDING", "15000"' in config
    assert "AUTOQUEUE_REFILL_BATCH_SIZE = 200" in manager
    assert "settings.queue_min_pending" in replenisher
    assert "settings.queue_target_pending" in replenisher
    assert "BATCH = min(200" in replenisher
    assert "LOCK_ID = CAMPAIGN_ENQUEUE_ADVISORY_LOCK_ID" in replenisher


def test_legacy_15m_supervisor_never_becomes_a_second_queue_writer():
    source = (ROOT / "scripts" / "validar_e_reparar_envios_15min.py").read_text(encoding="utf-8")
    assert "repor_fila_automatica(" not in source
    assert "mei-mg-email-queue-replenisher.service" in source


def test_worker_base_has_no_retired_exchange_quota_contract():
    source = (ROOT / "worker" / "worker.py").read_text(encoding="utf-8")
    assert "nao pode ultrapassar 10000" not in source
    assert "Exchange Online" not in source
    assert "hard cap Brevo de 300" in source
    assert "naoresponda@dev.shopvivaliz.com.br" not in source
    assert "status Graph inesperado" not in source
    assert "desbloqueio no Exchange" not in source
