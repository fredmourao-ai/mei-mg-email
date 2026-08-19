from pathlib import Path


MIGRATION = (
    Path(__file__).resolve().parents[1]
    / "db/migrations/V037__fail_closed_open_queue_and_legacy_copy.sql"
)


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
    )
    for token in required:
        assert token in sql
    assert "status = 'bloqueado'" in sql
