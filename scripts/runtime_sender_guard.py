#!/usr/bin/env python3
"""Fast runtime safety guard executed before the queue-first sender.

The production Flyway ledger can lag the physical schema. This guard therefore
reconciles send-safety invariants independently of migration history before each
worker start. It never grants consent, creates recipients, clears a sender-block
sentinel, or changes provider/rate limits.

Large open queues are repaired in small committed batches so a stale queue can
never hold the systemd unit in ExecStartPre until statement_timeout repeatedly
restarts the service.
"""
from __future__ import annotations

import json
import os

import psycopg
from dotenv import load_dotenv

BATCH = max(100, min(int(os.getenv("RUNTIME_GUARD_BATCH_SIZE", "500")), 2000))
OPEN_SQL = "('pendente','enviando','pending','processing')"
TERMINAL_SQL = "('submitted','enviado','delivered')"
LOCK_KEY = 99502027
LEGACY_MARKETING_ORIGINS = (
    "confirmacao_operador_2026-08-12",
    "confirmacao_operador_2026-08-13",
    "politica_importacao_operador_2026-08-13",
)
LEGACY_MEI_ORIGINS = (
    "override_operador_2026-08-13",
    "politica_importacao_operador_2026-08-13",
)


def _has_column(cur, table: str, column: str) -> bool:
    cur.execute(
        """
        select exists (
          select 1 from information_schema.columns
           where table_schema='mei_email' and table_name=%s and column_name=%s
        )
        """,
        (table, column),
    )
    return bool(cur.fetchone()[0])


def _has_table(cur, table: str) -> bool:
    cur.execute("select to_regclass(%s) is not null", (f"mei_email.{table}",))
    return bool(cur.fetchone()[0])


def _has_proc(cur, signature: str) -> bool:
    cur.execute("select to_regprocedure(%s) is not null", (signature,))
    return bool(cur.fetchone()[0])


def _batch_update(conn: psycopg.Connection, sql: str, params: tuple, *, max_batches: int = 200) -> int:
    total = 0
    for _ in range(max_batches):
        with conn.cursor() as cur:
            cur.execute("set statement_timeout='20s'")
            cur.execute("set lock_timeout='3s'")
            cur.execute(sql, params)
            changed = cur.rowcount
        conn.commit()
        total += max(changed, 0)
        if changed < BATCH:
            return total
    raise RuntimeError(f"runtime guard exceeded {max_batches} batches")


def _block_all_open(conn: psycopg.Connection, reason: str) -> int:
    return _batch_update(
        conn,
        f"""
        with target as (
          select id
            from mei_email.envios
           where status::text in {OPEN_SQL}
           order by id
           for update skip locked
           limit %s
        )
        update mei_email.envios e
           set status='bloqueado'::mei_email.status_envio,
               erro=%s
          from target t
         where e.id=t.id
        """,
        (BATCH, reason),
    )


def _block_ineligible(conn: psycopg.Connection) -> int:
    """Block rows without independently recorded, live MEI marketing eligibility."""
    return _batch_update(
        conn,
        f"""
        with target as (
          select e.id
            from mei_email.envios e
            join mei_email.empresas emp on emp.cnpj=e.cnpj
           where e.status::text in {OPEN_SQL}
             and (
               emp.marketing_autorizado is not true
               or nullif(btrim(coalesce(emp.marketing_autorizado_origem,'')), '') is null
               or btrim(emp.marketing_autorizado_origem) = any(%s)
               or emp.mei_verificado is not true
               or nullif(btrim(coalesce(emp.mei_verificado_origem,'')), '') is null
               or btrim(emp.mei_verificado_origem) = any(%s)
               or emp.opt_out is true
               or emp.situacao_cadastral <> 'ATIVA'
               or upper(coalesce(emp.uf,'')) <> 'MG'
               or upper(coalesce(emp.tipo_regime,'')) <> 'MEI'
               or emp.provavel_terceiro is true
               or emp.email is null
               or btrim(emp.email::text)=''
               or not mei_email.is_valid_email_address(emp.email)
             )
           order by e.id
           for update of e skip locked
           limit %s
        )
        update mei_email.envios e
           set status='bloqueado'::mei_email.status_envio,
               erro='runtime_guard: fila aberta sem autorizacao/MEI elegivel independente'
          from target t
         where e.id=t.id
        """,
        (list(LEGACY_MARKETING_ORIGINS), list(LEGACY_MEI_ORIGINS), BATCH),
    )


def _block_suppressed(conn: psycopg.Connection) -> int:
    """Use exact indexed suppression values; do not depend on a stale callback function."""
    return _batch_update(
        conn,
        f"""
        with target as (
          select e.id
            from mei_email.envios e
            join mei_email.empresas emp on emp.cnpj=e.cnpj
           where e.status::text in {OPEN_SQL}
             and exists (
               select 1
                 from mei_email.email_suppressions s
                where s.active
                  and (
                    (s.scope='email' and s.value=lower(btrim(emp.email::text))::public.citext)
                    or (s.scope='domain' and s.value=split_part(lower(btrim(emp.email::text)),'@',2)::public.citext)
                    or (s.scope='cnpj' and s.value=upper(btrim(emp.cnpj::text))::public.citext)
                  )
             )
           order by e.id
           for update of e skip locked
           limit %s
        )
        update mei_email.envios e
           set status='bloqueado'::mei_email.status_envio,
               erro='runtime_guard: destinatario em suppression list'
          from target t
         where e.id=t.id
        """,
        (BATCH,),
    )


