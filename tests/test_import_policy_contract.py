from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_campaign_creator_does_not_request_legacy_regime_filter():
    src = (ROOT / "scripts" / "criar_campanha_contabilidade_melo.py").read_text(
        encoding="utf-8"
    )

    assert "filtro_tipo_regime" not in src


def test_casa_dos_dados_import_keeps_mg_as_source_hint_only():
    src = (ROOT / "scripts" / "ingest_casa_dos_dados_daily.py").read_text(
        encoding="utf-8"
    )
    body = src.split("def main", 1)[1]

    assert 'company["uf"] != "MG"' not in body
    assert '"mei": {"optante": True}' not in src
    assert '"uf": ["mg"]' not in src


def test_public_imports_do_not_grant_legacy_authorization_or_mei_status():
    legacy_authorization = "marketing_" + "autorizado"
    for script in (
        "scripts/ingest_casa_dos_dados_daily.py",
        "scripts/ingest_from_huggingface.py",
        "scripts/ingest_estabelecimentos.py",
    ):
        src = (ROOT / script).read_text(encoding="utf-8")
        lowered = src.lower()
        assert legacy_authorization not in lowered
        assert "mei_verificado = true" not in lowered
        assert '"tipo_regime": "mei_candidato"' not in lowered
        assert '"tipo_regime": "mei"' not in lowered


def test_active_receita_import_has_no_legacy_mei_filter_switch():
    for path in (
        ROOT / 'scripts' / 'ingest_estabelecimentos.py',
        ROOT / 'app' / 'routes' / 'empresas.py',
    ):
        source = path.read_text(encoding='utf-8')
        assert 'filtrar_mei' not in source, path
