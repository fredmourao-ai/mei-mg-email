from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_suppression_bootstrap_satisfies_historical_v019_dependency():
    bootstrap = (ROOT / "db" / "init" / "01_email_suppressions.sql").read_text(encoding="utf-8").casefold()
    assert "create table if not exists mei_email.email_suppressions" in bootstrap
    assert "create or replace function mei_email.is_email_suppressed" in bootstrap
    assert "p_email public.citext" in bootstrap
    assert "idx_email_suppressions_lookup" in bootstrap
    assert "uq_email_suppressions_active_scope_value" in bootstrap

    v019 = (ROOT / "db" / "migrations" / "V019__deduplicate_shared_email_without_exclusion.sql").read_text(
        encoding="utf-8"
    ).casefold()
    assert "not mei_email.is_email_suppressed(e.email)" in v019
