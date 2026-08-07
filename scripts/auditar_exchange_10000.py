#!/usr/bin/env python3
"""Auditoria fail-closed para operacao de ate 10.000 destinatarios/24h.

Executar no mesmo ambiente do worker, com o .env e o banco de producao.
O script NAO envia e-mail. Ele valida DNS publico, dominio/remetente, TERRL
informado pelo administrador, limites locais e o estado real da fila/banco.
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


def sender_address() -> str:
    if settings.email_provider in {"microsoft_graph", "microsoft-oauth", "graph"}:
        return os.getenv("MICROSOFT_GRAPH_USER", "").strip()
    if settings.email_provider in {"microsoft", "outlook", "office365"}:
        return os.getenv("MICROSOFT_SMTP_USER", "").strip()
    return ""


def run_dns_audit() -> tuple[bool, str]:
    env = dict(os.environ)
    env["MICROSOFT_SENDER_DOMAIN"] = EXPECTED_DOMAIN
    result = subprocess.run(
        [sys.executable, str(BASE_DIR / "scripts" / "auditar_dns_microsoft.py")],
        cwd=str(BASE_DIR),
        env=env,
        text=True,
        capture_output=True,
        timeout=60,
    )
    output = (result.stdout + "\n" + result.stderr).strip()
    return result.returncode == 0, output


def main() -> int:
    errors: list[str] = []
    warnings: list[str] = []

    if settings.email_provider not in {
        "microsoft_graph", "microsoft-oauth", "graph", "microsoft", "outlook", "office365"
    }:
        errors.append(f"provider_nao_exchange={settings.email_provider}")

    if settings.max_envios_por_dia != 10000:
        errors.append(f"MAX_ENVIOS_POR_DIA_deve_ser_10000={settings.max_envios_por_dia}")
    if settings.rate_limit_envios_por_minuto > 30:
        errors.append(f"rate_limit_acima_exchange={settings.rate_limit_envios_por_minuto}")
    if settings.rate_limit_envios_por_minuto <= 0:
        errors.append("rate_limit_invalido")
    elif settings.rate_limit_envios_por_minuto > 20:
        warnings.append("rate_limit_acima_de_20_min_reduz_margem_para_throttling")

    sender = sender_address()
    if not sender or "@" not in sender:
        errors.append("remetente_microsoft_nao_configurado")
        sender_domain = ""
    else:
        sender_domain = sender.rsplit("@", 1)[1].lower().rstrip(".")
        if sender_domain.endswith(".onmicrosoft.com") or sender_domain == "onmicrosoft.com":
            errors.append("dominio_onmicrosoft_incompativel_com_10000_externos_dia")
        if sender_domain != EXPECTED_DOMAIN:
            errors.append(f"sender_domain_diverge_do_dominio_validado={sender_domain}!={EXPECTED_DOMAIN}")

    mail_from = os.getenv("MAIL_FROM", "").strip()
    _, mail_from_address = parseaddr(mail_from)
    if not mail_from_address:
        warnings.append("MAIL_FROM_nao_configurado")
    elif sender and mail_from_address.casefold() != sender.casefold():
        errors.append(f"MAIL_FROM_diverge_do_usuario_microsoft={mail_from_address}!={sender}")

    unsubscribe = urlsplit(settings.base_url_descadastro)
    if unsubscribe.scheme != "https" or not unsubscribe.netloc:
        errors.append("BASE_URL_DESCADASTRO_deve_ser_https_publico")
    elif unsubscribe.hostname and not unsubscribe.hostname.endswith("shopvivaliz.com.br"):
        errors.append(f"BASE_URL_DESCADASTRO_host_inesperado={unsubscribe.hostname}")

    terrl_raw = os.getenv("MICROSOFT_TERRL_THRESHOLD", "").strip()
    try:
        terrl = int(terrl_raw)
    except ValueError:
        terrl = 0
    if terrl < 10000:
        errors.append(
            "MICROSOFT_TERRL_THRESHOLD_deve_ser_confirmado_no_EAC_e_ser_maior_ou_igual_10000="
            + (terrl_raw or "nao_configurado")
        )

    dns_ok, dns_output = run_dns_audit()
    if not dns_ok:
        errors.append("dns_microsoft_custom_domain_not_ready")

    try:
        with psycopg.connect(settings.database_url) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    select
                      count(*) filter (where status = 'enviado' and enviado_em >= now() - interval '24 hours') as enviados_24h,
                      count(*) filter (where status = 'enviado' and enviado_em >= (now() at time zone 'America/Sao_Paulo')::date) as enviados_hoje,
                      count(*) filter (where status = 'falhou' and criado_em >= now() - interval '24 hours') as falhas_24h,
                      count(*) filter (where status = 'pendente') as pendentes,
                      count(*) filter (where status = 'opt_out') as opt_out,
                      count(*) filter (where status = 'processando') as processando
                    from mei_email.envios
                    """
                )
                enviados_24h, enviados_hoje, falhas_24h, pendentes, opt_out, processando = cur.fetchone()

                cur.execute(
                    """
                    select count(*)
                      from mei_email.lotes
                     where status = 'processando'
                       and iniciado_em < now() - interval '15 minutes'
                    """
                )
                lotes_travados = cur.fetchone()[0]

                cur.execute(
                    """
                    select count(*)
                      from mei_email.empresas
                     where situacao_cadastral = 'ATIVA'
                       and opt_out = false
                       and provavel_terceiro = false
                       and email is not null
                       and enviado = false
                    """
                )
                elegiveis = cur.fetchone()[0]

                cur.execute(
                    """
                    select count(*)
                      from (
                        select lower(trim(email)) as email_normalizado
                          from mei_email.envios
                         where status = 'enviado'
                         group by lower(trim(email))
                        having count(*) > 1
                      ) duplicados
                    """
                )
                emails_enviados_duplicados = cur.fetchone()[0]
    except Exception as exc:
        print("NOT_READY")
        print(f"database_audit_failed={type(exc).__name__}:{exc}")
        return 1

    if enviados_24h > 10000:
        errors.append(f"envios_24h_acima_limite={enviados_24h}")
    if emails_enviados_duplicados:
        errors.append(f"emails_com_envio_duplicado={emails_enviados_duplicados}")
    if lotes_travados:
        errors.append(f"lotes_processando_travados={lotes_travados}")
    if falhas_24h:
        total_tentados_24h = enviados_24h + falhas_24h
        failure_rate = (falhas_24h / total_tentados_24h) if total_tentados_24h else 0.0
        warnings.append(f"falhas_24h={falhas_24h};taxa={failure_rate:.2%}")
        if total_tentados_24h >= 100 and failure_rate >= 0.10:
            errors.append(f"taxa_falha_24h_alta={failure_rate:.2%}")
    else:
        failure_rate = 0.0

    comprometido = enviados_24h + pendentes + processando
    if comprometido > settings.max_envios_por_dia:
        warnings.append(
            f"fila_comprometida_acima_da_capacidade_24h={comprometido};worker_pausara_no_teto"
        )
    capacidade_restante = max(settings.max_envios_por_dia - enviados_24h, 0)
    if elegiveis < capacidade_restante:
        warnings.append(
            f"elegiveis_insuficientes_para_preencher_capacidade_restante={elegiveis}/{capacidade_restante}"
        )

    print("EXCHANGE_10000_AUDIT")
    print(f"provider={settings.email_provider}")
    print(f"sender={sender}")
    print(f"sender_domain={sender_domain}")
    print(f"expected_domain={EXPECTED_DOMAIN}")
    print(f"mail_from={mail_from}")
    print(f"terrl_threshold_confirmado={terrl}")
    print(f"rate_limit_por_minuto={settings.rate_limit_envios_por_minuto}")
    print(f"max_envios_24h={settings.max_envios_por_dia}")
    print(f"enviados_ultimas_24h={enviados_24h}")
    print(f"enviados_hoje={enviados_hoje}")
    print(f"falhas_ultimas_24h={falhas_24h}")
    print(f"taxa_falha_24h={failure_rate:.2%}")
    print(f"pendentes={pendentes}")
    print(f"processando={processando}")
    print(f"lotes_travados={lotes_travados}")
    print(f"opt_out_total={opt_out}")
    print(f"elegiveis_nao_contatados={elegiveis}")
    print(f"emails_enviados_duplicados={emails_enviados_duplicados}")
    print(f"meta_10000_atingida={'sim' if enviados_24h == 10000 else 'nao'}")
    print("DNS_AUDIT_BEGIN")
    print(dns_output)
    print("DNS_AUDIT_END")

    for warning in warnings:
        print(f"WARNING={warning}")

    if errors:
        print("NOT_READY")
        for error in errors:
            print(f"ERROR={error}")
        return 1

    print("READY_WITHIN_EXCHANGE_SERVICE_LIMITS")
    print("NOTE=Limites e autenticacao corretos nao eliminam TERRL dinamico, politica antispam ou reputacao do destinatario.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