def _block_replay(conn: psycopg.Connection) -> int:
    return _batch_update(
        conn,
        f"""
        with target as (
          select e.id
            from mei_email.envios e
           where e.status::text in {OPEN_SQL}
             and exists (
               select 1
                 from mei_email.envios prior
                where prior.id<>e.id
                  and lower(btrim(prior.email::text))=lower(btrim(e.email::text))
                  and prior.status::text in {TERMINAL_SQL}
             )
           order by e.id
           for update of e skip locked
           limit %s
        )
        update mei_email.envios e
           set status='bloqueado'::mei_email.status_envio,
               erro='runtime_guard: destinatario ja submetido/entregue; anti-replay'
          from target t
         where e.id=t.id
        """,
        (BATCH,),
    )


def main() -> int:
    load_dotenv('/home/ubuntu/mei-mg-email/.env', override=True)
    database_url = os.environ['DATABASE_URL']
    normalized_campaigns = 0
    blocked_ineligible = 0
    blocked_suppressed = 0
    blocked_replay = 0
    missing: list[str] = []

    with psycopg.connect(database_url, connect_timeout=10) as conn:
        conn.autocommit = False
        with conn.cursor() as cur:
            # Session-level lock survives the small commits between repair batches.
            cur.execute("set statement_timeout='20s'")
            cur.execute("select pg_advisory_lock(%s)", (LOCK_KEY,))
            cur.execute(
                """
                update mei_email.campanhas
                   set corpo_template = replace(
                         replace(
                           corpo_template,
                           'Você recebeu este e-mail porque seu contato consta em base pública de CNPJ.',
                           'Você recebe esta mensagem porque há uma autorização comercial registrada para este contato.'
                         ),
                         'Você recebeu este e-mail porque seu contato consta em base publica de CNPJ.',
                         'Você recebe esta mensagem porque há uma autorização comercial registrada para este contato.'
                       )
                 where corpo_template ilike '%base pública de CNPJ%'
                    or corpo_template ilike '%base publica de CNPJ%'
                """
            )
            normalized_campaigns = max(cur.rowcount, 0)
        conn.commit()

        required = (
            'marketing_autorizado', 'marketing_autorizado_origem',
            'mei_verificado', 'mei_verificado_origem', 'opt_out',
            'situacao_cadastral', 'uf', 'tipo_regime', 'provavel_terceiro', 'email'
        )
        with conn.cursor() as cur:
            missing = [c for c in required if not _has_column(cur, 'empresas', c)]
            valid_email_fn = _has_proc(cur, 'mei_email.is_valid_email_address(citext)')
            suppressions_table = _has_table(cur, 'email_suppressions')
        conn.rollback()

        if missing or not valid_email_fn:
            detail = ','.join(missing) if missing else 'is_valid_email_address(citext)'
            blocked_ineligible = _block_all_open(
                conn,
                'runtime_guard: contrato de elegibilidade indisponivel: ' + detail,
            )
        else:
            blocked_ineligible = _block_ineligible(conn)
            if suppressions_table:
                blocked_suppressed = _block_suppressed(conn)
            blocked_replay = _block_replay(conn)

        with conn.cursor() as cur:
            cur.execute("set statement_timeout='20s'")
            cur.execute(
                """
                select
                  (select count(*) from mei_email.campanhas
                    where corpo_template ilike '%base pública de CNPJ%'
                       or corpo_template ilike '%base publica de CNPJ%') legacy_copy_campaigns,
                  (select count(*) from mei_email.envios
                    where status::text in ('pendente','enviando','pending','processing')) open_queue,
                  (select count(*) from mei_email.envios e
                    where e.status::text in ('pendente','enviando','pending','processing')
                      and exists (
                        select 1 from mei_email.envios prior
                         where prior.id<>e.id
                           and lower(btrim(prior.email::text))=lower(btrim(e.email::text))
                           and prior.status::text in ('submitted','enviado','delivered')
                      )) replay_open
                """
            )
            legacy_copy, open_queue, replay_open = cur.fetchone()
            cur.execute("select pg_advisory_unlock(%s)", (LOCK_KEY,))
        conn.commit()

    result = {
        'runtime_sender_guard': 'ok',
        'batch_size': BATCH,
        'normalized_campaigns': int(normalized_campaigns),
        'blocked_ineligible': int(blocked_ineligible),
        'blocked_suppressed': int(blocked_suppressed),
        'blocked_replay': int(blocked_replay),
        'legacy_copy_campaigns': int(legacy_copy or 0),
        'open_queue': int(open_queue or 0),
        'replay_open': int(replay_open or 0),
        'missing_eligibility_columns': missing,
    }
    print(json.dumps(result, sort_keys=True))
    if result['legacy_copy_campaigns'] or result['replay_open']:
        raise SystemExit('runtime sender guard invariants failed')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
