from __future__ import annotations

import logging
import math
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import psycopg
from psycopg.rows import dict_row

from app.config import settings

logger = logging.getLogger("mei_mg_email.queue")
CAMPAIGN_ENQUEUE_ADVISORY_LOCK_ID = 99502026
TEMPLATE_PATH = (
    Path(__file__).resolve().parent.parent
    / "templates"
    / "mei-contabilidade-melo.html"
)
AUTOQUEUE_SUBJECT = "Contabilidade Melo para MEI: plano mensal e suporte fiscal"
AUTOQUEUE_LOT_SIZE = 100
AUTOQUEUE_REFILL_BATCH_SIZE = 5000
AUTOQUEUE_CANDIDATE_OVERSAMPLE = 4
AUTOQUEUE_CANDIDATE_MIN_EXTRA = 2000
OPEN_ENVIO_STATUSES = ("pendente", "enviando", "pending", "processing")


def carregar_template_html() -> str:
    template = TEMPLATE_PATH.read_text(encoding="utf-8")
    lower = template.casefold()
    required = (
        "<html",
        "{{unsubscribe_url}}",
        "{{nome_fantasia}}",
        "logo-contabilidade-melo-transparente.png",
    )
    missing = [token for token in required if token.casefold() not in lower]
    if missing:
        raise RuntimeError(
            f"template HTML incompleto; faltando={','.join(missing)}"
        )
    return template


def validar_config_fila() -> None:
    if settings.queue_min_pending < 1:
        raise RuntimeError("QUEUE_MIN_PENDING precisa ser pelo menos 1.")
    if settings.queue_target_pending <= settings.queue_min_pending:
        raise RuntimeError(
            "QUEUE_TARGET_PENDING precisa ser maior que QUEUE_MIN_PENDING."
        )


def quantidade_para_repor(pendentes: int) -> int:
    validar_config_fila()
    if pendentes > settings.queue_min_pending:
        return 0
    return min(
        max(settings.queue_target_pending - pendentes, 0),
        AUTOQUEUE_REFILL_BATCH_SIZE,
    )


def contar_pendentes(conn: psycopg.Connection) -> int:
    """Count actual open recipient rows, not declared lot sizes."""
    with conn.cursor() as cur:
        cur.execute(
            """
            select count(*)
              from mei_email.envios
             where status in ('pendente', 'enviando', 'pending', 'processing')
            """
        )
        return int(cur.fetchone()[0] or 0)


