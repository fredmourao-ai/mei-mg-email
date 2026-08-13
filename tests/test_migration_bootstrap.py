from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_suppression_callback_satisfies_historical_v019_dependency():
    callback = (ROOT / "db" / "callbacks" / "beforeMigrate.sql").read_text(encoding="utf-8").casefold()
    assert "create table if not exists mei_email.email_suppressions" in callback
    assert "create or replace function mei_email.is_email_suppressed" in callback
    assert "p_email public.citext" in callback
    assert "idx_email_suppressions_lookup" in callback
    assert "uq_email_suppressions_active_scope_value" in callback

    compose = (ROOT / "docker-compose.yml").read_text(encoding="utf-8").casefold()
    assert "flyway_callback_locations: filesystem:/flyway/callbacks" in compose
    assert "./db/callbacks:/flyway/callbacks:ro" in compose

    v019 = (ROOT / "db" / "migrations" / "V019__deduplicate_shared_email_without_exclusion.sql").read_text(
        encoding="utf-8"
    ).casefold()
    assert "not mei_email.is_email_suppressed(e.email)" in v019
