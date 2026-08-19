from pathlib import Path

from app.config import settings
from app.queue_manager import quantidade_para_repor

ROOT = Path(__file__).resolve().parents[1]


def test_continuous_queue_defaults_keep_nonzero_buffer():
    assert settings.queue_min_pending == 1000
    assert settings.queue_target_pending == 5000
    assert settings.queue_min_pending >= 1
    assert settings.queue_target_pending > settings.queue_min_pending


def test_replenisher_refills_before_queue_reaches_zero():
    assert quantidade_para_repor(0) == 5000
    assert quantidade_para_repor(500) == 4500
    assert quantidade_para_repor(1000) == 4000
    assert quantidade_para_repor(1001) == 0
    assert quantidade_para_repor(5000) == 0


def test_queue_first_consumes_and_recovers_before_refill():
    worker = (ROOT / "worker" / "worker_queue_first.py").read_text(
        encoding="utf-8"
    )
    consume = worker.index("_processar_se_disponivel(conn, provider)")
    recovery = worker.index(
        "recuperar_fila_legada_e_lotes_orfaos(conn)",
        consume,
    )
    refill = worker.index("repor_fila_automatica_isolada()", recovery)
    assert consume < recovery < refill


def test_queue_is_separate_from_24h_send_quota_in_audit():
    audit = (ROOT / "scripts" / "auditar_exchange_10000.py").read_text(
        encoding="utf-8"
    )
    assert "fila_compromete_acima_meta" not in audit
    assert "queue_target_pending" in audit
    assert "submitted_ou_enviados_ultimas_24h" in audit


def test_legacy_daily_script_uses_continuous_replenisher():
    script = (ROOT / "scripts" / "disparar_10000_mei_mg.py").read_text(
        encoding="utf-8"
    )
    assert "repor_fila_automatica" in script
    assert "EXPECTED_DAILY_TARGET = 9950" in script


def test_queue_status_queries_do_not_cast_enum_to_text():
    manager = (ROOT / "app" / "queue_manager.py").read_text(encoding="utf-8")
    daily = (ROOT / "scripts" / "disparar_10000_mei_mg.py").read_text(
        encoding="utf-8"
    )
    assert "status::text in ('pendente', 'enviando')" not in manager
    assert (
        "status in ('pendente', 'enviando', 'pending', 'processing')"
        in manager
    )
    assert "status::text in ('submitted', 'enviado')" not in daily
    assert "status in ('submitted', 'enviado')" in daily


def test_autoqueue_bounds_deduplication_pool_before_window_function():
    manager = (ROOT / "app" / "queue_manager.py").read_text(encoding="utf-8")
    assert "base as materialized" in manager
    assert "preselecionadas as" in manager
    assert "limit %s" in manager
    assert "from preselecionadas" in manager
    assert "AUTOQUEUE_CANDIDATE_OVERSAMPLE = 4" in manager


def test_autoqueue_excludes_send_history_before_candidate_limit():
    manager = (ROOT / "app" / "queue_manager.py").read_text(encoding="utf-8")
    base_start = manager.index("with base as materialized")
    first_limit = manager.index("limit %s", base_start)
    first_history_guard = manager.index("and not exists (", base_start)
    submitted_status = manager.index("'submitted', 'enviado', 'delivered', 'bounced'", base_start)
    assert first_history_guard < first_limit
    assert submitted_status < first_limit


def test_queue_depth_uses_actual_open_messages_and_nonblocking_lock():
    manager = (ROOT / "app" / "queue_manager.py").read_text(encoding="utf-8")
    assert "select count(*)" in manager
    assert "coalesce(sum(tamanho), 0)" not in manager
    assert "pg_try_advisory_xact_lock" in manager
    assert "pg_advisory_xact_lock" not in manager


def test_queue_status_index_migration_exists():
    migration = (
        ROOT / "db" / "migrations" / "V026__queue_status_index.sql"
    ).read_text(encoding="utf-8")
    assert "idx_envios_status" in migration
    assert "on mei_email.envios (status)" in migration
