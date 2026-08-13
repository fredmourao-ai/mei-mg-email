from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_suppression_callback_satisfies_historical_v019_dependency():
    callback = (ROOT / "db" / "migrations" / "beforeMigrate.sql").read_text(encoding="utf-8").casefold()
    assert "create table if not exists mei_email.email_suppressions" in callback
    assert "create or replace function mei_email.is_email_suppressed" in callback
    assert "p_email public.citext" in callback
    assert "idx_email_suppressions_lookup" in callback
    assert "uq_email_suppressions_active_scope_value" in callback

    compose = (ROOT / "docker-compose.yml").read_text(encoding="utf-8").casefold()
    assert "./db/migrations:/flyway/sql:ro" in compose
    assert "callbacklocations" not in compose

    v019 = (ROOT / "db" / "migrations" / "V019__deduplicate_shared_email_without_exclusion.sql").read_text(
        encoding="utf-8"
    ).casefold()
    assert "not mei_email.is_email_suppressed(e.email)" in v019


def test_status_enum_callback_recreates_production_v019_prerequisites():
    callback = (ROOT / "db" / "migrations" / "beforeEachMigrate.sql").read_text(
        encoding="utf-8"
    ).casefold()
    expected_in_order = [
        "descartado",
        "submitted",
        "sender_blocked",
        "bloqueado",
        "delivered",
        "bounce_permanent",
        "bounce_temporary",
        "suppressed",
        "cancelled",
        "pending",
        "processing",
        "failed",
    ]
    positions = []
    for label in expected_in_order:
        needle = f"add value if not exists '{label}'"
        assert needle in callback
        positions.append(callback.index(needle))
    assert positions == sorted(positions)
    assert "n.nspname = 'mei_email'" in callback
    assert "t.typname = 'status_envio'" in callback
