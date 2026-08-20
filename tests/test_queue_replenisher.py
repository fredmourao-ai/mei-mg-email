from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_template_existe_e_contem_descadastro():
    template = (ROOT / "templates" / "mei-contabilidade-melo.html").read_text(
        encoding="utf-8"
    )
    assert "{{unsubscribe_url}}" in template
    assert "{{nome_fantasia}}" in template
    assert "logo-contabilidade-melo-transparente.png" in template


def test_replenisher_cria_campanha_e_envios_em_lotes():
    manager = (ROOT / "app" / "queue_manager.py").read_text(encoding="utf-8")
    assert "insert into mei_email.campanhas" in manager
    assert "insert into mei_email.lotes" in manager
    assert "insert into mei_email.envios" in manager
    assert "AUTOQUEUE_LOT_SIZE = 100" in manager
    assert "AUTOQUEUE_REFILL_BATCH_SIZE = 5000" in manager
    assert "AUTOQUEUE_CANDIDATE_OVERSAMPLE = 4" in manager
    assert "AUTOQUEUE_CANDIDATE_MIN_EXTRA = 2000" in manager


def test_replenisher_respeita_elegibilidade_supressoes_e_nao_reenvia():
    manager = (ROOT / "app" / "queue_manager.py").read_text(encoding="utf-8")
    assert "tipo_regime = 'MEI'" in manager
    assert "uf = 'MG'" in manager
    assert "situacao_cadastral = 'ATIVA'" in manager
    assert "opt_out = false" in manager
    assert "provavel_terceiro = false" in manager
    assert "enviado = false" in manager
    assert "is_independent_marketing_authorization" in manager
    assert "is_independent_mei_verification" in manager
    assert "is_valid_email_address" in manager
    assert "is_email_suppressed" in manager
    assert "is_cnpj_suppressed" in manager
    assert "submitted" in manager
    assert "enviado" in manager
    assert "delivered" in manager
    assert "bounced" in manager


def test_replenisher_exclui_historico_antes_do_primeiro_limit():
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


def test_autoqueue_advisory_lock_uses_dedicated_tuple_cursor():
    manager = (ROOT / "app" / "queue_manager.py").read_text(encoding="utf-8")
    function = manager[manager.index("def repor_fila_automatica"):manager.index("select count(*) as pendentes")]
    assert "with conn.cursor(row_factory=tuple_row) as lock_cur:" in function
    assert "pg_try_advisory_xact_lock(%s)" in function
    assert "lock_row = lock_cur.fetchone()" in function
    assert "lock_row[0]" in function
    assert "row_factory=dict_row" in manager


def test_queue_status_index_migration_exists():
    migration = (
        ROOT / "db" / "migrations" / "V026__queue_status_index.sql"
    ).read_text(encoding="utf-8")
    assert "idx_envios_status" in migration
    assert "on mei_email.envios (status)" in migration
