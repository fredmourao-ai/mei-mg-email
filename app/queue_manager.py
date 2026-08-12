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
TEMPLATE_PATH = Path(__file__).resolve().parent.parent / "templates" / "mei-contabilidade-melo.html"
AUTOQUEUE_SUBJECT = "Aviso Importante para MEI - Regularizacao Fiscal"
AUTOQUEUE_LOT_SIZE = 100


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
        raise RuntimeError(f"template HTML incompleto; faltando={','.join(missing)}")
    return template


def validar_config_fila() -> None:
    if settings.queue_min_pending < 1:
        raise RuntimeError("QUEUE_MIN_PENDING precisa ser pelo menos 1.")
    if settings.queue_target_pending <= settings.queue_min_pending:
        raise RuntimeError("QUEUE_TARGET_PENDING precisa ser maior que QUEUE_MIN_PENDING.")


def quantidade_para_repor(pendentes: int) -> int:
    validar_config_fila()
    if pendentes > settings.queue_min_pending:
        return 0
    return max(settings.queue_target_pending - pendentes, 0)


def contar_pendentes(conn: psycopg.Connection) -> int:
    with conn.cursor() as cur:
        cur.execute(
            """
            select count(*)
              from mei_email.envios
             where status::text in ('pendente', 'enviando')
            """
        )
        return int(cur.fetchone()[0] or 0)


def repor_fila_automatica(conn: psycopg.Connection) -> int:
    """Mantem estoque de fila sem consumir a cota movel antes do envio.

    A fila e deliberadamente separada da cota de 9.950/24h. Enfileirar nao envia.
    O worker continua sendo a trava final e consulta a janela movel antes de cada
    submissao ao Microsoft Graph.
    """
    validar_config_fila()
    template = carregar_template_html()

    with conn.cursor(row_factory=dict_row) as cur:
        # Usa a mesma trava transacional da criacao manual de campanhas para
        # impedir que dois enfileiradores selecionem os mesmos destinatarios.
        cur.execute(
            "select pg_advisory_xact_lock(%s)",
            (CAMPAIGN_ENQUEUE_ADVISORY_LOCK_ID,),
        )
        cur.execute(
            """
            select count(*) as pendentes
              from mei_email.envios
             where status::text in ('pendente', 'enviando')
            """
        )
        pendentes_antes = int(cur.fetchone()["pendentes"] or 0)
        quantidade = quantidade_para_repor(pendentes_antes)
        if quantidade <= 0:
            conn.commit()
            return 0

        cur.execute(
            """
            with candidatas as (
                select cnpj, email, data_abertura,
                       row_number() over (
                           partition by lower(btrim(email::text))
                           order by data_abertura desc nulls last, cnpj
                       ) as posicao_do_email
                  from mei_email.vw_empresas_elegiveis
                 where tipo_regime = 'MEI'
                   and uf = 'MG'
            )
            select cnpj, email
              from candidatas
             where posicao_do_email = 1
             order by data_abertura desc nulls last, cnpj
             limit %s
            """,
            (quantidade,),
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
                    (campanha_id, lote_id, empresa["cnpj"], empresa["email"])
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
