from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_v025_blocks_reimport_and_purges_operational_pii():
    migration = (ROOT / "db" / "migrations" / "V025__purge_operational_records_and_block_reimport.sql").read_text(
        encoding="utf-8"
    ).casefold()
    normalized = " ".join(migration.split())

    assert "'cnpj'::text" in normalized
    assert "is_cnpj_suppressed" in normalized
    assert "register_operational_suppression" in normalized
    assert "zz_empresas_block_suppressed_or_rejected_insert" in normalized
    assert "return null" in normalized
    assert "zz_empresas_purge_rejected_after_update" in normalized
    assert "zz_envios_archive_and_purge_pii" in normalized
    assert "pii_purged_rate_ledger" in normalized
    assert "quota+" in normalized
    assert "interval '24 hours'" in normalized
    assert "delete from mei_email.empresas" in normalized
    assert "delete from mei_email.envios" in normalized


def test_v025_final_view_is_strict_mei_mg_filter():
    migration = (ROOT / "db" / "migrations" / "V025__purge_operational_records_and_block_reimport.sql").read_text(
        encoding="utf-8"
    ).casefold()
    normalized = " ".join(migration.split())

    assert "e.situacao_cadastral = 'ativa'" in normalized
    assert "upper(e.uf) = 'mg'" in normalized
    assert "e.provavel_terceiro = false" in normalized
    assert "e.marketing_autorizado = true" in normalized
    assert "e.tipo_regime = 'mei'" in normalized
    assert "e.mei_verificado = true" in normalized
    assert "not mei_email.is_email_suppressed(e.email)" in normalized
    assert "not mei_email.is_cnpj_suppressed(e.cnpj::text)" in normalized


def test_cleanup_script_is_apply_guarded_and_uses_suppression():
    script = (ROOT / "scripts" / "purgar_base_operacional.py").read_text(encoding="utf-8").casefold()
    assert 'parser.add_argument("--apply"' in script
    assert "register_operational_suppression" in script
    assert "purged_sent" in script
    assert "purged_filtered" in script
