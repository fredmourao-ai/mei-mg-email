from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_api_defaults_to_loopback_only():
    config = (ROOT / "app" / "config.py").read_text(encoding="utf-8")
    env_example = (ROOT / ".env.example").read_text(encoding="utf-8")
    assert 'os.getenv("API_HOST", "127.0.0.1")' in config
    assert "API_HOST=127.0.0.1" in env_example


def test_campaign_api_has_no_dynamic_sql_template_for_canonical_filters():
    source = (ROOT / "app" / "routes" / "campanhas.py").read_text(encoding="utf-8")
    assert "where_clause" not in source
    assert "f\"\"\"" not in source


def test_campaign_request_limit_matches_brevo_free_cap():
    source = (ROOT / "app" / "schemas.py").read_text(encoding="utf-8")
    block = source.split("limite_empresas", 1)[1].split("class CampanhaOut", 1)[0]
    assert "le=300" in block
    assert "Brevo" in block
    assert "10000" not in block


def test_base_update_does_not_expose_internal_exception_text():
    source = (ROOT / "app" / "routes" / "empresas.py").read_text(encoding="utf-8")
    assert "logger.exception" in source
    assert "str(e)" not in source
    assert 'detail="Erro interno durante a atualizacao da base"' in source


def test_campaign_api_applies_full_canonical_recipient_policy():
    source = (ROOT / "app" / "routes" / "campanhas.py").read_text(encoding="utf-8").casefold()
    assert "situacao_cadastral = 'ativa'" in source
    assert "coalesce(opt_out, false) = false" in source
    assert "position('contabil'" in source
    assert "is_valid_email_address" in source
    assert "is_email_suppressed" in source
    assert "is_cnpj_suppressed" in source
    assert "count(distinct e2.cnpj)" in source
    assert "<= 2" in source
    assert "not exists" in source and "mei_email.envios" in source
    assert "case when upper(coalesce" in source and "='mg'" in source
    for forbidden in ("mei_verificado", "tipo_regime", "filter_not_mei", "insert_filter_gate", "vw_empresas_elegiveis"):
        assert forbidden not in source
