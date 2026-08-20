from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SYNTHETIC_ORIGIN = "user_campaign_authorization_2026-08-20"


def test_runtime_rejects_synthetic_campaign_authorization_origin():
    source = (ROOT / "worker" / "safe_entrypoint.py").read_text(encoding="utf-8")
    assert SYNTHETIC_ORIGIN in source
    assert "LEGACY_MARKETING_ORIGINS" in source


def test_v044_restores_mei_and_independent_verification_guards():
    migration = (
        ROOT
        / "db"
        / "migrations"
        / "V044__restore_strict_mei_campaign_after_general_fallback.sql"
    ).read_text(encoding="utf-8").casefold()

    assert SYNTHETIC_ORIGIN.casefold() in migration
    assert "is_independent_marketing_authorization" in migration
    assert "is_independent_mei_verification" in migration
    assert "tipo_regime" in migration
    assert "'mei'" in migration
    assert "trg_envio_live_eligibility" in migration
    assert "tentativa de reabrir envio terminal" in migration
    assert "submitted" in migration
    assert "enviado" in migration
    assert "delivered" in migration


def test_v044_never_grants_consent_or_reopens_terminal_history():
    migration = (
        ROOT
        / "db"
        / "migrations"
        / "V044__restore_strict_mei_campaign_after_general_fallback.sql"
    ).read_text(encoding="utf-8").casefold()

    assert "set marketing_autorizado = true" not in migration
    assert "set mei_verificado = true" not in migration
    assert "set marketing_autorizado = false" in migration
    assert "status::text in ('pendente', 'pending', 'enviando', 'processing')" in migration
