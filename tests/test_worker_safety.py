from datetime import timezone
from pathlib import Path
from urllib.error import HTTPError

from app.config import settings
from app.email_provider import MicrosoftGraphEmailProvider
from scripts.disparar_10000_mei_mg import EXPECTED_DAILY_TARGET, carregar_template_html
from scripts.sincronizar_base_diaria import _parse_datetime
from worker.worker import _erro_transitorio, montar_corpo

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


def test_daily_target_keeps_margin_below_hard_cap():
    assert EXPECTED_DAILY_TARGET == 9950
    assert settings.meta_envios_por_dia == 9950
    assert settings.max_envios_por_dia == 10000
    assert settings.rate_limit_envios_por_minuto == 30
    assert settings.meta_envios_por_dia < settings.max_envios_por_dia


def test_official_template_is_html_with_footer_logo_and_unsubscribe():
    template = carregar_template_html()
    lower = template.casefold()
    assert "<html" in lower
    assert "{{nome_fantasia}}" in template
    assert "{{unsubscribe_url}}" in template
    assert "logo-contabilidade-melo-transparente.png" in lower
    assert "</html>" in lower


def test_fail_closed_migration_requires_authorization_and_global_dedupe():
    migration = (ROOT / "db" / "migrations" / "V013__eligibility_consent_and_global_dedupe.sql").read_text(
        encoding="utf-8"
    )
    normalized = " ".join(migration.casefold().split())
    assert "marketing_autorizado = true" in normalized
    assert "not exists" in normalized
    assert "from envios" in normalized
    assert "lower(btrim(x.email::text))" in normalized
    assert "situacao_cadastral = 'ativa'" in normalized


def test_cnpj_alphanumeric_migration_and_submitted_guard_are_present():
    migration = (ROOT / "db" / "migrations" / "V014__cnpj_alphanumeric_and_submission_guard.sql").read_text(
        encoding="utf-8"
    )
    normalized = " ".join(migration.casefold().split())
    assert "^[0-9a-z]{12}[0-9]{2}$" in normalized
    assert "trg_marcar_empresa_submetida" in normalized
    assert "('submitted', 'enviado')" in normalized
    assert "x.cnpj = e.cnpj" in normalized
    assert "lower(btrim(x.email::text))" in normalized
    assert "marketing_autorizado = true" in normalized


def test_daily_base_sync_is_independent_from_bulk_send():
    script = (ROOT / "scripts" / "sincronizar_base_diaria.py").read_text(encoding="utf-8").casefold()
    assert "base_sync_runs" in script
    assert "ingest_from_huggingface.py" in script
    assert "source_stale" in script
    assert "disparar_10000" not in script
    assert "systemctl start mei-mg-email-worker" not in script


def test_source_metadata_datetime_parser_accepts_huggingface_iso_timestamp():
    dt = _parse_datetime("2026-08-08T12:00:00.000Z")
    assert dt is not None
    assert dt.tzinfo == timezone.utc
    assert dt.year == 2026
