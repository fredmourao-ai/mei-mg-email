from worker.worker import _erro_transitorio, montar_corpo


def test_transient_exchange_errors_are_retryable():
    for error in [
        "Microsoft Graph: TooManyRequests",
        "HTTP 429 too many requests",
        "ServiceUnavailable",
        "HTTP_503",
        "connection reset by peer",
        "request timed out",
    ]:
        assert _erro_transitorio(error), error


def test_permanent_errors_are_not_retried_forever():
    for error in [
        "Microsoft Graph: ErrorSendAsDenied",
        "invalid recipient address",
        "authentication failed",
        "mailbox not found",
        None,
    ]:
        assert not _erro_transitorio(error), error


def test_unsubscribe_url_is_injected(monkeypatch):
    from app import config

    monkeypatch.setattr(config.settings, "base_url_descadastro", "https://dev.shopvivaliz.com.br/descadastro")
    corpo = montar_corpo(
        "Ola {{razao_social}}. Sair: {{unsubscribe_url}}",
        {
            "cnpj": "12345678000190",
            "email": "cliente+teste@example.com",
            "razao_social": "Empresa Teste",
            "nome_fantasia": "Teste",
        },
    )
    assert "Empresa Teste" in corpo
    assert "https://dev.shopvivaliz.com.br/descadastro?" in corpo
    assert "cliente%2Bteste%40example.com" in corpo
    assert "12345678000190" in corpo
