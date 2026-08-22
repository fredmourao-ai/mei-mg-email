from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_suppression_callback_satisfies_historical_v019_dependency():
    callback = (ROOT / "db" / "migrations" / "beforeMigrate.sql").read_text(encoding="utf-8").casefold()
    assert "create table if not exists mei_email.email_suppressions" in callback
    assert "create or replace function mei_email.is_email_suppressed" in callback
    assert "p_email public.citext" in callback
    assert "idx_email_suppressions_lookup" in callback
    assert "uq_email_suppressions_active_scope_value" in callback

    # O callback roda antes de cada Flyway migrate. Ele nao pode regredir a
    # funcao indexavel introduzida pela V027, senao a elegibilidade volta a
    # aplicar funcoes sobre a coluna e pode exceder statement_timeout.
    assert "lower(btrim(s.value::text))" not in callback
    assert "s.value = lower(btrim(p_email::text))::public.citext" in callback
    assert "s.value = split_part(lower(btrim(p_email::text)), '@', 2)::public.citext" in callback

    compose = (ROOT / "docker-compose.yml").read_text(encoding="utf-8").casefold()
    assert "./db/migrations:/flyway/sql:ro" in compose
    assert "callbacklocations" not in compose

    v019 = (ROOT / "db" / "migrations" / "V019__deduplicate_shared_email_without_exclusion.sql").read_text(
        encoding="utf-8"
    ).casefold()
    assert "not mei_email.is_email_suppressed(e.email)" in v019


def test_before_migrate_fails_closed_on_divergent_legacy_history():
    callback = (ROOT / "db" / "migrations" / "beforeMigrate.sql").read_text(
        encoding="utf-8"
    ).casefold()
    assert "flyway_history_divergence" in callback
    assert "mei_email.flyway_schema_history" in callback
    assert "v_max < 31" in callback
    assert "mei_email.envios_externos_cota" in callback
    assert "v_max < 34" in callback
    assert "guard_uncertain_graph_dispatch_replay" in callback
    assert "refusing to replay v021-v023 authorization migrations" in callback


def test_v039_repairs_callback_suppression_lookup_in_existing_databases():
    migration = (
        ROOT / "db" / "migrations_archived_post_v020_20260821" / "V039__restore_indexed_suppression_lookup_after_callback.sql"
    ).read_text(encoding="utf-8").casefold()
    assert "create or replace function mei_email.is_email_suppressed" in migration
    assert "idx_email_suppressions_lookup" in migration
    assert "lower(btrim(s.value::text))" not in migration
    assert "s.value = lower(btrim(p_email::text))::public.citext" in migration
    assert "s.value = split_part(lower(btrim(p_email::text)), '@', 2)::public.citext" in migration


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
