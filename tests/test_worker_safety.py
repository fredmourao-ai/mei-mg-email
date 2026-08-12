from datetime import date, timezone
from pathlib import Path
from urllib.error import HTTPError

from app.config import settings
from app.email_provider import MicrosoftGraphEmailProvider
from app.queue_manager import AUTOQUEUE_SUBJECT
from scripts.disparar_10000_mei_mg import EXPECTED_DAILY_TARGET, carregar_template_html
from scripts.ingest_casa_dos_dados_daily import (
    build_search_payload,
    extract_email,
    normalize_cnpj,
    normalize_company,
)
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


def test_daily_target_keeps_margin_and_recovery_rate():
    assert EXPECTED_DAILY_TARGET == 9950
    assert settings.meta_envios_por_dia == 9950
    assert settings.max_envios_por_dia == 10000
    assert settings.configured_rate_envios_por_minuto == 30
    assert settings.deliverability_max_envios_por_minuto == 10
    assert settings.rate_limit_envios_por_minuto == 10
    assert settings.meta_envios_por_dia < settings.max_envios_por_dia


def test_autoqueue_subject_is_clear_not_urgent():
    subject = AUTOQUEUE_SUBJECT.casefold()
    assert "contabilidade melo" in subject
    assert "importante" not in subject
    assert "urgente" not in subject
    assert "ultima chance" not in subject


def test_official_template_is_html_with_footer_logo_and_unsubscribe():
    template = carregar_template_html()
    lower = template.casefold()
    assert "<html" in lower
    assert "{{nome_fantasia}}" in template
    assert "{{unsubscribe_url}}" in template
    assert "logo-contabilidade-melo-transparente.png" in lower
    assert "autorização comercial" in lower
    assert "base pública de cnpj" not in lower
    assert "grátis" not in lower
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


def test_deliverability_consent_gate_blocks_public_or_unaudited_queue():
    migration = (ROOT / "db" / "migrations" / "V019__deliverability_consent_gate.sql").read_text(
        encoding="utf-8"
    )
    normalized = " ".join(migration.casefold().split())
    assert "marketing_autorizado_em is null" in normalized
    assert "marketing_autorizado_origem is null" in normalized
    assert "cadastro_site" in normalized
    assert "cliente_ativo" in normalized
    assert "importacao_consentida" in normalized
    assert "status = 'bloqueado'" in normalized
    assert "base publica de cnpj nunca e consentimento" in normalized


def test_pending_campaign_copy_is_neutralized():
    migration = (ROOT / "db" / "migrations" / "V020__refresh_pending_campaign_copy.sql").read_text(
        encoding="utf-8"
    )
    normalized = " ".join(migration.casefold().split())
    assert "contabilidade melo para mei: plano mensal e suporte fiscal" in normalized
    assert "autorização comercial registrada" in normalized
    assert "status::text in ('pendente', 'enviando')" in normalized


def test_exchange_transport_rules_add_bulk_compliance_headers():
    script = (ROOT / "scripts" / "configurar_exchange_deliverability.ps1").read_text(
        encoding="utf-8"
    ).casefold()
    assert "list-unsubscribe-post" in script
    assert "list-unsubscribe=one-click" in script
    assert "feedback-id" in script
    assert "setheadername" in script
    assert "setheadervalue" in script


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
    assert "ingest_casa_dos_dados_daily.py" in script
    assert "ingest_from_huggingface.py" in script
    assert "missing_secret" in script
    assert "source_stale" in script
    assert "disparar_10000" not in script
    assert "systemctl start mei-mg-email-worker" not in script


def test_source_metadata_datetime_parser_accepts_huggingface_iso_timestamp():
    dt = _parse_datetime("2026-08-08T12:00:00.000Z")
    assert dt is not None
    assert dt.tzinfo == timezone.utc
    assert dt.year == 2026


def test_mei_campaign_requires_official_verification_without_mass_rewrite():
    migration = (ROOT / "db" / "migrations" / "V016__verified_mei_eligibility.sql").read_text(
        encoding="utf-8"
    )
    normalized = " ".join(migration.casefold().split())
    assert "mei_verificado boolean not null default false" in normalized
    assert "tipo_regime not in ('mei', 'mei_candidato')" in normalized
    assert "mei_verificado = true" in normalized
    assert "marketing_autorizado = true" in normalized
    assert "update empresas set tipo_regime" not in normalized


def test_mirror_never_claims_verified_mei():
    script = (ROOT / "scripts" / "ingest_from_huggingface.py").read_text(encoding="utf-8").casefold()
    assert 'tipo_regime = "mei_candidato"' in script
    assert '"mei_verificado": true' not in script
    assert "mei_verificado = true" not in script
    assert "when mei_email.empresas.mei_verificado" in script


def test_official_simples_ingest_is_the_mei_verification_path():
    script = (ROOT / "scripts" / "ingest_estabelecimentos.py").read_text(encoding="utf-8").casefold()
    assert "opcao_pelo_mei" in script
    assert "receita_simples_opcao_mei" in script
    assert '"mei_verificado": mei_confirmado' in script


def test_casa_dos_dados_daily_payload_is_mg_mei_active_email_and_overlapping():
    payload = build_search_payload(date(2026, 8, 8), lookback_days=3, page=2, limit=100)
    assert payload["situacao_cadastral"] == ["ATIVA"]
    assert payload["uf"] == ["mg"]
    assert payload["mei"] == {"optante": True}
    assert payload["data_abertura"] == {"inicio": "2026-08-06", "fim": "2026-08-08"}
    assert payload["mais_filtros"]["com_email"] is True
    assert payload["mais_filtros"]["excluir_email_contab"] is True
    assert payload["pagina"] == 2
    assert payload["limite"] == 100


def test_casa_dos_dados_accepts_alphanumeric_cnpj_and_never_marks_verified_mei():
    assert normalize_cnpj("12.ABC.345/6789-01") == "12ABC345678901"
    company = normalize_company(
        {
            "cnpj": "12.ABC.345/6789-01",
            "razao_social": "MEI Teste",
            "nome_fantasia": "Teste",
            "situacao_cadastral": {"situacao_cadastral": "ATIVA"},
            "endereco": {"uf": "mg"},
            "data_abertura": "2026-08-08",
            "contato": {"email": "mei@example.com"},
        }
    )
    assert company is not None
    assert company["cnpj"] == "12ABC345678901"
    assert company["uf"] == "MG"
    assert company["email"] == "mei@example.com"
    assert company["tipo_regime"] == "MEI_CANDIDATO"
    assert "mei_verificado" not in company


def test_casa_dos_dados_email_extractor_ignores_accounting_email_field():
    item = {
        "email_contabilidade": "contador@example.com",
        "contatos": {"email": "empresa@example.com"},
    }
    assert extract_email(item) == "empresa@example.com"


def test_casa_dos_dados_ingest_preserves_campaign_safety_fields():
    script = (ROOT / "scripts" / "ingest_casa_dos_dados_daily.py").read_text(encoding="utf-8").casefold()
    assert "marketing_autorizado" in script
    assert "mei_verificado" in script
    assert "opt_out" in script
    assert "enviado" in script
    assert "disparar_10000" not in script
    assert "systemctl start mei-mg-email-worker" not in script
    assert "'mei_candidato'" in script or '"mei_candidato"' in script
