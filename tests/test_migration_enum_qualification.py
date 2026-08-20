from pathlib import Path
import re


def _v045_sql() -> str:
    return (
        Path(__file__).resolve().parents[1]
        / "db"
        / "migrations"
        / "V045__qualify_runtime_status_enum_casts.sql"
    ).read_text(encoding="utf-8")


def test_v045_runtime_status_enum_casts_are_schema_qualified() -> None:
    sql = _v045_sql()
    unqualified = re.compile(r"::\s*status_(?:envio|lote)\b", re.IGNORECASE)
    assert not unqualified.search(sql)
    assert "::mei_email.status_envio" in sql


def test_v045_repairs_function_in_place_without_trigger_ddl() -> None:
    sql = _v045_sql().lower()
    assert "create or replace function mei_email.enforce_envio_live_eligibility()" in sql
    assert "drop trigger" not in sql
    assert "create trigger" not in sql
    assert "user_campaign_authorization_2026-08-20" in sql
    assert "is_independent_marketing_authorization" in sql
    assert "is_independent_mei_verification" in sql
    assert "submitted" in sql and "delivered" in sql
