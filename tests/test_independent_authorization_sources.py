from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


LEGACY_MARKETING_ORIGINS = (
    "confirmacao_operador_2026-08-12",
    "confirmacao_operador_2026-08-13",
    "politica_importacao_operador_2026-08-13",
)
LEGACY_MEI_ORIGINS = (
    "override_operador_2026-08-13",
    "politica_importacao_operador_2026-08-13",
)


def test_v040_rejects_legacy_operator_authorization_sources():
    migration = (
        ROOT
        / "db"
        / "migrations"
        / "V040__independent_authorization_source_and_terminal_replay_guard.sql"
    ).read_text(encoding="utf-8").casefold()

    assert "is_independent_marketing_authorization" in migration
    assert "is_independent_mei_verification" in migration
    for origin in LEGACY_MARKETING_ORIGINS + LEGACY_MEI_ORIGINS:
        assert origin.casefold() in migration

    assert "zz_empresas_enforce_independent_sources" in migration
    assert "tentativa de reabrir envio terminal" in migration
    assert "old.status::text in ('submitted', 'enviado', 'delivered')" in migration
    assert "trg_envio_live_eligibility" in migration


def test_autoqueue_requires_independent_sources_before_first_limit():
    source = (ROOT / "app" / "queue_manager.py").read_text(encoding="utf-8").casefold()
    base_start = source.index("with base as materialized")
    first_limit = source.index("limit %s", base_start)
    base = source[base_start:first_limit]

    assert "is_independent_marketing_authorization" in base
    assert "is_independent_mei_verification" in base
    assert "submitted" in base
    assert "enviado" in base
    assert "delivered" in base
    assert "bounced" in base


def test_v040_never_grants_authorization():
    migration = (
        ROOT
        / "db"
        / "migrations"
        / "V040__independent_authorization_source_and_terminal_replay_guard.sql"
    ).read_text(encoding="utf-8").casefold()
    assert "new.marketing_autorizado := true" not in migration
    assert "new.mei_verificado := true" not in migration
    assert "set marketing_autorizado = true" not in migration
    assert "set mei_verificado = true" not in migration


def test_v042_rejects_synthesized_recovery_authorization_before_autoqueue():
    migration = (
        ROOT
        / "db"
        / "migrations"
        / "V042__reject_synthesized_authorization_origins.sql"
    ).read_text(encoding="utf-8").casefold()

    assert "user_explicit_authorization_2026-08-20" in migration
    assert "operator_authorization_true" in migration
    assert "is_independent_marketing_authorization" in migration
    assert "create or replace view mei_email.vw_empresas_elegiveis" in migration
    assert "synthesized_authorization_rejected_20260820" in migration
    assert "status = 'bloqueado'" in migration
    assert "submitted" in migration
    assert "enviado" in migration
    assert "delivered" in migration
    assert "set marketing_autorizado = true" not in migration
