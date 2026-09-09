from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_template_existe_e_contem_descadastro():
    template = (ROOT / "templates/mei-contabilidade-melo.html").read_text(encoding="utf-8")
    assert "{{unsubscribe_url}}" in template
    assert "{{nome_fantasia}}" in template
    assert "logo-contabilidade-melo-transparente.png" in template


def test_continuous_replenisher_uses_canonical_first_send_contract():
    src = (ROOT / "scripts/queue_replenisher.py").read_text(encoding="utf-8")
    for token in (
        "situacao_cadastral",
        "opt_out",
        "is_valid_email_address",
        "contabil",
        "is_email_suppressed",
        "is_cnpj_suppressed",
        "ACTIVE_STATUSES",
        "limit 3",
    ):
        assert token in src
    legacy_authorization = "marketing_" + "autorizado"
    for retired in (
        legacy_authorization,
        "mei_verificado",
        "tipo_regime = 'MEI'",
        "uf = 'MG'",
        "vw_empresas_elegiveis",
    ):
        assert retired not in src


def test_mg_is_priority_only_not_exclusion():
    manager = (ROOT / "app/queue_manager.py").read_text(encoding="utf-8")
    assert "case when upper(coalesce(e.uf::text,''))='MG' then 0 else 1 end" in manager
    assert "uf = 'MG'" not in manager


def test_replenisher_uses_shared_queue_settings_and_bounded_batch():
    src = (ROOT / "scripts/queue_replenisher.py").read_text(encoding="utf-8")
    assert "settings.queue_target_pending" in src
    assert "settings.queue_min_pending" in src
    assert "LOCK_ID = CAMPAIGN_ENQUEUE_ADVISORY_LOCK_ID" in src
    assert "TARGET = 15000" not in src
    assert "MINIMUM = 14800" not in src
    assert "BATCH = min(200" in src
    assert "insert into mei_email.campanhas" in src
    assert "insert into mei_email.lotes" in src
    assert "insert into mei_email.envios" in src


def test_replenisher_uses_repo_relative_runtime_paths():
    src = (ROOT / "scripts/queue_replenisher.py").read_text(encoding="utf-8")
    assert "Path(__file__).resolve().parents[1]" in src
    assert "Path('/home/ubuntu/mei-mg-email')" not in src


def test_active_flyway_migrations_stop_at_v020():
    names = sorted(p.name for p in (ROOT / "db/migrations").glob("V[0-9]*__*.sql"))
    assert names[-1].startswith("V020__")
    archived = ROOT / "db/migrations_archived_post_v020_20260821"
    assert (archived / "V026__queue_status_index.sql").exists()
