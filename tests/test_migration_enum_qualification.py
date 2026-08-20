from pathlib import Path
import re


MIGRATIONS = (
    "V037__fail_closed_open_queue_and_legacy_copy.sql",
    "V038__enforce_campaign_copy_and_live_eligibility.sql",
    "V044__restore_strict_mei_campaign_after_general_fallback.sql",
    "V045__qualify_runtime_status_enum_casts.sql",
)


def test_runtime_status_enum_casts_are_schema_qualified() -> None:
    root = Path(__file__).resolve().parents[1] / "db" / "migrations"
    unqualified = re.compile(r"::\s*status_(?:envio|lote)\b", re.IGNORECASE)
    for name in MIGRATIONS:
        sql = (root / name).read_text(encoding="utf-8")
        assert not unqualified.search(sql), f"{name} contains an unqualified runtime enum cast"


def test_v045_repairs_function_in_place_without_trigger_ddl() -> None:
    sql = (
        Path(__file__).resolve().parents[1]
        / "db"
        / "migrations"
        / "V045__qualify_runtime_status_enum_casts.sql"
    ).read_text(encoding="utf-8").lower()
    assert "create or replace function mei_email.enforce_envio_live_eligibility()" in sql
    assert "::mei_email.status_envio" in sql
    assert "drop trigger" not in sql
    assert "create trigger" not in sql
    assert "user_campaign_authorization_2026-08-20" in sql
    assert "is_independent_marketing_authorization" in sql
    assert "is_independent_mei_verification" in sql
    assert "submitted" in sql and "delivered" in sql
