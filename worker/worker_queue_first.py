"""Worker operacional que prioriza a fila existente antes de repor autoqueue.

Evita que uma consulta de reposicao lenta bloqueie milhares de envios ja
prontos. A reposicao so ocorre quando nao existe lote pendente. Enderecos com
sintaxe invalida sao suprimidos e removidos antes de qualquer chamada ao Graph.
Todas as travas de seguranca, cota movel, sender_blocked e processamento
permanecem nas funcoes do worker principal.
"""
from __future__ import annotations

import time

import psycopg
from psycopg.rows import dict_row

from app.config import settings
from app.email_provider import get_email_provider
from app.queue_manager import repor_fila_automatica
import worker.worker as base_worker
from worker.worker import (
    WORKER_ADVISORY_LOCK_ID,
    SENDER_BLOCK_SENTINEL,
    _sender_blocked_pause_ativo,
    logger,
    pegar_proximo_lote,
    processar_lote,
    recuperar_lotes_travados,
)


def _tabela_cota_externa_existe(conn: psycopg.Connection) -> bool:
    with conn.cursor() as cur:
        cur.execute("select to_regclass('mei_email.envios_externos_cota')")
        return cur.fetchone()[0] is not None


def _obter_envios_ultimas_24h_indexado(conn: psycopg.Connection) -> int:
    """Conta a janela movel pelo indice parcial V030 e pelo ledger externo.

    O ledger externo cobre envios comprovados no Outlook/Graph que nao foram
    criados pelo worker, mas consomem a mesma reputacao/cota do remetente.
    """
    with conn.cursor() as cur:
        cur.execute(
            """
            select count(*)
              from mei_email.envios
             where status in ('submitted', 'enviado')
               and enviado_em >= now() - interval '24 hours'
            """
        )
        total = int(cur.fetchone()[0] or 0)

        if _tabela_cota_externa_existe(conn):
            cur.execute(
                """
                select count(*)
                  from mei_email.envios_externos_cota
                 where sent_at >= now() - interval '24 hours'
                """
            )
            total += int(cur.fetchone()[0] or 0)
        return total


def _ja_submetido_ou_entregue_indexado(
    conn: psycopg.Connection, envio_id, email: str
) -> bool:
    """Consulta primeiro a supressao compacta e cai para os indices de email."""
    with conn.cursor() as cur:
        cur.execute(
            "select mei_email.is_email_suppressed(%s::citext)",
            (email,),
        )
        if bool(cur.fetchone()[0]):
            return True
        cur.execute(
            """
            select 1
              from mei_email.envios
             where id <> %s
               and status in ('submitted', 'enviado')
               and lower(btrim(email::text)) = lower(btrim(%s))
             limit 1
            """,
            (envio_id, email),
        )
        if cur.fetchone() is not None:
            return True

        if _tabela_cota_externa_existe(conn):
            cur.execute(
                """
                select 1
                  from mei_email.envios_externos_cota
                 where lower(btrim(email::text)) = lower(btrim(%s))
                 limit 1
                """,
                (email,),
            )
            if cur.fetchone() is not None:
                return True
        return False


# processar_lote e uma funcao do modulo worker.worker. Substituir estes dois
# globals mantem toda a logica de seguranca original, mas usa os caminhos
# indexados quando a funcao roda.
base_worker.obter_envios_ultimas_24h = _obter_envios_ultimas_24h_indexado
base_worker._ja_submetido_ou_entregue = _ja_submetido_ou_entregue_indexado


