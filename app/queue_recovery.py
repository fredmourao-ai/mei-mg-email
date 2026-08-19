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
    discarded_ineligible: int = 0
    discarded_already_suppressed: int = 0
    discarded_open_duplicates: int = 0
    closed_empty_lots: int = 0

    @property
    def changed(self) -> int:
        return (
            self.normalized_legacy
            + self.recovered_stale_sending
            + self.reopened_lots
            + self.discarded_ineligible
            + self.discarded_already_suppressed
            + self.discarded_open_duplicates
            + self.closed_empty_lots
        )


def recuperar_fila_legada_e_lotes_orfaos(
    conn: psycopg.Connection,
) -> QueueRecoveryResult:
    """Normalize legacy states, prune ineligible/redundant rows and reopen lots.

    This function is idempotent. The worker calls it while holding the global
    sender advisory lock. The hourly repair service stops the worker before
    calling it, so a current Graph submission is never moved backwards.

    Legacy queues can contain thousands of rows that are no longer eligible,
    were already suppressed/submitted, or are duplicates. Pruning those rows
    in set-based SQL avoids spending the sender loop on one query/commit per
    blocked recipient while preserving the exact same consent, opt-out and
    suppression semantics enforced by the worker.
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
               set status = case when emp.opt_out then 'opt_out' else 'bloqueado' end,
                   erro = case
                       when coalesce(e.erro, '') = '' then
                           'recuperado: fila aberta tornou-se inelegivel antes do envio'
                       else e.erro || ' | recuperado: fila aberta tornou-se inelegivel antes do envio'
                   end
              from mei_email.empresas emp
             where emp.cnpj = e.cnpj
               and e.status in ('pendente', 'enviando', 'pending', 'processing')
               and (
                   emp.opt_out = true
                   or emp.situacao_cadastral <> 'ATIVA'
                   or emp.provavel_terceiro = true
                   or emp.marketing_autorizado = false
                   or emp.mei_verificado = false
                   or not mei_email.is_valid_email_address(e.email)
               )
            """
        )
        discarded_ineligible = cur.rowcount

        cur.execute(
            """
            update mei_email.envios e
               set status = 'descartado',
                   erro = case
                       when coalesce(e.erro, '') = '' then
                           'recuperado: fila redundante ja suprimida/submetida'
                       else e.erro || ' | recuperado: fila redundante ja suprimida/submetida'
                   end
             where e.status in ('pendente', 'enviando', 'pending', 'processing')
               and (
                   mei_email.is_email_suppressed(e.email)
                   or exists (
                       select 1
                         from mei_email.envios h
                        where h.id <> e.id
                          and h.status in ('submitted', 'enviado', 'delivered', 'bounced')
                          and lower(btrim(h.email::text)) = lower(btrim(e.email::text))
                   )
               )
            """
        )
        discarded_already_suppressed = cur.rowcount

        cur.execute(
            """
            with ranked as (
                select id,
                       row_number() over (
                           partition by lower(btrim(email::text))
                           order by criado_em, id
                       ) as rn
                  from mei_email.envios
                 where status in ('pendente', 'enviando', 'pending', 'processing')
            )
            update mei_email.envios e
               set status = 'descartado',
                   erro = case
                       when coalesce(e.erro, '') = '' then
                           'recuperado: duplicata aberta de destinatario descartada'
                       else e.erro || ' | recuperado: duplicata aberta de destinatario descartada'
                   end
              from ranked r
             where r.id = e.id
               and r.rn > 1
            """
        )
        discarded_open_duplicates = cur.rowcount

        cur.execute(
            """
            update mei_email.lotes l
               set status = 'concluido',
                   concluido_em = coalesce(l.concluido_em, now()),
                   erro = null
             where l.status = 'pendente'
               and not exists (
                   select 1
                     from mei_email.envios e
                    where e.lote_id = l.id
                      and e.status in ('pendente', 'enviando', 'pending', 'processing')
               )
            """
        )
        closed_empty_lots = cur.rowcount

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

    if (
        discarded_ineligible
        or discarded_already_suppressed
        or discarded_open_duplicates
        or closed_empty_lots
    ):
        logger.warning(
            "QUEUE_BULK_PRUNE ineligible=%d suppressed_or_sent=%d duplicate_open=%d empty_lots=%d",
            discarded_ineligible,
            discarded_already_suppressed,
            discarded_open_duplicates,
            closed_empty_lots,
        )

    result = QueueRecoveryResult(
        normalized_legacy=normalized_legacy,
        recovered_stale_sending=recovered_stale_sending,
        reopened_lots=reopened_lots,
        discarded_ineligible=discarded_ineligible,
        discarded_already_suppressed=discarded_already_suppressed,
        discarded_open_duplicates=discarded_open_duplicates,
        closed_empty_lots=closed_empty_lots,
    )
    if result.changed:
        logger.warning(
            "QUEUE_RECOVERY normalized_legacy=%d stale_sending=%d reopened_lots=%d total_changes=%d",
            result.normalized_legacy,
            result.recovered_stale_sending,
            result.reopened_lots,
            result.changed,
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
