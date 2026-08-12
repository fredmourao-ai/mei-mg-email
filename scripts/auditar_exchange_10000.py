#!/usr/bin/env python3
"""Auditoria fail-closed para a meta operacional de 9.950 destinatarios/24h.

Executar no mesmo ambiente do worker, com o .env e banco de producao. O script
NAO envia e-mail. Valida DNS, autenticacao Microsoft Graph app-only, remetente,
TERRL derivado das assinaturas Microsoft, template HTML, seguranca da fila e o
buffer continuo. A fila pendente e deliberadamente separada da cota de envio.
"""
from __future__ import annotations

import json
import math
import os
import subprocess
import sys
from email.utils import parseaddr
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

import psycopg

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from app.config import settings
from app.email_provider import MicrosoftGraphEmailProvider

EXPECTED_DOMAIN = os.getenv("MICROSOFT_SENDER_DOMAIN", "dev.shopvivaliz.com.br").strip().lower().rstrip(".")
EXPECTED_SENDER = "naoresponda@dev.shopvivaliz.com.br"
TEMPLATE_PATH = BASE_DIR / "templates" / "mei-contabilidade-melo.html"
GRAPH_PROVIDERS = {"microsoft_graph", "microsoft-oauth", "graph"}


def sender_address() -> str:
    if settings.email_provider in GRAPH_PROVIDERS:
        return os.getenv("MICROSOFT_GRAPH_USER", "").strip()
    return ""


def run_script(name: str) -> tuple[bool, str]:
    result = subprocess.run(
        [sys.executable, str(BASE_DIR / "scripts" / name)],
        cwd=str(BASE_DIR),
        env=dict(os.environ),
        text=True,
        capture_output=True,
        timeout=90,
    )
    return result.returncode == 0, (result.stdout + "\n" + result.stderr).strip()


def _is_email_service_plan(name: str, status: str) -> bool:
    low = name.casefold()
    return (
        ("exchange" in low or low.startswith("eop_") or "exchangearchive" in low)
        and status.casefold() not in {"disabled", "deleted"}
    )


def derive_terrl_from_microsoft_subscriptions() -> tuple[int, int, int, str]:
    """Derive TERRL using Microsoft's published formula and Graph subscription facts.

    Trial email licenses are excluded from the paid-license formula. If the tenant
    has no non-trial email license but has trial email licenses, the trial cap is
    5,000. Returns threshold, non-trial count, trial count and source marker.
    """
    provider = MicrosoftGraphEmailProvider()
    token = provider._get_access_token()
    req = Request(
        "https://graph.microsoft.com/v1.0/directory/subscriptions",
        headers={"Authorization": "Bearer " + token, "Accept": "application/json"},
    )
    with urlopen(req, timeout=30) as response:
        subscriptions = json.loads(response.read().decode("utf-8")).get("value", [])

    nontrial = 0
    trial = 0
    for sub in subscriptions:
        has_email = any(
            _is_email_service_plan(
                str(plan.get("servicePlanName") or ""),
                str(plan.get("provisioningStatus") or ""),
            )
            for plan in (sub.get("serviceStatus") or [])
        )
        if not has_email:
            continue
        total = int(sub.get("totalLicenses") or 0)
        status = str(sub.get("status") or "").casefold()
        if status not in {"enabled", "warning"}:
            continue
        if bool(sub.get("isTrial")):
            trial += total
        else:
            nontrial += total

    if nontrial > 0:
        threshold = math.floor(500 * (nontrial**0.7) + 9500)
        source = "microsoft_graph_company_subscriptions_nontrial_formula"
    elif trial > 0:
        threshold = 5000
        source = "microsoft_trial_tenant_cap"
    else:
        threshold = 0
        source = "no_exchange_or_eop_subscription_found"
    return threshold, nontrial, trial, source


