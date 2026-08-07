from urllib.error import HTTPError

from app.email_provider import MicrosoftGraphEmailProvider
from worker.worker import _erro_transitorio, montar_corpo


def test_transient_exchange_errors_are_retryable():
    for error in [
        "Microsoft Graph: TooManyRequests; http_429",
        "Microsoft Graph: ServiceUnavailable; http_503",
        "Microsoft Graph: too many requests (429)",
        "HTTP 429 too many requests",
        "service unavailable",
        "HTTP_503",
        "connection reset by peer",
        "request timed out",
    ]:
        assert _erro_transitorio(error), error


def test_retry_after_header_is_preserved():
    error = HTTPError(
        url="https://graph.microsoft.com/v1.0/users/test/sendMail",
        code=429,
        msg="Too Many Requests",
        hdrs={"Retry-After": "120"},
        fp=None,
    )
    assert MicrosoftGraphEmailProvider._parse_retry_after(error) == 120


def test_invalid_retry_after_is_ignored():
    error = HTTPError(
        url="https://graph.microsoft.com/v1.0/users/test/sendMail",
        code=503,
        msg="Service Unavailable",
        hdrs={"Retry-After": "not-a-number"},
        fp=None,
    )
    assert MicrosoftGraphEmailProvider._parse_retry_after(error) is None


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