def _purgar_invalidos_do_lote(conn: psycopg.Connection, lote_id) -> int:
    """Suprime e remove destinatarios invalidos do lote sem chamar o Graph."""
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            select distinct e.cnpj, e.email
              from mei_email.envios e
             where e.lote_id = %s
               and e.status = 'pendente'
               and not mei_email.is_valid_email_address(e.email)
             order by e.cnpj
            """,
            (lote_id,),
        )
        invalidos = cur.fetchall()

    for item in invalidos:
        with conn.cursor() as cur:
            cur.execute(
                """
                select mei_email.register_operational_suppression(
                    %s, %s, 'filter_email_invalid', 'worker_invalid_guard', null, now()
                )
                """,
                (item["cnpj"], item["email"]),
            )
            cur.execute(
                "delete from mei_email.envios where cnpj = %s",
                (item["cnpj"],),
            )
            cur.execute(
                "delete from mei_email.empresas where cnpj = %s",
                (item["cnpj"],),
            )
        conn.commit()

    if invalidos:
        logger.warning(
            "Lote %s: %d destinatarios com email invalido suprimidos e removidos antes do Graph.",
            lote_id,
            len(invalidos),
        )
    return len(invalidos)


def run() -> None:
    if settings.max_envios_por_dia > 10000:
        raise RuntimeError("MAX_ENVIOS_POR_DIA nao pode ultrapassar 10000 para Exchange Online.")
    if settings.meta_envios_por_dia <= 0:
        raise RuntimeError("META_ENVIOS_POR_DIA precisa ser maior que zero.")
    if settings.meta_envios_por_dia > settings.max_envios_por_dia:
        raise RuntimeError("META_ENVIOS_POR_DIA nao pode ultrapassar MAX_ENVIOS_POR_DIA.")
    if settings.rate_limit_envios_por_minuto > 30:
        raise RuntimeError("RATE_LIMIT_ENVIOS_POR_MINUTO nao pode ultrapassar 30 no Exchange Online.")
    if settings.rate_limit_envios_por_minuto <= 0:
        raise RuntimeError("RATE_LIMIT_ENVIOS_POR_MINUTO precisa ser maior que zero.")
    if settings.queue_min_pending < 1:
        raise RuntimeError("QUEUE_MIN_PENDING precisa ser pelo menos 1.")
    if settings.queue_target_pending <= settings.queue_min_pending:
        raise RuntimeError("QUEUE_TARGET_PENDING precisa ser maior que QUEUE_MIN_PENDING.")

    provider = get_email_provider(settings.email_provider)
    logger.info(
        "Worker queue-first iniciado. provedor=%s rate_limit=%d/min meta_24h=%d teto_24h=%d poll=%ds fila_min=%d fila_target=%d",
        settings.email_provider,
        settings.rate_limit_envios_por_minuto,
        settings.meta_envios_por_dia,
        settings.max_envios_por_dia,
        settings.worker_poll_interval_segundos,
        settings.queue_min_pending,
        settings.queue_target_pending,
    )

    with psycopg.connect(settings.database_url) as conn:
        with conn.cursor() as cur:
            cur.execute("select pg_try_advisory_lock(%s)", (WORKER_ADVISORY_LOCK_ID,))
            if not cur.fetchone()[0]:
                raise RuntimeError(
                    "Ja existe outro worker de disparo ativo. Mantendo instancia unica para respeitar o rate limit global."
                )

        recuperados = recuperar_lotes_travados(conn)
        if recuperados:
            logger.warning("Recuperados %d lotes que estavam presos em processando.", recuperados)

        while True:
            try:
                if _sender_blocked_pause_ativo():
                    logger.critical(
                        "Worker pausado por sender_blocked. Sentinel=%s. Confirme desbloqueio no Exchange antes de remover o arquivo.",
                        SENDER_BLOCK_SENTINEL,
                    )
                    time.sleep(max(settings.worker_poll_interval_segundos, 60))
                    continue

                lote = pegar_proximo_lote(conn)
                if lote is not None:
                    _purgar_invalidos_do_lote(conn, lote["id"])
                    processar_lote(conn, lote, provider)
                    continue

                adicionados = repor_fila_automatica(conn)
                if adicionados:
                    logger.warning("Fila vazia; autoqueue repôs %d destinatarios.", adicionados)

                lote = pegar_proximo_lote(conn)
                if lote is None:
                    time.sleep(settings.worker_poll_interval_segundos)
                    continue
                _purgar_invalidos_do_lote(conn, lote["id"])
                processar_lote(conn, lote, provider)
            except Exception:
                logger.exception("Erro processando lote ou repondo fila -- worker continua rodando")
                conn.rollback()
                time.sleep(settings.worker_poll_interval_segundos)


if __name__ == "__main__":
    run()
