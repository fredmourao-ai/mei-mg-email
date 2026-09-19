from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_v032_normalizes_legacy_queue_and_reopens_orphan_lots():
    migration = (
        ROOT / "db" / "migrations_archived_post_v020_20260821" / "V032__recover_legacy_queue_and_orphan_lots.sql"
    ).read_text(encoding="utf-8")
    normalized = " ".join(migration.casefold().split())
    assert "status in ('pending', 'processing')" in normalized
    assert "set status = 'pendente'" in normalized
    assert "l.status <> 'pendente'" in normalized
    assert "idx_envios_open_queue_lote" in normalized
    assert "analyze envios" in normalized


def test_queue_recovery_module_is_idempotent_and_refill_is_isolated():
    source = (ROOT / "app" / "queue_recovery.py").read_text(encoding="utf-8")
    assert "recuperar_fila_legada_e_lotes_orfaos" in source
    assert "repor_fila_automatica_isolada" in source
    assert "QUEUE_BULK_PRUNE" in source
    assert "fila redundante ja suprimida/submetida" in source
    assert "duplicata aberta de destinatario descartada" in source
    assert "status in ('submitted', 'enviado', 'delivered', 'bounced')" in source
    assert "statement_timeout" in source
    assert "lock_timeout" in source
    assert "psycopg.connect(settings.database_url)" in source


def test_queue_recovery_is_bounded_and_skips_locked_rows():
    source = (ROOT / "app" / "queue_recovery.py").read_text(encoding="utf-8")
    normalized = " ".join(source.casefold().split())
    assert "queue_recovery_batch_size = 500" in normalized
    assert "queue_recovery_max_batches = 4" in normalized
    assert "queue_recovery_statement_timeout_seconds = 30" in normalized
    assert "queue_recovery_lock_timeout_seconds = 3" in normalized
    assert "queue_recovery_deferred" in normalized
    assert normalized.count("for update of e skip locked") >= 5
    assert normalized.count("for update of l skip locked") >= 2
    assert "conn.commit()" in source
    assert "conn.rollback()" in source


def test_ineligible_prune_casts_case_to_status_enum():
    source = (ROOT / "app" / "queue_recovery.py").read_text(encoding="utf-8")
    normalized = " ".join(source.split())
    assert "case when t.opt_out then 'opt_out' else 'bloqueado' end )::mei_email.status_envio" in normalized


def test_queue_first_consumes_and_recovers_without_inline_refill():
    source = (ROOT / "worker" / "worker_queue_first.py").read_text(encoding="utf-8")
    loop = source[source.index("while True:"):]
    consume = loop.index("_processar_se_disponivel(conn, provider)")
    recover = loop.index("recuperar_fila_legada_e_lotes_orfaos(conn)", consume)
    assert consume < recover
    assert "repor_fila_automatica_isolada()" not in loop
    assert "Queue replenishment runs in a separate lightweight service" in loop


def test_sender_block_uses_canonical_fail_closed_path():
    source = (ROOT / "worker" / "worker_queue_first.py").read_text(encoding="utf-8")
    assert "/var/lib/mei-mg-email/sender_blocked.pause" in source
    assert "LEGACY_SENDER_BLOCK_SENTINEL" in source
    assert "base_worker.SENDER_BLOCK_SENTINEL = SENDER_BLOCK_SENTINEL" in source


def test_hourly_autorepair_never_removes_sender_block_sentinel():
    source = (ROOT / "scripts" / "autocorrigir_envios_2h.py").read_text(
        encoding="utf-8"
    )
    assert "blocked_fail_closed" in source
    assert "automatic resume is forbidden" in source
    assert "unlink(" not in source
    assert "remove(" not in source

    timer = (
        ROOT / "deploy" / "systemd" / "mei-mg-email-autorepair.timer"
    ).read_text(encoding="utf-8")
    assert "OnUnitActiveSec=15min" in timer
    assert "OnUnitActiveSec=1h" not in timer
    assert "OnUnitActiveSec=2h" not in timer
    assert "Persistent=true" in timer


def test_historical_sender_block_is_telemetry_not_current_circuit_breaker():
    source = (ROOT / "scripts" / "autocorrigir_envios_2h.py").read_text(
        encoding="utf-8"
    )
    assert '"historical_sender_blocked_24h"' in source
    assert "if sentinel_active:" in source
    assert 'or before["sender_blocked_24h"] > 0' not in source


def test_hourly_autorepair_holds_global_lock_for_entire_execution():
    source = (ROOT / "scripts" / "autocorrigir_envios_2h.py").read_text(
        encoding="utf-8"
    )
    assert "def _repair_lock():" in source
    assert "pg_try_advisory_lock" in source
    assert "pg_advisory_unlock" in source
    assert "with _repair_lock():" in source
    assert "another hourly repair is already active" in source


