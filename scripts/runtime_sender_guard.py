#!/usr/bin/env python3
"""Runtime fail-closed guard for queue-first sending.

This guard is intentionally independent of Flyway history. It runs immediately
before the worker and reconciles only safety invariants: legacy campaign copy,
independent authorization/MEI evidence, opt-out/company validity, technical
suppression when available, and terminal-send replay. It never grants consent,
creates recipients, clears sender-block, or increases provider limits.
"""
from __future__ import annotations

import json
import os

import psycopg
from dotenv import load_dotenv

OPEN = "('pendente','enviando','pending','processing')"
TERMINAL = "('submitted','enviado','delivered')"
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


def _has_proc(cur, signature: str) -> bool:
    cur.execute("select to_regprocedure(%s) is not null", (signature,))
    return bool(cur.fetchone()[0])


def main() -> int:
    load_dotenv('/home/ubuntu/mei-mg-email/.env', override=True)
    database_url = os.environ['DATABASE_URL']

    with psycopg.connect(database_url, connect_timeout=10) as conn:
        with conn.cursor() as cur:
            cur.execute("set statement_timeout='60s'")
            cur.execute("set lock_timeout='5s'")
            cur.execute("select pg_advisory_xact_lock(99502027)")

            # Never let a legacy discovery claim leave the worker again.
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
            normalized_campaigns = cur.rowcount

            required = (
                'marketing_autorizado', 'marketing_autorizado_origem',
                'mei_verificado', 'mei_verificado_origem', 'opt_out',
                'situacao_cadastral', 'provavel_terceiro', 'email'
            )
            missing = [c for c in required if not _has_column(cur, 'empresas', c)]

            if missing:
                cur.execute(
                    f"""
                    update mei_email.envios
                       set status='bloqueado',
                           erro=%s
                     where status::text in {OPEN}
                    """,
                    ('runtime_guard: colunas de elegibilidade ausentes: ' + ','.join(missing),),
                )
                blocked_open = cur.rowcount
            else:
                suppression_email = _has_proc(cur, 'mei_email.is_email_suppressed(citext)')
                suppression_cnpj = _has_proc(cur, 'mei_email.is_cnpj_suppressed(text)')
                extra = []
                if suppression_email:
                    extra.append("mei_email.is_email_suppressed(emp.email)")
                if suppression_cnpj:
                    extra.append("mei_email.is_cnpj_suppressed(emp.cnpj::text)")
                extra_sql = ''.join(f" or {cond}" for cond in extra)

                cur.execute(
                    f"""
                    update mei_email.envios e
                       set status='bloqueado',
                           erro='runtime_guard: fila aberta inelegivel/legada/replay'
                      from mei_email.empresas emp
                     where e.cnpj=emp.cnpj
                       and e.status::text in {OPEN}
                       and (
                         emp.marketing_autorizado is not true
                         or nullif(btrim(coalesce(emp.marketing_autorizado_origem,'')), '') is null
                         or btrim(emp.marketing_autorizado_origem) = any(%s)
                         or emp.mei_verificado is not true
                         or nullif(btrim(coalesce(emp.mei_verificado_origem,'')), '') is null
                         or btrim(emp.mei_verificado_origem) = any(%s)
                         or emp.opt_out is true
                         or emp.situacao_cadastral <> 'ATIVA'
                         or emp.provavel_terceiro is true
                         or emp.email is null
                         or btrim(emp.email::text)=''
                         {extra_sql}
                         or exists (
                           select 1 from mei_email.envios prior
                            where prior.id<>e.id
                              and lower(btrim(prior.email::text))=lower(btrim(e.email::text))
                              and prior.status::text in {TERMINAL}
                         )
                       )
                    """,
                    (list(LEGACY_MARKETING_ORIGINS), list(LEGACY_MEI_ORIGINS)),
                )
                blocked_open = cur.rowcount

            conn.commit()

        with conn.cursor() as cur:
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

    result = {
        'runtime_sender_guard': 'ok',
        'normalized_campaigns': int(normalized_campaigns or 0),
        'blocked_open': int(blocked_open or 0),
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