def main() -> int:
    errors: list[str] = []
    warnings: list[str] = []

    if settings.email_provider not in GRAPH_PROVIDERS:
        errors.append(f"provider_nao_microsoft_graph={settings.email_provider}")

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
    if settings.queue_min_pending < 1:
        errors.append(f"QUEUE_MIN_PENDING_invalido={settings.queue_min_pending}")
    if settings.queue_target_pending <= settings.queue_min_pending:
        errors.append(
            f"QUEUE_TARGET_PENDING_deve_ser_maior_que_min={settings.queue_target_pending}/{settings.queue_min_pending}"
        )

    sender = sender_address()
    if not sender or "@" not in sender:
        errors.append("remetente_microsoft_nao_configurado")
        sender_domain = ""
    else:
        sender_domain = sender.rsplit("@", 1)[1].lower().rstrip(".")
        if sender.casefold() != EXPECTED_SENDER.casefold():
            errors.append(f"sender_diverge={sender}!={EXPECTED_SENDER}")
        if sender_domain.endswith(".onmicrosoft.com") or sender_domain == "onmicrosoft.com":
            errors.append("dominio_onmicrosoft_nao_permitido_para_esta_operacao")
        if sender_domain != EXPECTED_DOMAIN:
            errors.append(f"sender_domain_diverge={sender_domain}!={EXPECTED_DOMAIN}")

    mail_from = os.getenv("MAIL_FROM", "").strip()
    _, mail_from_address = parseaddr(mail_from)
    if not mail_from_address:
        errors.append("MAIL_FROM_nao_configurado")
    elif sender and mail_from_address.casefold() != sender.casefold():
        errors.append(f"MAIL_FROM_diverge_do_usuario_microsoft={mail_from_address}!={sender}")

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

    terrl = 0
    terrl_nontrial_licenses = 0
    terrl_trial_licenses = 0
    terrl_source = "unavailable"
    try:
        terrl, terrl_nontrial_licenses, terrl_trial_licenses, terrl_source = derive_terrl_from_microsoft_subscriptions()
    except Exception as exc:
        errors.append(f"terrl_subscription_derivation_failed={type(exc).__name__}:{exc}")

    configured_terrl_raw = os.getenv("MICROSOFT_TERRL_THRESHOLD", "").strip()
    if configured_terrl_raw:
        try:
            configured_terrl = int(configured_terrl_raw)
            if terrl and configured_terrl != terrl:
                warnings.append(f"MICROSOFT_TERRL_THRESHOLD_env_diverge_formula={configured_terrl}/{terrl}")
        except ValueError:
            warnings.append(f"MICROSOFT_TERRL_THRESHOLD_env_invalido={configured_terrl_raw}")

    if terrl < settings.meta_envios_por_dia:
        errors.append(f"TERRL_insuficiente_para_meta={terrl}/{settings.meta_envios_por_dia}")
    elif terrl - settings.meta_envios_por_dia < 50:
        warnings.append(f"margem_TERRL_menor_que_50={terrl - settings.meta_envios_por_dia}")

    dns_ok, dns_output = run_script("auditar_dns_microsoft.py")
    if not dns_ok:
        errors.append("dns_microsoft_custom_domain_not_ready")

    graph_output = "not_applicable"
    if settings.email_provider in GRAPH_PROVIDERS:
        graph_ok, graph_output = run_script("auditar_graph_token.py")
        if not graph_ok:
            errors.append("graph_app_only_not_ready")

    try:
        with psycopg.connect(settings.database_url) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    select
                      count(*) filter (
                        where status::text in ('submitted','enviado')
                          and enviado_em >= now() - interval '24 hours'
                      ) as consumidos_24h,
                      count(*) filter (where status::text in ('pendente','enviando')) as pendentes,
                      count(*) filter (where status::text = 'falhou' and criado_em >= now() - interval '24 hours') as falhas_24h,
                      count(*) filter (where status::text = 'sender_blocked' and criado_em >= now() - interval '24 hours') as sender_blocked_24h,
                      count(*) filter (where status::text = 'bloqueado') as bloqueados,
                      count(*) filter (where status::text = 'opt_out') as opt_out
                    from mei_email.envios
                    """
                )
                consumidos_24h, pendentes, falhas_24h, sender_blocked_24h, bloqueados, opt_out = cur.fetchone()

                cur.execute("select count(*) from mei_email.vw_empresas_elegiveis")
                elegiveis = cur.fetchone()[0]

                cur.execute(
                    """
                    select count(*)
                      from mei_email.envios e
                      join mei_email.empresas emp on emp.cnpj = e.cnpj
                     where e.status::text in ('pendente','enviando')
                       and (
                         emp.situacao_cadastral <> 'ATIVA'
                         or emp.opt_out
                         or emp.provavel_terceiro
                         or not emp.marketing_autorizado
                       )
                    """
                )
                fila_invalida = cur.fetchone()[0]

                cur.execute(
                    """
                    select count(*)
                      from (
                        select lower(btrim(email::text)) as email_normalizado
                          from mei_email.envios
                         where status::text in ('pendente','enviando')
                         group by lower(btrim(email::text))
                        having count(*) > 1
                      ) repetidos
                    """
                )
                duplicados_na_fila_atual = cur.fetchone()[0]

                cur.execute(
                    """
                    select count(*)
                      from mei_email.envios p
                     where p.status::text in ('pendente','enviando')
                       and exists (
                         select 1
                           from mei_email.envios s
                          where s.id <> p.id
                            and s.status::text in ('submitted','enviado')
                            and lower(btrim(s.email::text)) = lower(btrim(p.email::text))
                       )
                    """
                )
                pendentes_ja_submetidos = cur.fetchone()[0]

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
                      from pg_stat_activity
                     where datname = current_database()
                       and state = 'idle in transaction'
                       and query ilike '%from mei_email.lotes%'
                       and query ilike '%for update skip locked%'
                    """
                )
                workers_idle_transaction = cur.fetchone()[0]
    except Exception as exc:
        print("EXCHANGE_9950_AUDIT")
        print("NOT_READY")
        print(f"database_audit_failed={type(exc).__name__}:{exc}")
        return 1

    if consumidos_24h > settings.meta_envios_por_dia:
        errors.append(f"consumidos_24h_acima_meta={consumidos_24h}")
    if pendentes == 0:
        warnings.append("fila_zerada_autoqueue_deve_repor_imediatamente")
    elif pendentes <= settings.queue_min_pending:
        warnings.append(
            f"fila_no_gatilho_de_reposicao={pendentes}/{settings.queue_min_pending}"
        )
    if pendentes > settings.queue_target_pending:
        warnings.append(
            f"fila_acima_target_legado_ou_manual={pendentes}/{settings.queue_target_pending}"
        )
    if duplicados_na_fila_atual:
        errors.append(f"emails_duplicados_na_fila_atual={duplicados_na_fila_atual}")
    if pendentes_ja_submetidos:
        errors.append(f"pendentes_ja_submitted_ou_enviados={pendentes_ja_submetidos}")
    if fila_invalida:
        errors.append(f"fila_contem_destinatarios_nao_elegiveis={fila_invalida}")
    if lotes_travados:
        errors.append(f"lotes_processando_travados={lotes_travados}")
    if workers_idle_transaction:
        errors.append(f"worker_idle_in_transaction={workers_idle_transaction}")
    if sender_blocked_24h:
        errors.append(f"sender_blocked_24h={sender_blocked_24h}")

    total_falhas_24h = falhas_24h + sender_blocked_24h
    total_tentados_24h = consumidos_24h + total_falhas_24h
    failure_rate = (total_falhas_24h / total_tentados_24h) if total_tentados_24h else 0.0
    if total_falhas_24h:
        warnings.append(f"falhas_24h={total_falhas_24h};taxa={failure_rate:.2%}")
        if total_tentados_24h >= 100 and failure_rate >= 0.10:
            errors.append(f"taxa_falha_24h_alta={failure_rate:.2%}")

    necessario_para_target = max(settings.queue_target_pending - pendentes, 0)
    if elegiveis < necessario_para_target:
        warnings.append(
            f"elegiveis_autorizados_insuficientes_para_target={elegiveis}/{necessario_para_target}"
        )

    print("EXCHANGE_9950_AUDIT")
    print(f"provider={settings.email_provider}")
    print(f"sender={sender}")
    print(f"sender_domain={sender_domain}")
    print(f"terrl_threshold_derivado={terrl}")
    print(f"terrl_source={terrl_source}")
    print(f"terrl_nontrial_email_licenses={terrl_nontrial_licenses}")
    print(f"terrl_trial_email_licenses_excluded={terrl_trial_licenses}")
    print(f"rate_limit_por_minuto={settings.rate_limit_envios_por_minuto}")
    print(f"meta_envios_24h={settings.meta_envios_por_dia}")
    print(f"teto_local_24h={settings.max_envios_por_dia}")
    print(f"submitted_ou_enviados_ultimas_24h={consumidos_24h}")
    print(f"pendentes={pendentes}")
    print(f"queue_min_pending={settings.queue_min_pending}")
    print(f"queue_target_pending={settings.queue_target_pending}")
    print(f"elegiveis_autorizados={elegiveis}")
    print(f"bloqueados_total={bloqueados}")
    print(f"opt_out_total={opt_out}")
    print(f"duplicados_na_fila_atual={duplicados_na_fila_atual}")
    print(f"pendentes_ja_submitted_ou_enviados={pendentes_ja_submetidos}")
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
    print("NOTE=A fila pendente e um buffer continuo e nao e somada a cota de envio; o worker valida 9.950/24h antes de cada submissao.")
    print("NOTE=TERRL quota is derived from Microsoft company subscription data and the published formula; direct tenant ObservedValue still requires the Exchange Online TERRL report/cmdlet.")
    print("NOTE=Readiness tecnico nao autoriza envio para contatos sem permissao nem elimina bloqueios dinamicos do provedor.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
