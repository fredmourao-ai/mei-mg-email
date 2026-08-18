"""Worker operacional que prioriza a fila existente antes de repor autoqueue.

Evita que uma consulta de reposicao lenta bloqueie milhares de envios ja
prontos. A reposicao ocorre em outra conexao, com timeout, somente depois de
recuperar estados legados e lotes orfaos. Enderecos com sintaxe invalida sao
suprimidos e removidos antes de qualquer chamada ao Graph.
"""
from __future__ import annotations

import os
import time
from pathlib import Path

import psycopg
from psycopg.rows import dict_row

from app.config import settings
from app.email_provider import get_email_provider
from app.queue_recovery import (
    recuperar_fila_legada_e_lotes_orfaos,
    repor_fila_automatica_isolada,
)
import worker.worker as base_worker
from worker.worker import (
    WORKER_ADVISORY_LOCK_ID,
    _sender_blocked_pause_ativo,
    logger,
    pegar_proximo_lote,
    processar_lote,
    recuperar_lotes_travados,
)

# One canonical circuit-breaker path is shared by the worker, monitor and
# two-hour auto-repair service. Keep the legacy repository path read-only as a
# second safety signal during the transition.
SENDER_BLOCK_SENTINEL = Path(
    os.getenv(
        "SENDER_BLOCK_SENTINEL_PATH",
        "/var/lib/mei-mg-email/sender_blocked.pause",
    )
)
LEGACY_SENDER_BLOCK_SENTINEL = (
    Path(__file__).resolve().parents[1] / "runtime" / "sender_blocked.pause"
)
base_worker.SENDER_BLOCK_SENTINEL = SENDER_BLOCK_SENTINEL


def _sender_pause_ativo_em_qualquer_caminho() -> bool:
    return _sender_blocked_pause_ativo() or LEGACY_SENDER_BLOCK_SENTINEL.is_file()


def _tabela_cota_externa_existe(conn: psycopg.Connection) -> bool:
    with conn.cursor() as cur:
        cur.execute("select to_regclass('mei_email.envios_externos_cota')")
        return cur.fetchone()[0] is not None


def _obter_envios_ultimas_24h_indexado(conn: psycopg.Connection) -> int:
    """Count the rolling window using the partial index and external ledger."""
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
    """Consult compact suppression first and then indexed email history."""
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


# processar_lote is defined in worker.worker. Replacing these module globals
# preserves all safety checks while using indexed paths.
base_worker.obter_envios_ultimas_24h = _obter_envios_ultimas_24h_indexado
base_worker._ja_submetido_ou_entregue = _ja_submetido_ou_entregue_indexado


def _purgar_invalidos_do_lote(conn: psycopg.Connection, lote_id) -> int:
    """Suppress and remove invalid recipients before any Graph request."""
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            select distinct e.cnpj, e.email
              from mei_email.envios e
             where e.lote_id = %s
               and e.status in ('pendente', 'pending')
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
            "Lote %s: %d destinatarios invalidos removidos antes do Graph.",
            lote_id,
            len(invalidos),
        )
    return len(invalidos)


def _processar_se_disponivel(conn: psycopg.Connection, provider) -> bool:
    lote = pegar_proximo_lote(conn)
    if lote is None:
        return False
    _purgar_invalidos_do_lote(conn, lote["id"])
    processar_lote(conn, lote, provider)
    return True


def run() -> None:
    if settings.max_envios_por_dia > 10000:
        raise RuntimeError("MAX_ENVIOS_POR_DIA nao pode ultrapassar 10000.")
    if settings.meta_envios_por_dia <= 0:
        raise RuntimeError("META_ENVIOS_POR_DIA precisa ser maior que zero.")
    if settings.meta_envios_por_dia > settings.max_envios_por_dia:
        raise RuntimeError("META_ENVIOS_POR_DIA nao pode ultrapassar o teto.")
    if settings.rate_limit_envios_por_minuto > 30:
        raise RuntimeError("RATE_LIMIT_ENVIOS_POR_MINUTO nao pode ultrapassar 30.")
    if settings.rate_limit_envios_por_minuto <= 0:
        raise RuntimeError("RATE_LIMIT_ENVIOS_POR_MINUTO precisa ser positivo.")
    if settings.queue_min_pending < 1:
        raise RuntimeError("QUEUE_MIN_PENDING precisa ser pelo menos 1.")
    if settings.queue_target_pending <= settings.queue_min_pending:
        raise RuntimeError("QUEUE_TARGET_PENDING precisa ser maior que o minimo.")

    provider = get_email_provider(settings.email_provider)
    logger.info(
        "Worker queue-first iniciado. provedor=%s rate_limit=%d/min "
        "meta_24h=%d teto_24h=%d poll=%ds fila_min=%d fila_target=%d",
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
                    "Ja existe outro worker de disparo ativo; instancia unica mantida."
                )

        recuperados = recuperar_lotes_travados(conn)
        recovery = recuperar_fila_legada_e_lotes_orfaos(conn)
        if recuperados or recovery.changed:
            logger.warning(
                "STARTUP_RECOVERY stuck_lots=%d queue_changes=%d",
                recuperados,
                recovery.changed,
            )

        while True:
            try:
                if _sender_pause_ativo_em_qualquer_caminho():
                    logger.critical(
                        "Worker pausado por sender_blocked. canonical=%s legacy=%s",
                        SENDER_BLOCK_SENTINEL,
                        LEGACY_SENDER_BLOCK_SENTINEL,
                    )
                    time.sleep(max(settings.worker_poll_interval_segundos, 60))
                    continue

                # Existing queue always wins. No replenishment query may run
                # while there is a recoverable lot.
                if _processar_se_disponivel(conn, provider):
                    continue

                recovery = recuperar_fila_legada_e_lotes_orfaos(conn)
                if recovery.changed and _processar_se_disponivel(conn, provider):
                    continue

                adicionados = repor_fila_automatica_isolada()
                if adicionados:
                    logger.warning(
                        "AUTOQUEUE_ISOLATED added=%d; retomando consumo.",
                        adicionados,
                    )

                if not _processar_se_disponivel(conn, provider):
                    time.sleep(settings.worker_poll_interval_segundos)
            except Exception:
                logger.exception("Erro no ciclo do worker; conexao sera recuperada")
                conn.rollback()
                time.sleep(settings.worker_poll_interval_segundos)


if __name__ == "__main__":
    run()
