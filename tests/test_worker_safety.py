import json
from pathlib import Path
from urllib.error import HTTPError

from app.config import settings
from app.email_provider import MicrosoftGraphEmailProvider
from app import send_control
from scripts.disparar_10000_mei_mg import EXPECTED_DAILY_TARGET, carregar_template_html
from worker.worker import _classificar_falha_final, _erro_transitorio, montar_corpo

ROOT = Path(__file__).resolve().parents[1]


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


def test_graph_send_includes_reply_to(monkeypatch):
    provider = MicrosoftGraphEmailProvider()
    captured = {}

    class FakeResponse:
        status = 202
        headers = {"request-id": "request-123"}

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr(provider, "_get_access_token", lambda: "token-value")

    def fake_urlopen(request, timeout=30):
        captured["url"] = request.full_url
        captured["body"] = json.loads(request.data.decode("utf-8"))
        captured["timeout"] = timeout
        return FakeResponse()

    monkeypatch.setattr("app.email_provider.urlopen", fake_urlopen)

    result = provider.send("cliente@example.com", "Assunto teste", "<html><body>teste</body></html>")

    assert result.success is True
    assert captured["timeout"] == 30
    assert captured["body"]["message"]["replyTo"][0]["emailAddress"]["address"] == "fiscalmelo@hotmail.com"
    assert captured["body"]["message"]["toRecipients"][0]["emailAddress"]["address"] == "cliente@example.com"


def test_permanent_errors_are_not_retried_forever():
    for error in [
        "Microsoft Graph: ErrorSendAsDenied",
        "invalid recipient address",
        "authentication failed",
        "mailbox not found",
        None,
        ]:
        assert not _erro_transitorio(error), error


def test_sender_blocked_error_is_classified():
    status, ndr_code, reason = _classificar_falha_final(
        "550 5.1.8 Access denied, bad outbound sender AS(42004)"
    )
    assert status == "sender_blocked"
    assert ndr_code == "AS(42004)"
    assert "Access denied" in reason


def test_permanent_bounce_is_classified():
    status, ndr_code, reason = _classificar_falha_final("550 5.4.312 Message expired, DNS query failed")
    assert status == "bounce_permanent"
    assert ndr_code == "5.4.312"
    assert "DNS query failed" in reason


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


def test_daily_target_keeps_margin_below_hard_cap():
    assert EXPECTED_DAILY_TARGET == 9950
    assert settings.meta_envios_por_dia == 9950
    assert settings.max_envios_por_dia == 10000
    assert settings.meta_envios_por_dia < settings.max_envios_por_dia


def test_official_template_is_html_with_footer_logo_and_unsubscribe():
    template = carregar_template_html()
    lower = template.casefold()
    assert "<html" in lower
    assert "{{nome_fantasia}}" in template
    assert "{{unsubscribe_url}}" in template
    assert "logo-contabilidade-melo-transparente.png" in lower
    assert "</html>" in lower


def test_send_pause_file_controls_state(tmp_path, monkeypatch):
    pause_file = tmp_path / "email-sends.paused"
    monkeypatch.setattr(send_control, "PAUSE_FILE", pause_file)

    assert not send_control.email_sends_paused()
    send_control.pause_email_sends("teste manual")
    assert send_control.email_sends_paused()
    assert "reason=teste manual" in pause_file.read_text(encoding="utf-8")

    send_control.resume_email_sends()
    assert not send_control.email_sends_paused()


def test_daily_enqueue_stops_when_paused(monkeypatch):
    from scripts import disparar_10000_mei_mg as disparar

    monkeypatch.setattr(disparar, "email_sends_paused", lambda: True)
    assert disparar.enfileirar_meta_diaria_mei_mg() == 0


def test_fail_closed_migration_requires_authorization_and_global_dedupe():
    migration = (ROOT / "db" / "migrations" / "V010__eligibility_consent_and_global_dedupe.sql").read_text(
        encoding="utf-8"
    )
    normalized = " ".join(migration.casefold().split())
    assert "marketing_autorizado = true" in normalized
    assert "not exists" in normalized
    assert "from envios" in normalized
    assert "lower(btrim(x.email::text))" in normalized
    assert "situacao_cadastral = 'ativa'" in normalized
