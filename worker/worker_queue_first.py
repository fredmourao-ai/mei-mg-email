"""Worker operacional que prioriza a fila existente antes de repor autoqueue.

Evita que uma consulta de reposicao lenta bloqueie milhares de envios ja
prontos. A reposicao so ocorre quando nao existe lote pendente. Todas as travas
de seguranca, cota movel, sender_blocked e processamento permanecem nas funcoes
do worker principal.
"""
from __future__ import annotations

import time

import psycopg

from app.config import settings
from app.email_provider import get_email_provider
from app.queue_manager import repor_fila_automatica
from worker.worker import (
    WORKER_ADVISORY_LOCK_ID,
    SENDER_BLOCK_SENTINEL,
    _sender_blocked_pause_ativo,
    logger,
    pegar_proximo_lote,
    processar_lote,
    recuperar_lotes_travados,
)


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

                # Prioridade operacional: consumir o que ja esta pronto.
                # Uma reposicao cara nunca deve bloquear lotes pendentes.
                lote = pegar_proximo_lote(conn)
                if lote is not None:
                    processar_lote(conn, lote, provider)
                    continue

                # So repoe quando a fila realmente secou.
                adicionados = repor_fila_automatica(conn)
                if adicionados:
                    logger.warning("Fila vazia; autoqueue repôs %d destinatarios.", adicionados)

                lote = pegar_proximo_lote(conn)
                if lote is None:
                    time.sleep(settings.worker_poll_interval_segundos)
                    continue
                processar_lote(conn, lote, provider)
            except Exception:
                logger.exception("Erro processando lote ou repondo fila -- worker continua rodando")
                conn.rollback()
                time.sleep(settings.worker_poll_interval_segundos)


if __name__ == "__main__":
    run()
