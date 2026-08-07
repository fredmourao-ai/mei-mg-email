#!/usr/bin/env python3
"""Auditoria fail-closed para operacao de ate 10.000 destinatarios/24h.

Executar no mesmo ambiente do worker, com o .env e o banco de producao.
O script NAO envia e-mail. Ele valida configuracao local e mede o que o
sistema registrou como enviado nas ultimas 24 horas.
"""
from __future__ import annotations

import os
import sys
from urllib.parse import urlsplit

import psycopg

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from app.config import settings


def sender_address() -> str:
    if settings.email_provider in {"microsoft_graph", "microsoft-oauth", "graph"}:
        return os.getenv("MICROSOFT_GRAPH_USER", "").strip()
    if settings.email_provider in {"microsoft", "outlook", "office365"}:
        return os.getenv("MICROSOFT_SMTP_USER", "").strip()
    return ""


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
    elif sender.lower().endswith(".onmicrosoft.com"):
        errors.append("dominio_onmicrosoft_incompativel_com_10000_externos_dia")

    unsubscribe = urlsplit(settings.base_url_descadastro)
    if unsubscribe.scheme != "https" or not unsubscribe.netloc:
        errors.append("BASE_URL_DESCADASTRO_deve_ser_https_publico")

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
                      count(*) filter (where status = 'opt_out') as opt_out
                    from mei_email.envios
                    """
                )
                enviados_24h, enviados_hoje, falhas_24h, pendentes, opt_out = cur.fetchone()

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
    except Exception as exc:
        print("NOT_READY")
        print(f"database_audit_failed={type(exc).__name__}:{exc}")
        return 1

    if enviados_24h > 10000:
        errors.append(f"envios_24h_acima_limite={enviados_24h}")
    if falhas_24h:
        warnings.append(f"falhas_24h={falhas_24h}")
    if elegiveis < 10000 and enviados_24h < 10000:
        warnings.append(f"elegiveis_insuficientes_para_atingir_10000={elegiveis}")

    print("EXCHANGE_10000_AUDIT")
    print(f"provider={settings.email_provider}")
    print(f"sender={sender}")
    print(f"rate_limit_por_minuto={settings.rate_limit_envios_por_minuto}")
    print(f"max_envios_24h={settings.max_envios_por_dia}")
    print(f"enviados_ultimas_24h={enviados_24h}")
    print(f"enviados_hoje={enviados_hoje}")
    print(f"falhas_ultimas_24h={falhas_24h}")
    print(f"pendentes={pendentes}")
    print(f"opt_out_total={opt_out}")
    print(f"elegiveis_nao_contatados={elegiveis}")
    print(f"meta_10000_atingida={'sim' if enviados_24h == 10000 else 'nao'}")

    for warning in warnings:
        print(f"WARNING={warning}")

    if errors:
        print("NOT_READY")
        for error in errors:
            print(f"ERROR={error}")
        return 1

    print("READY_WITHIN_EXCHANGE_SERVICE_LIMITS")
    print("NOTE=Exchange Online ainda pode aplicar anti-spam/TERRL; nao ha bypass de limite pelo aplicativo.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
