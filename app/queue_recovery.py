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
QUEUE_RECOVERY_BATCH_SIZE = 500
QUEUE_RECOVERY_MAX_BATCHES = 4
QUEUE_RECOVERY_STATEMENT_TIMEOUT_SECONDS = 30
QUEUE_RECOVERY_LOCK_TIMEOUT_SECONDS = 3


@dataclass(frozen=True)
class QueueRecoveryResult:
    normalized_legacy: int
    recovered_stale_sending: int
    reopened_lots: int
    quarantined_uncertain_dispatches: int = 0
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
            + self.quarantined_uncertain_dispatches
            + self.discarded_ineligible
            + self.discarded_already_suppressed
            + self.discarded_open_duplicates
            + self.closed_empty_lots
        )


def _run_batched_update(
    conn: psycopg.Connection,
    sql: str,
    *,
    label: str,
) -> int:
    """Apply a recovery update in bounded transactions without lock pileups.

    Legacy cleanup previously used unbounded UPDATE statements. On a busy
    production database one slow cleanup could hold row locks for hours, cause
    later repairers to wait behind it and strand the sender even though the
    worker process itself still looked active. Each batch now locks only rows
    that are immediately available, commits promptly and defers on timeout.
    The recovery remains idempotent, so later worker/hourly passes continue
    where the prior bounded pass stopped.
    """
    total = 0
    for _ in range(QUEUE_RECOVERY_MAX_BATCHES):
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "select set_config('statement_timeout', %s, true)",
                    (f"{QUEUE_RECOVERY_STATEMENT_TIMEOUT_SECONDS}s",),
                )
                cur.execute(
                    "select set_config('lock_timeout', %s, true)",
                    (f"{QUEUE_RECOVERY_LOCK_TIMEOUT_SECONDS}s",),
                )
                cur.execute(sql, (QUEUE_RECOVERY_BATCH_SIZE,))
                changed = int(cur.rowcount or 0)
            conn.commit()
        except (
            psycopg.errors.QueryCanceled,
            psycopg.errors.LockNotAvailable,
        ) as exc:
            conn.rollback()
            logger.warning(
                "QUEUE_RECOVERY_DEFERRED label=%s reason=%s detail=%s",
                label,
                type(exc).__name__,
                str(exc)[:500],
            )
            break

        total += changed
        if changed < QUEUE_RECOVERY_BATCH_SIZE:
            break
    return total


def quarentenar_dispatches_incertos(conn: psycopg.Connection) -> int:
    """Quarantine stale pre-send checkpoints without running heavy queue repair.

    A persisted ``dispatch_started`` row may already have reached the provider.
    It must never be blindly replayed. Reserve one conservative quota slot at
    the best durable dispatch timestamp and block the row atomically.
    """
    return _run_batched_update(
        conn,
        """
        with target as (
            select e.id, e.email, c.assunto,
                   coalesce(
                       greatest(
                           l.iniciado_em,
                           (
                               select max(coalesce(h.submitted_at, h.enviado_em))
                                 from mei_email.envios h
                                where h.lote_id = e.lote_id
                                  and h.id <> e.id
                                  and (
                                      h.submitted_at is not null
                                      or h.enviado_em is not null
                                  )
                           )
                       ),
                       now()
                   ) as quota_sent_at
              from mei_email.envios e
              join mei_email.lotes l on l.id = e.lote_id
              join mei_email.campanhas c on c.id = e.campanha_id
             where e.status = 'enviando'
               and coalesce(e.erro, '') like 'dispatch_started:%%'
               and (
                   l.iniciado_em is null
                   or l.iniciado_em < now() - interval '15 minutes'
               )
             order by e.id
             for update of e skip locked
             limit %s
        ),
        quota_reservation as (
            insert into mei_email.envios_externos_cota
                (email, subject, sent_at, source, provider_message_id, metadata)
            select t.email,
                   coalesce(t.assunto, 'Resultado de envio incerto'),
                   t.quota_sent_at,
                   'brevo_uncertain_dispatch_recovery',
                   null,
                   jsonb_build_object(
                       'purpose', 'anti_replay_quota_reservation',
                       'envio_id', t.id::text
                   )
              from target t
            returning id
        )
        update mei_email.envios e
           set status = 'bloqueado'::mei_email.status_envio,
               erro = 'delivery_uncertain: checkpoint dispatch_started recuperado fail-closed; reenvio proibido; cota Brevo reservada'
          from target t
         where t.id = e.id
        """,
        label="quarantine_uncertain_dispatch",
    )


