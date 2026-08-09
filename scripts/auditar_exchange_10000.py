#!/usr/bin/env python3
"""Auditoria fail-closed para a meta operacional de 9.950 destinatarios/24h.

Executar no mesmo ambiente do worker, com o .env, token cache Graph e banco de
producao. O script NAO envia e-mail. Valida DNS, token OAuth nao interativo,
remetente, TERRL informado pelo administrador, template HTML e estado da fila.
"""
from __future__ import annotations

import os
import subprocess
import sys
from email.utils import parseaddr
from pathlib import Path
from urllib.parse import urlsplit

import psycopg

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from app.config import settings

EXPECTED_DOMAIN = os.getenv("MICROSOFT_SENDER_DOMAIN", "dev.shopvivaliz.com.br").strip().lower().rstrip(".")
TEMPLATE_PATH = BASE_DIR / "templates" / "mei-contabilidade-melo.html"


def sender_address() -> str:
    if settings.email_provider in {"microsoft_graph", "microsoft-oauth", "graph"}:
        return os.getenv("MICROSOFT_GRAPH_USER", "").strip()
    return ""


def run_script(name: str) -> tuple[bool, str]:
    result = subprocess.run(
        [sys.executable, str(BASE_DIR / "scripts" / name)],
        cwd=str(BASE_DIR),
        env=dict(os.environ),
        text=True,
        capture_output=True,
        timeout=60,
    )
    return result.returncode == 0, (result.stdout + "\n" + result.stderr).strip()


