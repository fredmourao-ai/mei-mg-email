#!/usr/bin/env python3
"""Constant-time read-only preflight for the nonstop queue-first worker.

Systemd startup must not perform bulk maintenance. Production showed that even
small-looking campaign/queue rewrites can block behind long transactions and
strand the sender in ``activating`` while no Microsoft sender-block exists.

This preflight therefore performs only schema capability checks. Independent
consent, verified MEI source, suppressions, terminal-history replay protection
and legacy-copy normalization are enforced per recipient immediately before
every Graph call by ``worker.safe_entrypoint_v2``. Durable migrations remain
the desired database policy layer, but startup availability does not depend on
running a table-wide mutation.

A transient database connection outage is not a sender block. In that case the
preflight deliberately returns success with a ``deferred`` marker so systemd
can start the worker process; the safe entrypoint then remains alive and retries
the database connection. No Graph send can occur until the DB is reachable and
per-recipient safety checks succeed.
"""
from __future__ import annotations

import json
import os

import psycopg
from dotenv import load_dotenv

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

    try:
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
                    raise RuntimeError(
                        "send-safety columns unavailable: " + ",".join(missing)
                    )

                cur.execute(
                    """
                    select
                      to_regclass('mei_email.envios') is not null,
                      to_regclass('mei_email.campanhas') is not null,
                      to_regclass('mei_email.email_suppressions') is not null,
                      to_regprocedure('mei_email.is_valid_email_address(citext)') is not null
                    """
                )
                envios_ok, campanhas_ok, suppressions_ok, valid_email_ok = cur.fetchone()
                out.update(
                    {
                        "envios": bool(envios_ok),
                        "campanhas": bool(campanhas_ok),
                        "email_suppressions": bool(suppressions_ok),
                        "email_validator": bool(valid_email_ok),
                    }
                )
    except psycopg.OperationalError as exc:
        print(
            json.dumps(
                {
                    "runtime_sender_preflight": "deferred",
                    "reason": "database_unavailable",
                    "error_type": type(exc).__name__,
                },
                sort_keys=True,
            )
        )
        return 0

    if not all(bool(out[k]) for k in ("envios", "campanhas", "email_suppressions", "email_validator")):
        raise RuntimeError("required send-safety schema primitive unavailable")
    print(json.dumps(out, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
