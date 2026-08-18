from __future__ import annotations

import logging
from dataclasses import dataclass

import psycopg

from app.config import settings
from app.queue_manager import repor_fila_automatica

logger = logging.getLogger("mei_mg_email.queue_recovery")

OPEN_ENVIO_STATUSES = ("pendente", "enviando", "pending", "processing")
LEGACY_ENVIO_STATUSES = ("pending", "processing")
QUEUE_REPAIR_ADVISORY_LOCK_ID = 9950202602


@dataclass(frozen=True)
class QueueRecoveryResult:
    normalized_legacy: int
    recovered_stale_sending: int
    reopened_lots: int

    @property
    def changed(self) -> int:
        return self.normalized_legacy + self.recovered_stale_sending + self.reopened_lots


def recuperar_fila_legada_e_lotes_orfaos(
    conn: psycopg.Connection,
) -> QueueRecoveryResult:
    """Normalize legacy queue states and reopen lots that still have work.

    This function is idempotent. The worker calls it while holding the global
    sender advisory lock. The two-hour repair service stops the worker before
    calling it, so a current Graph submission is never moved backwards.
    """
    with conn.cursor() as cur:
        cur.execute(
            """
            update mei_email.envios
               set status = 'pendente',
                   erro = case
                       when coalesce(erro, '') = '' then
                           'recuperado: estado legado normalizado'
                       else erro || ' | recuperado: estado legado normalizado'
                   end
             where status in ('pending', 'processing')
            """
        )
        normalized_legacy = cur.rowcount

        cur.execute(
            """
            update mei_email.envios e
               set status = 'pendente',
                   erro = case
                       when coalesce(e.erro, '') = '' then
                           'recuperado: envio preso em processamento'
                       else e.erro || ' | recuperado: envio preso em processamento'
                   end
              from mei_email.lotes l
             where l.id = e.lote_id
               and e.status = 'enviando'
               and l.status = 'processando'
               and l.iniciado_em < now() - interval '15 minutes'
            """
        )
        recovered_stale_sending = cur.rowcount

        cur.execute(
            """
            update mei_email.lotes l
               set status = 'pendente',
                   iniciado_em = null,
                   concluido_em = null,
                   erro = case
                       when coalesce(l.erro, '') = '' then
                           'recuperado: lote possuia envios abertos'
                       else l.erro || ' | recuperado: lote possuia envios abertos'
                   end
             where l.status <> 'pendente'
               and exists (
                   select 1
                     from mei_email.envios e
                    where e.lote_id = l.id
                      and e.status in ('pendente', 'enviando', 'pending', 'processing')
               )
            """
        )
        reopened_lots = cur.rowcount
    conn.commit()

    result = QueueRecoveryResult(
        normalized_legacy=normalized_legacy,
        recovered_stale_sending=recovered_stale_sending,
        reopened_lots=reopened_lots,
    )
    if result.changed:
        logger.warning(
            "QUEUE_RECOVERY normalized_legacy=%d stale_sending=%d reopened_lots=%d",
            result.normalized_legacy,
            result.recovered_stale_sending,
            result.reopened_lots,
        )
    return result


def repor_fila_automatica_isolada(
    *,
    statement_timeout_seconds: int = 90,
    lock_timeout_seconds: int = 5,
) -> int:
    """Run the expensive replenisher outside the sender connection.

    A blocked refill must never hold the worker advisory lock or stop already
    queued messages. Timeouts are treated as a deferred refill, not as a send
    failure.
    """
    try:
        with psycopg.connect(settings.database_url) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "select set_config('statement_timeout', %s, false)",
                    (f"{max(statement_timeout_seconds, 1)}s",),
                )
                cur.execute(
                    "select set_config('lock_timeout', %s, false)",
                    (f"{max(lock_timeout_seconds, 1)}s",),
                )
            return repor_fila_automatica(conn)
    except (
        psycopg.errors.QueryCanceled,
        psycopg.errors.LockNotAvailable,
        psycopg.OperationalError,
    ) as exc:
        logger.error(
            "AUTOQUEUE_DEFERRED reason=%s detail=%s",
            type(exc).__name__,
            str(exc)[:500],
        )
        return 0
