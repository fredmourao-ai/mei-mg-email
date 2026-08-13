from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_casa_dos_dados_upsert_sets_operator_policy_explicitly():
    script = (ROOT / "scripts" / "ingest_casa_dos_dados_daily.py").read_text(
        encoding="utf-8"
    ).casefold()

    assert "marketing_autorizado, marketing_autorizado_em, marketing_autorizado_origem" in script
    assert "mei_verificado, mei_verificado_em, mei_verificado_origem" in script
    assert "marketing_autorizado = true" in script
    assert "mei_verificado = true" in script
    assert "politica_importacao_operador_2026-08-13" in script
    assert "opt_out =" not in script
    assert "systemctl start mei-mg-email-worker" not in script
