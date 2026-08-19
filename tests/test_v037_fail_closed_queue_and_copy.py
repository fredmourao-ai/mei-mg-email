from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "db/migrations/V037__fail_closed_open_queue_and_legacy_copy.sql"
MIGRATION_V038 = ROOT / "db/migrations/V038__enforce_campaign_copy_and_live_eligibility.sql"


def test_v037_never_grants_marketing_authorization():
    sql = MIGRATION.read_text(encoding="utf-8").casefold()
    assert "set marketing_autorizado = true" not in sql
    assert "base pública de cnpj" in sql
    assert "autorização comercial registrada" in sql


def test_v037_blocks_open_rows_that_lost_live_eligibility():
    sql = MIGRATION.read_text(encoding="utf-8").casefold()
    required = (
        "marketing_autorizado is not true",
        "mei_verificado is not true",
        "opt_out is true",
        "situacao_cadastral <> 'ativa'",
        "provavel_terceiro is true",
        "is_valid_email_address",
        "is_email_suppressed",
        "is_cnpj_suppressed",
        "::status_lote",
    )
    for token in required:
        assert token in sql
    assert "status = 'bloqueado'" in sql


def test_v038_prevents_legacy_copy_from_being_reintroduced():
    sql = MIGRATION_V038.read_text(encoding="utf-8").casefold()
    assert "enforce_campaign_copy_policy" in sql
    assert "before insert or update of corpo_template on campanhas" in sql
    assert "legacy public-cnpj marketing copy is forbidden" in sql
    assert "autorização comercial registrada" in sql
    assert "set marketing_autorizado = true" not in sql


def test_v038_enforces_live_eligibility_and_global_anti_replay():
    sql = MIGRATION_V038.read_text(encoding="utf-8").casefold()
    required = (
        "enforce_envio_live_eligibility",
        "before insert or update of status, cnpj, email on envios",
        "marketing_autorizado is true",
        "mei_verificado is true",
        "opt_out is false",
        "situacao_cadastral = 'ativa'",
        "provavel_terceiro is false",
        "is_valid_email_address",
        "is_email_suppressed",
        "is_cnpj_suppressed",
        "lower(btrim(prior.email::text)) = lower(btrim(new.email::text))",
        "prior.status::text in ('submitted', 'enviado', 'delivered')",
        "destinatario ja submetido/entregue",
        "new.status := 'bloqueado'::status_envio",
        "::status_lote",
    )
    for token in required:
        assert token in sql
