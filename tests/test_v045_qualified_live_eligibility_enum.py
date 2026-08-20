from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "db/migrations/V045__qualify_live_eligibility_enum.sql"


def test_v045_qualifies_enum_and_function_search_path():
    sql = MIGRATION.read_text()
    assert "'bloqueado'::mei_email.status_envio" in sql
    assert "set search_path = mei_email, public" in sql
    assert "create or replace function mei_email.enforce_envio_live_eligibility" in sql


def test_v045_does_not_relax_live_eligibility_contract():
    sql = MIGRATION.read_text().lower()
    assert "is_independent_marketing_authorization" in sql
    assert "is_independent_mei_verification" in sql
    assert "opt_out is false" in sql
    assert "situacao_cadastral = 'ativa'" in sql
    assert "provavel_terceiro is false" in sql
    assert "is_email_suppressed" in sql
    assert "is_cnpj_suppressed" in sql
    assert "already_terminal" in sql
