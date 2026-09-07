import json

import app.email_provider as provider_module
from app.email_provider import ALLOWED_SENDER, get_email_provider


class FakeResponse:
    status = 201
    headers = {}

    def __init__(self, payload: dict):
        self._payload = payload

    def read(self):
        return json.dumps(self._payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False


def test_brevo_storage_id_is_provider_attributed():
    assert provider_module.brevo_storage_message_id("<abc@example>") == "brevo:<abc@example>"


def test_brevo_and_legacy_graph_senders_are_separate():
    assert provider_module.BREVO_ALLOWED_SENDER == "atendimento@shopvivaliz.com.br"
    assert ALLOWED_SENDER == "naoresponda@dev.shopvivaliz.com.br"


def test_brevo_provider_posts_transactional_email(monkeypatch):
    seen = {}
    monkeypatch.setenv("BREVO_API_KEY", "secret-test-key")
    monkeypatch.setenv("MAIL_FROM", provider_module.BREVO_ALLOWED_SENDER)
    monkeypatch.setenv("MAIL_FROM_NAME", "Contabilidade Melo")

    def fake_urlopen(request, timeout=0):
        seen["request"] = request
        seen["timeout"] = timeout
        return FakeResponse({"messageId": "<abc@example>"})

    monkeypatch.setattr(provider_module, "urlopen", fake_urlopen)
    provider = get_email_provider("brevo")
    result = provider.send(
        "owner@example.com", "Assunto", "<html><body>Oi</body></html>"
    )

    request = seen["request"]
    payload = json.loads(request.data.decode("utf-8"))
    headers = {k.casefold(): v for k, v in request.headers.items()}
    assert request.full_url == "https://api.brevo.com/v3/smtp/email"
    assert request.method == "POST"
    assert headers["api-key"] == "secret-test-key"
    assert payload["sender"]["email"] == provider_module.BREVO_ALLOWED_SENDER
    assert payload["replyTo"]["email"] == "fiscalmelo@hotmail.com"
    assert payload["to"] == [{"email": "owner@example.com"}]
    assert payload["htmlContent"].startswith("<html>")
    assert result.success is True
    assert result.status == "submitted"
    assert result.status_code == 201
    assert result.message_id == "brevo:<abc@example>"
