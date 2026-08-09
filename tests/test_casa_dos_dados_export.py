from scripts.casa_dos_dados_export import build_payload, sanitized_history


def test_mg_export_payload_requires_active_mei_with_email():
    payload = build_payload("mg", "base@example.com", "mei-mg")

    assert payload["tipo"] == "csv"
    assert payload["pesquisa"]["uf"] == ["mg"]
    assert payload["pesquisa"]["situacao_cadastral"] == ["ATIVA"]
    assert payload["pesquisa"]["mei"] == {"optante": True}
    assert payload["pesquisa"]["mais_filtros"] == {
        "com_email": True,
        "excluir_email_contab": True,
    }


def test_national_export_payload_has_no_state_filter():
    payload = build_payload("nacional", "base@example.com", "mei-nacional")

    assert "uf" not in payload["pesquisa"]


def test_history_redacts_export_recipients():
    history = sanitized_history([{
        "arquivo_uuid": "abc",
        "status": "concluido",
        "enviar_para": ["private@example.com"],
    }])

    assert history == [{
        "arquivo_uuid": "abc",
        "nome": None,
        "tipo": None,
        "status": "concluido",
        "quantidade": None,
        "quantidade_solicitada": None,
        "criado": None,
        "atualizado": None,
    }]
