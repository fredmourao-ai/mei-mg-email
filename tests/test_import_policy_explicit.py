from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_casa_dos_dados_public_base_does_not_grant_marketing_opt_in():
    script = (ROOT / "scripts" / "ingest_casa_dos_dados_daily.py").read_text(
        encoding="utf-8"
    ).casefold()

    assert "marketing_autorizado, marketing_autorizado_em, marketing_autorizado_origem" in script
    assert "mei_verificado, mei_verificado_em, mei_verificado_origem" in script
    assert "false, null, 'base_publica_sem_opt_in'" in script
    assert "marketing_autorizado = mei_email.empresas.marketing_autorizado" in script
    assert "marketing_autorizado_em = mei_email.empresas.marketing_autorizado_em" in script
    assert "marketing_autorizado_origem = mei_email.empresas.marketing_autorizado_origem" in script
    assert "mei_verificado = true" in script
    assert "base_publica_nao_concede_opt_in" in script
    assert "marketing_autorizado = true" not in script
    assert "opt_out =" not in script
    assert "systemctl start mei-mg-email-worker" not in script


def test_v033_revokes_only_legacy_public_base_authorization():
    migration = (
        ROOT / "db" / "migrations" / "V033__public_cnpj_base_is_not_marketing_opt_in.sql"
    ).read_text(encoding="utf-8").casefold()
    assert "marketing_autorizado = false" in migration
    assert "marketing_autorizado_origem = 'politica_importacao_operador_2026-08-13'" in migration
    assert "base_publica_sem_opt_in_20260819" in migration
