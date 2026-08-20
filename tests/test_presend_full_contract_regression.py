from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_effective_v2_presend_keeps_full_authorized_mei_contract():
    src = (ROOT / "worker/safe_entrypoint_v2.py").read_text()
    required = (
        "marketing_autorizado_origem",
        "_disallowed_marketing_origin",
        "mei_verificado",
        "mei_verificado_origem",
        "LEGACY_MEI_ORIGINS",
        "opt_out",
        "situacao_cadastral",
        'row["uf"]',
        'row["tipo_regime"]',
        "provavel_terceiro",
        "is_valid_email_address",
        "email_suppressions",
        "terminal_history",
        "envios_externos_cota",
    )
    for token in required:
        assert token in src
    assert "reason = any" not in src
    assert "protected_suppression" not in src
    assert 'as suppressed' in src


def test_synthesized_explicit_origin_is_fail_closed_again():
    base = (ROOT / "worker/safe_entrypoint.py").read_text()
    v2 = (ROOT / "worker/safe_entrypoint_v2.py").read_text()
    assert '"user_explicit_authorization_2026-08-20"' in base
    assert '"operator_authorization_true" in lowered' in v2