def recuperar_fila_legada_e_lotes_orfaos(
    conn: psycopg.Connection,
) -> QueueRecoveryResult:
    """Normalize legacy states, prune ineligible/redundant rows and reopen lots.

    This function is idempotent. The worker calls it while holding the global
    sender advisory lock. The hourly repair service stops the worker before
    calling it, so a current provider submission is never moved backwards.

    Recovery is deliberately bounded. Every mutation selects at most a small
    batch with FOR UPDATE SKIP LOCKED, commits that batch and stops after a
    finite number of batches. This prevents one cleanup pass from holding
    transaction locks for hours while preserving the same consent, opt-out,
    dedupe and suppression semantics enforced by the worker.
    """
    normalized_legacy = _run_batched_update(
        conn,
        """
        with target as (
            select e.id
              from mei_email.envios e
             where e.status in ('pending', 'processing')
             order by e.id
             for update of e skip locked
             limit %s
        )
        update mei_email.envios e
           set status = 'pendente',
               erro = case
                   when coalesce(e.erro, '') = '' then
                       'recuperado: estado legado normalizado'
                   else e.erro || ' | recuperado: estado legado normalizado'
               end
          from target t
         where t.id = e.id
        """,
        label="normalize_legacy",
    )

    discarded_ineligible = _run_batched_update(
        conn,
        """
        with target as (
            select e.id, emp.opt_out
              from mei_email.envios e
              join mei_email.empresas emp on emp.cnpj = e.cnpj
             where e.status in ('pendente', 'enviando', 'pending', 'processing')
               and (
                   coalesce(emp.opt_out, false)
                   or emp.situacao_cadastral <> 'ATIVA'
                   or e.email is null
                   or btrim(e.email::text) = ''
                   or not mei_email.is_valid_email_address(e.email)
                   or position('contabil' in lower(btrim(e.email::text))) > 0
                   or mei_email.is_email_suppressed(e.email)
                   or mei_email.is_cnpj_suppressed(e.cnpj::text)
                   or (
                       select count(*)
                         from (
                           select 1
                             from mei_email.empresas emp2
                            where lower(btrim(emp2.email::text)) = lower(btrim(e.email::text))
                            limit 3
                         ) shared
                   ) > 2
               )
             order by e.id
             for update of e skip locked
             limit %s
        )
        update mei_email.envios e
           set status = (
                   case when t.opt_out then 'opt_out' else 'bloqueado' end
               )::mei_email.status_envio,
               erro = case
                   when coalesce(e.erro, '') = '' then
                       'recuperado: fila aberta tornou-se inelegivel antes do envio'
                   else e.erro || ' | recuperado: fila aberta tornou-se inelegivel antes do envio'
               end
          from target t
         where t.id = e.id
        """,
        label="discard_ineligible",
    )

    discarded_already_suppressed = _run_batched_update(
        conn,
        """
        with target as (
            select e.id
              from mei_email.envios e
             where e.status in ('pendente', 'enviando', 'pending', 'processing')
               and exists (
                       select 1
                         from mei_email.envios h
                        where h.id <> e.id
                          and h.status in ('submitted', 'enviado', 'delivered', 'bounced')
                          and (
                              h.cnpj = e.cnpj
                              or lower(btrim(h.email::text)) = lower(btrim(e.email::text))
                          )
                   )
             order by e.id
             for update of e skip locked
             limit %s
        )
        update mei_email.envios e
           set status = 'descartado',
               erro = case
                   when coalesce(e.erro, '') = '' then
                       'recuperado: fila redundante ja suprimida/submetida'
                   else e.erro || ' | recuperado: fila redundante ja suprimida/submetida'
               end
          from target t
         where t.id = e.id
        """,
        label="discard_suppressed_or_sent",
    )

    discarded_open_duplicates = _run_batched_update(
        conn,
        """
        with ranked as (
            select id,
                   row_number() over (
                       partition by lower(btrim(email::text))
                       order by criado_em, id
                   ) as email_rn,
                   row_number() over (
                       partition by cnpj
                       order by criado_em, id
                   ) as cnpj_rn
              from mei_email.envios
             where status in ('pendente', 'enviando', 'pending', 'processing')
        ),
        target as (
            select e.id
              from mei_email.envios e
              join ranked r on r.id = e.id
             where r.email_rn > 1 or r.cnpj_rn > 1
             order by e.id
             for update of e skip locked
             limit %s
        )
        update mei_email.envios e
           set status = 'descartado',
               erro = case
                   when coalesce(e.erro, '') = '' then
                       'recuperado: duplicata aberta de destinatario descartada'
                   else e.erro || ' | recuperado: duplicata aberta de destinatario descartada'
               end
          from target t
         where t.id = e.id
        """,
        label="discard_open_duplicates",
    )

    closed_empty_lots = _run_batched_update(
        conn,
        """
        with target as (
            select l.id
              from mei_email.lotes l
             where l.status = 'pendente'
               and not exists (
                   select 1
                     from mei_email.envios e
                    where e.lote_id = l.id
                      and e.status in ('pendente', 'enviando', 'pending', 'processing')
               )
             order by l.id
             for update of l skip locked
             limit %s
        )
        update mei_email.lotes l
           set status = 'concluido',
               concluido_em = coalesce(l.concluido_em, now()),
               erro = null
          from target t
         where t.id = l.id
        """,
        label="close_empty_lots",
    )

    quarantined_uncertain_dispatches = quarentenar_dispatches_incertos(conn)

    recovered_stale_sending = _run_batched_update(
        conn,
        """
        with target as (
            select e.id
              from mei_email.envios e
              join mei_email.lotes l on l.id = e.lote_id
             where e.status = 'enviando'
               and coalesce(e.erro, '') not like 'dispatch_started:%%'
               and (
                   l.iniciado_em is null
                   or l.iniciado_em < now() - interval '15 minutes'
               )
             order by e.id
             for update of e skip locked
             limit %s
        )
        update mei_email.envios e
           set status = 'pendente',
               erro = case
                   when coalesce(e.erro, '') = '' then
                       'recuperado: envio preso em processamento'
                   else e.erro || ' | recuperado: envio preso em processamento'
               end
          from target t
         where t.id = e.id
        """,
        label="recover_stale_sending",
    )

    reopened_lots = _run_batched_update(
        conn,
        """
        with target as (
            select l.id
              from mei_email.lotes l
             where l.status <> 'pendente'
               and exists (
                   select 1
                     from mei_email.envios e
                    where e.lote_id = l.id
                      and e.status in ('pendente', 'enviando', 'pending', 'processing')
               )
             order by l.id
             for update of l skip locked
             limit %s
        )
        update mei_email.lotes l
           set status = 'pendente',
               iniciado_em = null,
               concluido_em = null,
               erro = case
                   when coalesce(l.erro, '') = '' then
                       'recuperado: lote possuia envios abertos'
                   else l.erro || ' | recuperado: lote possuia envios abertos'
               end
          from target t
         where t.id = l.id
        """,
        label="reopen_orphan_lots",
    )

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
        quarantined_uncertain_dispatches=quarantined_uncertain_dispatches,
        discarded_ineligible=discarded_ineligible,
        discarded_already_suppressed=discarded_already_suppressed,
        discarded_open_duplicates=discarded_open_duplicates,
        closed_empty_lots=closed_empty_lots,
    )
    if result.changed:
        logger.warning(
            "QUEUE_RECOVERY normalized_legacy=%d stale_sending=%d uncertain_quarantined=%d reopened_lots=%d total_changes=%d",
            result.normalized_legacy,
            result.recovered_stale_sending,
            result.quarantined_uncertain_dispatches,
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
