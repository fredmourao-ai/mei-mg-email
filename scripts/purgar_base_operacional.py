#!/usr/bin/env python3
"""Move historico/sujeitos fora do filtro para supressao e limpa a base operacional.

Por padrao apenas calcula/mostra lotes. Use --apply para efetivar. O processo e
idempotente: email/CNPJ entram em email_suppressions e nunca voltam pelos
triggers da V025. Registros enviados antigos sao removidos de envios/empresas;
a janela de 24h continua preservada para novos envios pelo ledger anonimo da
V025.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass

import psycopg
from psycopg.rows import dict_row

from app.config import settings

SENT_STATUSES = ("submitted", "enviado", "delivered")
LEDGER_PATTERN = "quota+%@invalid.local"


@dataclass
class Stats:
    sent_purged: int = 0
    filtered_purged: int = 0


def purge_sent(conn: psycopg.Connection, batch_size: int, apply: bool) -> int:
    total = 0
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
        print(f"sent_batch={len(rows)}", flush=True)
        if not apply:
            total += len(rows)
            break

        ids = [row["id"] for row in rows]
        cnpjs = [row["cnpj"] for row in rows if row["cnpj"]]
        emails = [str(row["email"]).strip().lower() for row in rows if row["email"]]
        with conn.cursor() as cur:
            for row in rows:
                cur.execute(
                    "select mei_email.register_operational_suppression(%s,%s::citext,'sent','historical_cleanup',%s,%s)",
                    (row["cnpj"], row["email"], str(row["id"]), row["event_at"]),
                )
            cur.execute("delete from mei_email.envios where id = any(%s)", (ids,))
            if cnpjs or emails:
                cur.execute(
                    """
                    delete from mei_email.empresas
                     where (%s and btrim(cnpj::text) = any(%s))
                        or (%s and lower(btrim(email::text)) = any(%s))
                    """,
                    (bool(cnpjs), cnpjs or [""], bool(emails), emails or [""]),
                )
        conn.commit()
        total += len(rows)
    return total


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
                     where btrim(cnpj::text) = %s
                        or (%s is not null and lower(btrim(email::text)) = lower(btrim(%s)))
                    """,
                    (cnpj, email, email),
                )
                cur.execute("delete from mei_email.empresas where btrim(cnpj::text) = %s", (cnpj,))
            last_cnpj = cnpj
        conn.commit()
        total += len(rows)
    return total


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="Efetiva supressao e exclusao; sem esta flag apenas amostra um lote.")
    parser.add_argument("--batch-size", type=int, default=500, help="Tamanho dos lotes de limpeza.")
    args = parser.parse_args()
    batch_size = max(10, min(args.batch_size, 5000))

    with psycopg.connect(settings.database_url) as conn:
        sent = purge_sent(conn, batch_size, args.apply)
        filtered = purge_filtered(conn, batch_size, args.apply)

    print(f"PURGE_APPLY={str(args.apply).lower()}")
    print(f"PURGED_SENT={sent}")
    print(f"PURGED_FILTERED={filtered}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