def main() -> int:
    errors: list[str] = []
    warnings: list[str] = []

    if settings.email_provider not in {"microsoft_graph", "microsoft-oauth", "graph"}:
        errors.append(f"provider_nao_exchange={settings.email_provider}")

    if settings.max_envios_por_dia != 10000:
        errors.append(f"MAX_ENVIOS_POR_DIA_deve_ser_10000={settings.max_envios_por_dia}")
    if settings.meta_envios_por_dia != 9950:
        errors.append(f"META_ENVIOS_POR_DIA_deve_ser_9950={settings.meta_envios_por_dia}")
    if settings.meta_envios_por_dia >= settings.max_envios_por_dia:
        errors.append("meta_sem_margem_abaixo_do_teto")
    if settings.rate_limit_envios_por_minuto <= 0 or settings.rate_limit_envios_por_minuto > 30:
        errors.append(f"rate_limit_invalido={settings.rate_limit_envios_por_minuto}")
    elif settings.rate_limit_envios_por_minuto > 20:
        warnings.append("rate_limit_acima_de_20_min_reduz_margem_para_throttling")

    sender = sender_address()
    if not sender or "@" not in sender:
        errors.append("remetente_microsoft_nao_configurado")
        sender_domain = ""
    else:
        sender_domain = sender.rsplit("@", 1)[1].lower().rstrip(".")
        if sender_domain.endswith(".onmicrosoft.com") or sender_domain == "onmicrosoft.com":
            errors.append("dominio_onmicrosoft_nao_permitido_para_esta_operacao")
        if sender_domain != EXPECTED_DOMAIN:
            errors.append(f"sender_domain_diverge={sender_domain}!={EXPECTED_DOMAIN}")

    mail_from = os.getenv("MAIL_FROM", "").strip()
    _, mail_from_address = parseaddr(mail_from)
    if not mail_from_address:
        warnings.append("MAIL_FROM_nao_configurado")
    elif sender and mail_from_address.casefold() != sender.casefold():
        errors.append(f"MAIL_FROM_diverge_do_usuario_microsoft={mail_from_address}!={sender}")

    reply_to = os.getenv("MAIL_REPLY_TO", "").strip() or os.getenv("REPLY_TO", "").strip()
    _, reply_to_address = parseaddr(reply_to)
    if not reply_to_address:
        warnings.append("MAIL_REPLY_TO_nao_configurado")
    elif reply_to_address.casefold() != "fiscalmelo@hotmail.com":
        errors.append(f"MAIL_REPLY_TO_diverge={reply_to_address}!=fiscalmelo@hotmail.com")

    unsubscribe = urlsplit(settings.base_url_descadastro)
    if unsubscribe.scheme != "https" or not unsubscribe.netloc:
        errors.append("BASE_URL_DESCADASTRO_deve_ser_https_publico")

    try:
        template = TEMPLATE_PATH.read_text(encoding="utf-8")
        lower = template.casefold()
        for required in ("<html", "{{unsubscribe_url}}", "{{nome_fantasia}}", "logo-contabilidade-melo-transparente.png"):
            if required.casefold() not in lower:
                errors.append(f"template_html_faltando={required}")
    except OSError as exc:
        errors.append(f"template_html_indisponivel={exc}")

    terrl_raw = os.getenv("MICROSOFT_TERRL_THRESHOLD", "").strip()
    try:
        terrl = int(terrl_raw)
    except ValueError:
        terrl = 0
    if terrl < settings.meta_envios_por_dia:
        errors.append(
            "MICROSOFT_TERRL_THRESHOLD_insuficiente_ou_nao_confirmado=" + (terrl_raw or "nao_configurado")
        )
    elif terrl - settings.meta_envios_por_dia < 50:
        warnings.append(f"margem_TERRL_menor_que_50={terrl - settings.meta_envios_por_dia}")

    dns_ok, dns_output = run_script("auditar_dns_microsoft.py")
    if not dns_ok:
        errors.append("dns_microsoft_custom_domain_not_ready")

    graph_output = "not_applicable"
    if settings.email_provider in {"microsoft_graph", "microsoft-oauth", "graph"}:
        graph_ok, graph_output = run_script("auditar_graph_token.py")
        if not graph_ok:
            errors.append("graph_token_cache_not_ready")

    try:
        with psycopg.connect(settings.database_url) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    select
                      count(*) filter (
                        where status in ('submitted', 'delivered', 'enviado')
                          and coalesce(submitted_at, enviado_em, criado_em) >= now() - interval '24 hours'
                      ) as submitted_24h,
                      count(*) filter (
                        where status in ('pending', 'processing', 'submitted', 'pendente', 'enviando', 'enviado')
                      ) as pendentes,
                      count(*) filter (
                        where status in ('failed', 'falhou')
                          and coalesce(failed_at, criado_em) >= now() - interval '24 hours'
                      ) as falhas_24h,
                      count(*) filter (
                        where status in ('bounce_temporary', 'bounce_permanent', 'sender_blocked', 'bounced')
                          and coalesce(bounced_at, criado_em) >= now() - interval '24 hours'
                      ) as bounces_24h,
                      count(*) filter (where status in ('cancelled', 'bloqueado')) as cancelados,
                      count(*) filter (where status in ('suppressed', 'opt_out')) as suppressed
                    from mei_email.envios
                    """
                )
                submitted_24h, pendentes, falhas_24h, bounces_24h, cancelados, suppressed = cur.fetchone()

                cur.execute("select count(*) from mei_email.vw_empresas_elegiveis")
                elegiveis = cur.fetchone()[0]

                cur.execute(
                    """
                    select count(*)
                      from mei_email.envios e
                      join mei_email.empresas emp on emp.cnpj = e.cnpj
                     where e.status in ('pending', 'processing', 'submitted', 'pendente', 'enviando', 'enviado')
                       and (emp.situacao_cadastral <> 'ATIVA' or emp.opt_out or not emp.marketing_autorizado)
                    """
                )
                fila_invalida = cur.fetchone()[0]

                cur.execute(
                    """
                      select count(*)
                      from (
                        select lower(btrim(email::text)) as email_normalizado
                          from mei_email.envios
                         where status in ('pending', 'processing', 'submitted', 'delivered', 'pendente', 'enviando', 'enviado')
                         group by lower(btrim(email::text))
                        having count(*) > 1
                      ) repetidos
                    """
                )
                emails_repetidos_na_fila_historico = cur.fetchone()[0]

                cur.execute(
                    """
                    select count(*)
                      from mei_email.lotes
                     where status = 'processando'
                       and iniciado_em < now() - interval '15 minutes'
                    """
                )
                lotes_travados = cur.fetchone()[0]
    except Exception as exc:
        print("EXCHANGE_9950_AUDIT")
        print("NOT_READY")
        print(f"database_audit_failed={type(exc).__name__}:{exc}")
        return 1

    comprometido = submitted_24h + pendentes
    if submitted_24h > settings.meta_envios_por_dia:
        errors.append(f"submitted_24h_acima_meta={submitted_24h}")
    if comprometido > settings.meta_envios_por_dia:
        errors.append(f"fila_compromete_acima_meta={comprometido}")
    if emails_repetidos_na_fila_historico:
        errors.append(f"emails_repetidos_em_envios={emails_repetidos_na_fila_historico}")
    if fila_invalida:
        errors.append(f"fila_contem_destinatarios_nao_elegiveis={fila_invalida}")
    if lotes_travados:
        errors.append(f"lotes_processando_travados={lotes_travados}")

    total_tentados_24h = submitted_24h + falhas_24h + bounces_24h
    failure_rate = (falhas_24h / total_tentados_24h) if total_tentados_24h else 0.0
    if falhas_24h:
        warnings.append(f"falhas_24h={falhas_24h};taxa={failure_rate:.2%}")
        if total_tentados_24h >= 100 and failure_rate >= 0.10:
            errors.append(f"taxa_falha_24h_alta={failure_rate:.2%}")

    restante = max(settings.meta_envios_por_dia - comprometido, 0)
    if elegiveis < restante:
        warnings.append(f"elegiveis_autorizados_insuficientes={elegiveis}/{restante}")

    print("EXCHANGE_9950_AUDIT")
    print(f"provider={settings.email_provider}")
    print(f"sender={sender}")
    print(f"sender_domain={sender_domain}")
    print(f"reply_to={reply_to_address}")
    print(f"terrl_threshold_confirmado={terrl}")
    print(f"rate_limit_por_minuto={settings.rate_limit_envios_por_minuto}")
    print(f"meta_envios_24h={settings.meta_envios_por_dia}")
    print(f"teto_local_24h={settings.max_envios_por_dia}")
    print(f"submitted_ultimas_24h={submitted_24h}")
    print(f"pendentes={pendentes}")
    print(f"comprometido={comprometido}")
    print(f"elegiveis_autorizados={elegiveis}")
    print(f"cancelados_total={cancelados}")
    print(f"suppressed_total={suppressed}")
    print(f"bounces_24h={bounces_24h}")
    print(f"emails_repetidos_em_envios={emails_repetidos_na_fila_historico}")
    print("DNS_AUDIT_BEGIN")
    print(dns_output)
    print("DNS_AUDIT_END")
    print("GRAPH_AUDIT_BEGIN")
    print(graph_output)
    print("GRAPH_AUDIT_END")

    for warning in warnings:
        print(f"WARNING={warning}")
    if errors:
        print("NOT_READY")
        for error in errors:
            print(f"ERROR={error}")
        return 1

    print("READY_FOR_AUTHORIZED_RECIPIENTS_WITHIN_CONFIGURED_LIMITS")
    print("NOTE=Readiness tecnico nao autoriza envio para contatos sem permissao nem elimina bloqueios dinamicos do provedor.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