def repor_fila_automatica(conn: psycopg.Connection) -> int:
    """Replenish a bounded queue without consuming the rolling send quota."""
    validar_config_fila()
    template = carregar_template_html()

    with conn.cursor() as lock_cur:
        lock_cur.execute(
            "select pg_try_advisory_xact_lock(%s)",
            (CAMPAIGN_ENQUEUE_ADVISORY_LOCK_ID,),
        )
        lock_row = lock_cur.fetchone()
        if lock_row is None or not bool(lock_row[0]):
            conn.commit()
            logger.warning("AUTOQUEUE_SKIPPED another replenisher owns the lock")
            return 0

    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            select count(*) as pendentes
              from mei_email.envios
             where status in ('pendente', 'enviando', 'pending', 'processing')
            """
        )
        pendentes_antes = int(cur.fetchone()["pendentes"] or 0)
        quantidade = quantidade_para_repor(pendentes_antes)
        if quantidade <= 0:
            conn.commit()
            return 0

        candidate_limit = max(
            quantidade * AUTOQUEUE_CANDIDATE_OVERSAMPLE,
            quantidade + AUTOQUEUE_CANDIDATE_MIN_EXTRA,
        )

        # Fail closed before the first LIMIT: only independently authorized,
        # independently verified MEI/MG recipients are allowed into the bounded
        # candidate pool. Known operator/synthesized origins are rejected even
        # if production Flyway helper functions are temporarily behind main.
        cur.execute(
            """
            with base as materialized (
                select e.cnpj, e.email, e.data_abertura
                  from mei_email.empresas e
                 where e.tipo_regime = 'MEI'
                   and e.uf = 'MG'
                   and e.situacao_cadastral = 'ATIVA'
                   and e.opt_out = false
                   and e.provavel_terceiro = false
                   and e.email is not null
                   and e.enviado = false
                   and mei_email.is_independent_marketing_authorization(
                       e.marketing_autorizado, e.marketing_autorizado_origem
                   )
                   and btrim(coalesce(e.marketing_autorizado_origem, '')) not in (
                       'confirmacao_operador_2026-08-12',
                       'confirmacao_operador_2026-08-13',
                       'politica_importacao_operador_2026-08-13',
                       'user_explicit_authorization_2026-08-20'
                   )
                   and lower(btrim(coalesce(e.marketing_autorizado_origem, '')))
                       not like '%%operator_authorization_true%%'
                   and mei_email.is_independent_mei_verification(
                       e.mei_verificado, e.mei_verificado_origem
                   )
                   and btrim(coalesce(e.mei_verificado_origem, '')) not in (
                       'override_operador_2026-08-13',
                       'politica_importacao_operador_2026-08-13'
                   )
                   and not exists (
                       select 1
                         from mei_email.envios x
                        where x.cnpj = e.cnpj
                          and x.status in (
                              'pendente', 'enviando', 'pending', 'processing',
                              'submitted', 'enviado', 'delivered', 'bounced'
                          )
                   )
                   and not exists (
                       select 1
                         from mei_email.envios x
                        where lower(btrim(x.email::text)) =
                              lower(btrim(e.email::text))
                          and x.status in (
                              'pendente', 'enviando', 'pending', 'processing',
                              'submitted', 'enviado', 'delivered', 'bounced'
                          )
                   )
                 order by e.cnpj
                 limit %s
            ),
            preselecionadas as (
                select b.cnpj, b.email, b.data_abertura
                  from base b
                 where btrim(b.email::text) <> ''
                   and mei_email.is_valid_email_address(b.email)
                   and not mei_email.is_email_suppressed(b.email)
                   and not mei_email.is_cnpj_suppressed(b.cnpj::text)
                   and not exists (
                       select 1
                         from mei_email.envios x
                        where x.cnpj = b.cnpj
                          and x.status in (
                              'pendente', 'enviando', 'pending', 'processing',
                              'submitted', 'enviado', 'delivered', 'bounced'
                          )
                   )
                   and not exists (
                       select 1
                         from mei_email.envios x
                        where lower(btrim(x.email::text)) =
                              lower(btrim(b.email::text))
                          and x.status in (
                              'pendente', 'enviando', 'pending', 'processing',
                              'submitted', 'enviado', 'delivered', 'bounced'
                          )
                   )
            ),
            candidatas as (
                select cnpj, email, data_abertura,
                       row_number() over (
                           partition by lower(btrim(email::text))
                           order by data_abertura desc nulls last, cnpj
                       ) as posicao_do_email
                  from preselecionadas
            )
            select cnpj, email
              from candidatas
             where posicao_do_email = 1
             order by data_abertura desc nulls last, cnpj
             limit %s
            """,
            (candidate_limit, quantidade),
        )
        empresas = cur.fetchall()

        if not empresas:
            conn.commit()
            level = logging.CRITICAL if pendentes_antes == 0 else logging.WARNING
            logger.log(
                level,
                "Autoqueue sem candidatos elegiveis. pendentes=%d min=%d target=%d",
                pendentes_antes,
                settings.queue_min_pending,
                settings.queue_target_pending,
            )
            return 0

        agora_sp = datetime.now(ZoneInfo("America/Sao_Paulo"))
        cur.execute(
            """
            insert into mei_email.campanhas
                (nome, assunto, corpo_template, filtro_tipo_regime, filtro_uf,
                 tamanho_lote, status, total_empresas)
            values (%s, %s, %s, 'MEI', 'MG', %s, 'enfileirada', %s)
            returning id
            """,
            (
                f"MEI MG Autoqueue {agora_sp:%Y-%m-%d %H:%M:%S}",
                AUTOQUEUE_SUBJECT,
                template,
                AUTOQUEUE_LOT_SIZE,
                len(empresas),
            ),
        )
        campanha_id = cur.fetchone()["id"]

        total_lotes = math.ceil(len(empresas) / AUTOQUEUE_LOT_SIZE)
        for numero in range(total_lotes):
            fatia = empresas[
                numero * AUTOQUEUE_LOT_SIZE : (numero + 1) * AUTOQUEUE_LOT_SIZE
            ]
            cur.execute(
                """
                insert into mei_email.lotes
                    (campanha_id, numero, status, tamanho)
                values (%s, %s, 'pendente', %s)
                returning id
                """,
                (campanha_id, numero, len(fatia)),
            )
            lote_id = cur.fetchone()["id"]
            cur.executemany(
                """
                insert into mei_email.envios
                    (campanha_id, lote_id, cnpj, email, status)
                values (%s, %s, %s, %s, 'pendente')
                """,
                [
                    (
                        campanha_id,
                        lote_id,
                        empresa["cnpj"],
                        empresa["email"],
                    )
                    for empresa in fatia
                ],
            )

    conn.commit()
    pendentes_depois = pendentes_antes + len(empresas)
    logger.warning(
        "AUTOQUEUE_REPOSTA campanha=%s antes=%d adicionados=%d depois=%d target=%d",
        campanha_id,
        pendentes_antes,
        len(empresas),
        pendentes_depois,
        settings.queue_target_pending,
    )
    return len(empresas)
