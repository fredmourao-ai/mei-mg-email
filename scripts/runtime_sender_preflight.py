#!/usr/bin/env python3
"""Bounded send-safety preflight for the nonstop queue-first worker.

This runs as systemd ExecStartPre.  It must never perform a table-wide queue
rewrite: production proved that doing so can keep the worker in `activating`
for minutes and can destabilize the local PostgreSQL container.  Per-recipient
eligibility/replay enforcement lives in ``worker.safe_entrypoint`` immediately
before each Graph submission.

The preflight only verifies that the schema primitives needed by that guard
exist and normalizes the campaign copy.  It never grants consent, creates a
recipient, clears sender-block state, or changes provider/rate limits.
"""
from __future__ import annotations

import json
import os

import psycopg
from dotenv import load_dotenv

LOCK_KEY = 99502027
REQUIRED_EMPRESA_COLUMNS = (
    "marketing_autorizado",
    "marketing_autorizado_origem",
    "mei_verificado",
    "mei_verificado_origem",
    "opt_out",
    "situacao_cadastral",
    "uf",
    "tipo_regime",
    "provavel_terceiro",
    "email",
)


def main() -> int:
    load_dotenv("/home/ubuntu/mei-mg-email/.env", override=True)
    database_url = os.environ["DATABASE_URL"]
    out: dict[str, object] = {"runtime_sender_preflight": "ok"}

    with psycopg.connect(database_url, connect_timeout=10) as conn:
        with conn.cursor() as cur:
            cur.execute("set statement_timeout='10s'")
            cur.execute("set lock_timeout='2s'")
            cur.execute("select pg_try_advisory_lock(%s)", (LOCK_KEY,))
            if not bool(cur.fetchone()[0]):
                raise RuntimeError("runtime sender preflight lock busy; retrying via systemd")

            cur.execute(
                """
                select column_name
                  from information_schema.columns
                 where table_schema='mei_email'
                   and table_name='empresas'
                   and column_name = any(%s::text[])
                """,
                (list(REQUIRED_EMPRESA_COLUMNS),),
            )
            present = {str(row[0]) for row in cur.fetchall()}
            missing = sorted(set(REQUIRED_EMPRESA_COLUMNS) - present)
            if missing:
                raise RuntimeError(
                    "send-safety columns unavailable: " + ",".join(missing)
                )

            cur.execute(
                "select to_regclass('mei_email.email_suppressions') is not null"
            )
            if not bool(cur.fetchone()[0]):
                raise RuntimeError("email_suppressions is required before worker start")
            cur.execute(
                "select to_regprocedure('mei_email.is_valid_email_address(citext)') is not null"
            )
            if not bool(cur.fetchone()[0]):
                raise RuntimeError("is_valid_email_address(citext) is required before worker start")

            # Small bounded metadata repair.  Never touch the bulk queue here.
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
            out["normalized_campaigns"] = max(int(cur.rowcount or 0), 0)
            conn.commit()

            cur.execute("set statement_timeout='5s'")
            cur.execute(
                """
                select count(*)
                  from mei_email.campanhas
                 where corpo_template ilike '%base pública de CNPJ%'
                    or corpo_template ilike '%base publica de CNPJ%'
                """
            )
            out["legacy_copy_campaigns"] = int(cur.fetchone()[0] or 0)
            cur.execute("select pg_advisory_unlock(%s)", (LOCK_KEY,))
        conn.commit()

    if out["legacy_copy_campaigns"]:
        raise RuntimeError("legacy public-CNPJ campaign copy remains after preflight")
    print(json.dumps(out, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
