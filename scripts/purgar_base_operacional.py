#!/usr/bin/env python3
"""Move historico/sujeitos fora do filtro para supressao e limpa a base operacional.

Por padrao apenas calcula/mostra lotes. Use --apply para efetivar. O processo e
idempotente: email/CNPJ entram em email_suppressions e nunca voltam pelos
triggers da V025. Para envios das ultimas 24h, o PII e removido mas a linha e
mantida anonima somente como ledger de quota; depois de 24h essa linha pode ser
removida sem afetar a janela movel do Microsoft 365.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone, timedelta

import psycopg
from psycopg.rows import dict_row

from app.config import settings

SENT_STATUSES = ("submitted", "enviado", "delivered")
LEDGER_PATTERN = "quota+%@invalid.local"


def _ledger_email(envio_id) -> str:
    return f"quota+{str(envio_id).replace('-', '')}@invalid.local"


def _ledger_cnpj(envio_id) -> str:
    return str(envio_id).replace("-", "").upper()[:14]


def purge_sent(conn: psycopg.Connection, batch_size: int, apply: bool) -> tuple[int, int]:
    """Retorna (anonimizados_24h, removidos_antigos)."""
    anonymized = 0
    deleted = 0
    while True:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                select id, btrim(cnpj::text) as cnpj, email::text as email,
                       coalesce(enviado_em, criado_em) as event_at
                  from mei_email.envios
                 where status::text = any(%s)
                   and email::text not like %s
                 order by coalesce(enviado_em, criado_em), id
                 limit %s
                """,
                (list(SENT_STATUSES), LEDGER_PATTERN, batch_size),
            )
            rows = cur.fetchall()
        if not rows:
            break

        recent = sum(1 for row in rows if row["event_at"] >= datetime.now(timezone.utc) - timedelta(hours=24))
        old = len(rows) - recent
        print(f"sent_batch={len(rows)} recent_to_anonymize={recent} old_to_delete={old}", flush=True)
        if not apply:
            return recent, old

        with conn.cursor() as cur:
            for row in rows:
                cur.execute(
                    "select mei_email.register_operational_suppression(%s,%s::citext,'sent','historical_cleanup',%s,%s)",
                    (row["cnpj"], row["email"], str(row["id"]), row["event_at"]),
                )
                cur.execute(
                    """
                    delete from mei_email.empresas
                     where btrim(cnpj::text) = %s
                        or lower(btrim(email::text)) = lower(btrim(%s))
                    """,
                    (row["cnpj"], row["email"]),
                )

                if row["event_at"] >= datetime.now(timezone.utc) - timedelta(hours=24):
                    cur.execute(
                        """
                        update mei_email.envios
                           set email = %s::citext,
                               cnpj = %s,
                               erro = case
                                 when erro is null or erro = '' then 'PII_PURGED_RATE_LEDGER'
                                 else erro || ' | PII_PURGED_RATE_LEDGER'
                               end
                         where id = %s
                        """,
                        (_ledger_email(row["id"]), _ledger_cnpj(row["id"]), row["id"]),
                    )
                    anonymized += 1
                else:
                    cur.execute("delete from mei_email.envios where id = %s", (row["id"],))
                    deleted += 1
        conn.commit()
    return anonymized, deleted


def purge_filtered(conn: psycopg.Connection, batch_size: int, apply: bool) -> int:
    total = 0
    last_cnpj = ""
    while True:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                select btrim(cnpj::text) as cnpj, email::text as email,
                       mei_email.operational_filter_rejection_reason(
                         situacao_cadastral, uf, email, opt_out, provavel_terceiro,
                         marketing_autorizado, tipo_regime, mei_verificado
                       ) as rejection,
                       mei_email.is_cnpj_suppressed(cnpj::text) as cnpj_suppressed,
                       case when email is null then false else mei_email.is_email_suppressed(email) end as email_suppressed
                  from mei_email.empresas
                 where btrim(cnpj::text) > %s
                   and (
                     mei_email.operational_filter_rejection_reason(
                       situacao_cadastral, uf, email, opt_out, provavel_terceiro,
                       marketing_autorizado, tipo_regime, mei_verificado
                     ) is not null
                     or mei_email.is_cnpj_suppressed(cnpj::text)
                     or (email is not null and mei_email.is_email_suppressed(email))
                   )
                 order by cnpj
                 limit %s
                """,
                (last_cnpj, batch_size),
            )
            rows = cur.fetchall()
        if not rows:
            break
        print(f"filtered_batch={len(rows)} first={rows[0]['cnpj']} last={rows[-1]['cnpj']}", flush=True)
        if not apply:
            total += len(rows)
            break

        for row in rows:
            cnpj = row["cnpj"]
            email = row["email"]
            reason = row["rejection"] or "already_suppressed"
            with conn.cursor() as cur:
                cur.execute(
                    "select mei_email.register_operational_suppression(%s,%s::citext,%s,'historical_filter_cleanup',null,now())",
                    (cnpj, email, reason),
                )
                cur.execute(
                    """
                    delete from mei_email.envios
                     where email::text not like %s
                       and (btrim(cnpj::text) = %s
                        or (%s is not null and lower(btrim(email::text)) = lower(btrim(%s))))
                    """,
                    (LEDGER_PATTERN, cnpj, email, email),
                )
                cur.execute("delete from mei_email.empresas where btrim(cnpj::text) = %s", (cnpj,))
            last_cnpj = cnpj
        conn.commit()
        total += len(rows)
    return total


def cleanup_expired_ledgers(conn: psycopg.Connection, apply: bool) -> int:
    with conn.cursor() as cur:
        cur.execute(
            """
            select count(*)
              from mei_email.envios
             where email::text like %s
               and enviado_em < now() - interval '24 hours'
            """,
            (LEDGER_PATTERN,),
        )
        count = int(cur.fetchone()[0] or 0)
        if apply and count:
            cur.execute(
                """
                delete from mei_email.envios
                 where email::text like %s
                   and enviado_em < now() - interval '24 hours'
                """,
                (LEDGER_PATTERN,),
            )
    if apply:
        conn.commit()
    return count


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="Efetiva supressao/exclusao; sem esta flag apenas amostra.")
    parser.add_argument("--batch-size", type=int, default=500, help="Tamanho dos lotes de limpeza.")
    args = parser.parse_args()
    batch_size = max(10, min(args.batch_size, 5000))

    with psycopg.connect(settings.database_url) as conn:
        anonymized, deleted = purge_sent(conn, batch_size, args.apply)
        filtered = purge_filtered(conn, batch_size, args.apply)
        expired = cleanup_expired_ledgers(conn, args.apply)

    print(f"PURGE_APPLY={str(args.apply).lower()}")
    print(f"SENT_RECENT_ANONYMIZED={anonymized}")
    print(f"SENT_OLDER_DELETED={deleted}")
    print(f"FILTERED_DELETED={filtered}")
    print(f"EXPIRED_LEDGER_DELETED={expired if args.apply else 0}")
    print(f"EXPIRED_LEDGER_WOULD_DELETE={expired}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
