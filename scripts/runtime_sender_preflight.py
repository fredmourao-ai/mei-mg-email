#!/usr/bin/env python3
"""Read-only startup preflight for the first-send worker."""
from __future__ import annotations

import json
import os

import psycopg
from dotenv import load_dotenv

REQUIRED_EMPRESA_COLUMNS = (
    "email",
    "opt_out",
    "situacao_cadastral",
)


def main() -> int:
    load_dotenv("/home/ubuntu/mei-mg-email/.env", override=True)
    database_url = os.environ["DATABASE_URL"]
    out: dict[str, object] = {"runtime_sender_preflight": "ok"}

    with psycopg.connect(database_url, connect_timeout=5) as conn:
        with conn.cursor() as cur:
            cur.execute("set statement_timeout='5s'")
            cur.execute("set lock_timeout='1s'")
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
                raise RuntimeError("required empresa columns unavailable: " + ",".join(missing))

            cur.execute(
                """
                select
                  to_regclass('mei_email.envios') is not null,
                  to_regclass('mei_email.campanhas') is not null,
                  to_regprocedure('mei_email.is_valid_email_address(citext)') is not null
                """
            )
            envios_ok, campanhas_ok, validator_ok = cur.fetchone()
            out.update(
                {
                    "envios": bool(envios_ok),
                    "campanhas": bool(campanhas_ok),
                    "email_validator": bool(validator_ok),
                }
            )

    if not all(bool(out[k]) for k in ("envios", "campanhas", "email_validator")):
        raise RuntimeError("required send schema primitive unavailable")
    print(json.dumps(out, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