def test_hourly_autorepair_uses_total_quota_but_worker_progress_for_stall():
    source = (ROOT / "scripts" / "autocorrigir_envios_2h.py").read_text(
        encoding="utf-8"
    )
    assert "envios_externos_cota" in source
    assert 'row["queue_sent_24h"]' in source
    assert 'row["external_sent_24h"]' in source
    assert 'row["sent_24h"] = queue_sent_24h + external_sent_24h' in source
    assert "make_interval(mins => %s)" in source
    assert 'before["sent_stall_window"] == 0' in source
    assert 'after["sent_stall_window"] == 0' in source


def test_startup_recovers_stale_sending_before_reopening_stuck_lots():
    source = (ROOT / "worker" / "worker_queue_first.py").read_text(encoding="utf-8")
    startup = source[source.index("with psycopg.connect"):source.index("while True:")]
    recover_queue = startup.index("recuperar_fila_legada_e_lotes_orfaos(conn)")
    recover_lots = startup.index("recuperar_lotes_travados(conn)")
    assert recover_queue < recover_lots


def test_stale_sending_recovery_handles_reopened_lot():
    source = (ROOT / "app" / "queue_recovery.py").read_text(encoding="utf-8")
    block = source[source.index("recovered_stale_sending ="):source.index("reopened_lots =")]
    assert "l.status =" not in block
    assert "l.iniciado_em is null" in block


def test_uncertain_dispatch_checkpoint_is_quarantined_instead_of_requeued():
    source = (ROOT / "app" / "queue_recovery.py").read_text(encoding="utf-8")
    normalized = " ".join(source.casefold().split())
    assert "quarantine_uncertain_dispatch" in normalized
    assert "coalesce(e.erro, '') like 'dispatch_started:%%'" in normalized
    assert "set status = 'bloqueado'::mei_email.status_envio" in normalized
    stale_block = source[source.index("recovered_stale_sending ="):source.index("reopened_lots =")]
    assert "not like 'dispatch_started:%%'" in stale_block.casefold()


def test_uncertain_dispatch_reserves_one_slot_in_external_brevo_quota_ledger():
    source = (ROOT / "app" / "queue_recovery.py").read_text(encoding="utf-8")
    normalized = " ".join(source.casefold().split())
    assert "insert into mei_email.envios_externos_cota" in normalized
    assert "brevo_uncertain_dispatch_recovery" in normalized
    assert "delivery_uncertain" in normalized


def test_queue_recovery_reports_uncertain_dispatch_quarantine_separately():
    source = (ROOT / "app" / "queue_recovery.py").read_text(encoding="utf-8")
    assert "quarantined_uncertain_dispatches" in source



def test_uncertain_dispatch_quota_uses_best_durable_dispatch_time_before_now_fallback():
    source = (ROOT / "app" / "queue_recovery.py").read_text(encoding="utf-8")
    normalized = " ".join(source.casefold().split())
    assert "max(coalesce(h.submitted_at, h.enviado_em))" in normalized
    assert "greatest(" in normalized
    assert "l.iniciado_em" in normalized
    assert "t.quota_sent_at" in normalized

def test_hourly_autorepair_detects_and_repairs_open_ineligible_rows():
    source = (ROOT / "scripts" / "autocorrigir_envios_2h.py").read_text(
        encoding="utf-8"
    )
    assert 'row["ineligible_open"]' in source
    assert 'before["ineligible_open"] > 0' in source
    assert 'after["ineligible_open"]' in source
    assert "position('contabil'" in source
    assert "situacao_cadastral <> 'ATIVA'" in source


def test_queue_recovery_prunes_full_canonical_policy_drift():
    source = (ROOT / "app" / "queue_recovery.py").read_text(encoding="utf-8")
    normalized = " ".join(source.casefold().split())
    assert "coalesce(emp.opt_out, false)" in normalized
    assert "is_email_suppressed(e.email)" in normalized
    assert "is_cnpj_suppressed(e.cnpj::text)" in normalized
    assert "limit 3" in normalized
    assert "h.cnpj = e.cnpj" in normalized
    assert "email_rn > 1 or r.cnpj_rn > 1" in normalized


def test_hourly_autorepair_detects_shared_suppressed_and_replay_drift():
    source = (ROOT / "scripts" / "autocorrigir_envios_2h.py").read_text(
        encoding="utf-8"
    )
    normalized = " ".join(source.casefold().split())
    assert "coalesce(e.opt_out, false)" in normalized
    assert "is_email_suppressed(v.email)" in normalized
    assert "is_cnpj_suppressed(v.cnpj::text)" in normalized
    assert "limit 3" in normalized
    assert "h.cnpj = v.cnpj" in normalized
    assert "h.status in ('submitted','enviado','delivered','bounced')" in normalized
