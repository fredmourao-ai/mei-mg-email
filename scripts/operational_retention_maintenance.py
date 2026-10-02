#!/usr/bin/env python3
"""Bounded operational retention for the MEI-MG recipient base.

Dry-run is the default. Apply mode is fail-closed: the sender pause sentinel must
exist and the worker must not be active. The send/event history is preserved;
only rows in mei_email.empresas are removed after durable suppression is written.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
from pathlib import Path

import psycopg
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
PAUSE_SENTINEL = Path("/var/lib/mei-mg-email/sender_blocked.pause")
WORKER_UNIT = "mei-mg-email-worker.service"
ADVISORY_LOCK_KEY = 74821002

load_dotenv(ROOT / ".env")

TERMINAL_SQL = r"""
WITH candidates AS MATERIALIZED (
    SELECT DISTINCT ON (e.cnpj)
           e.cnpj,
           e.email,
           CASE
             WHEN v.status::text IN ('submitted','enviado','delivered') THEN 'sent'
             WHEN v.status::text = 'bounce_permanent' THEN 'hard_bounce'
           END AS reason,
           true AS suppress_cnpj,
           true AS suppress_email
      FROM mei_email.envios v
      JOIN mei_email.empresas e ON e.cnpj = v.cnpj
     WHERE v.status::text IN
           ('submitted','enviado','delivered','bounce_permanent')
     ORDER BY e.cnpj,
              CASE
                WHEN v.status::text IN ('submitted','enviado','delivered') THEN 0
                WHEN v.status::text = 'bounce_permanent' THEN 1
              END,
              v.criado_em DESC
     LIMIT %s
)
SELECT cnpj, email, reason, suppress_cnpj, suppress_email FROM candidates
"""

FILTER_SQL = r"""
WITH candidates AS MATERIALIZED (
    SELECT e.cnpj,
           e.email,
           CASE
             WHEN e.opt_out THEN 'opt_out'
             WHEN e.situacao_cadastral <> 'ATIVA' THEN 'filter_inactive'
             WHEN e.email IS NULL OR btrim(e.email::text) = '' THEN 'filter_email_missing'
             WHEN NOT mei_email.is_valid_email_address(e.email) THEN 'filter_email_invalid'
             WHEN position('contabil' in lower(btrim(e.email::text))) > 0 THEN 'filter_email_contabil'
           END AS reason,
           true AS suppress_cnpj,
           CASE
             WHEN e.opt_out THEN true
             WHEN e.email IS NULL OR btrim(e.email::text) = '' THEN false
             WHEN NOT mei_email.is_valid_email_address(e.email) THEN true
             WHEN position('contabil' in lower(btrim(e.email::text))) > 0 THEN true
             ELSE false
           END AS suppress_email
      FROM mei_email.empresas e
     WHERE e.opt_out
        OR e.situacao_cadastral <> 'ATIVA'
        OR e.email IS NULL
        OR btrim(e.email::text) = ''
        OR NOT mei_email.is_valid_email_address(e.email)
        OR position('contabil' in lower(btrim(e.email::text))) > 0
     ORDER BY e.cnpj
     LIMIT %s
)
SELECT cnpj, email, reason, suppress_cnpj, suppress_email FROM candidates
"""

SHARED_EMAIL_SQL = r"""
WITH shared AS MATERIALIZED (
    SELECT lower(btrim(email::text)) AS email_norm
      FROM mei_email.empresas
     WHERE email IS NOT NULL AND btrim(email::text) <> ''
     GROUP BY lower(btrim(email::text))
    HAVING count(DISTINCT cnpj) > 2
     ORDER BY lower(btrim(email::text))
     LIMIT %s
),
candidates AS MATERIALIZED (
    SELECT e.cnpj, e.email, 'filter_shared_email'::text AS reason,
           true AS suppress_cnpj, true AS suppress_email
      FROM mei_email.empresas e
      JOIN shared s
        ON lower(btrim(e.email::text)) = s.email_norm
     ORDER BY e.cnpj
     LIMIT %s
)
SELECT cnpj, email, reason, suppress_cnpj, suppress_email FROM candidates
"""

def _worker_active() -> bool:
    cp = subprocess.run(
        ["systemctl", "is-active", "--quiet", WORKER_UNIT],
        check=False,
        timeout=10,
    )
    return cp.returncode == 0


def _require_safe_apply() -> None:
    if not PAUSE_SENTINEL.exists():
        raise RuntimeError("sender pause sentinel is absent; refusing retention apply")
    if _worker_active():
        raise RuntimeError("sender worker is active; refusing retention apply")


def _fetch_candidates(cur, phase: str, limit: int):
    sql = {"terminal": TERMINAL_SQL, "filter": FILTER_SQL, "shared": SHARED_EMAIL_SQL}[phase]
    params = (limit, limit) if phase == "shared" else (limit,)
    cur.execute(sql, params)
    return cur.fetchall()


def _apply_candidates(conn: psycopg.Connection, rows) -> int:
    if not rows:
        return 0
    with conn.transaction():
        with conn.cursor() as cur:
            for cnpj, email, reason, suppress_cnpj, suppress_email in rows:
                cur.execute(
                    """
                    SELECT mei_email.register_operational_suppression(
                        %s, %s::public.citext, %s, 'canonical_retention_maintenance', NULL, now()
                    )
                    """,
                    (
                        str(cnpj) if suppress_cnpj else None,
                        str(email) if suppress_email and email is not None else None,
                        reason,
                    ),
                )
            cnpjs = [row[0] for row in rows]
            cur.execute(
                "DELETE FROM mei_email.empresas WHERE cnpj = ANY(%s) RETURNING cnpj",
                (cnpjs,),
            )
            deleted = len(cur.fetchall())
            if deleted != len(rows):
                raise RuntimeError(
                    f"retention batch mismatch candidates={len(rows)} deleted={deleted}"
                )
    return deleted


def run(*, apply: bool, batch_size: int, max_batches: int) -> dict:
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        raise RuntimeError("DATABASE_URL missing")
    if apply:
        _require_safe_apply()

    result = {
        "mode": "apply" if apply else "dry-run",
        "batch_size": batch_size,
        "max_batches": max_batches,
        "phases": {},
        "deleted_total": 0,
    }
    with psycopg.connect(database_url, connect_timeout=5, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT pg_try_advisory_lock(%s)", (ADVISORY_LOCK_KEY,))
            if not cur.fetchone()[0]:
                raise RuntimeError("another retention maintenance execution holds the advisory lock")
        try:
            for phase in ("terminal", "filter", "shared"):
                phase_deleted = 0
                phase_batches = 0
                for _ in range(max_batches):
                    if apply:
                        _require_safe_apply()
                    with conn.cursor() as cur:
                        rows = _fetch_candidates(cur, phase, batch_size)
                    if not rows:
                        break
                    phase_batches += 1
                    if not apply:
                        break
                    phase_deleted += _apply_candidates(conn, rows)
                result["phases"][phase] = {
                    "batches": phase_batches,
                    "candidate_count_last_batch": len(rows) if 'rows' in locals() else 0,
                    "deleted": phase_deleted,
                }
                result["deleted_total"] += phase_deleted
        finally:
            with conn.cursor() as cur:
                cur.execute("SELECT pg_advisory_unlock(%s)", (ADVISORY_LOCK_KEY,))
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--batch-size", type=int, default=1000)
    parser.add_argument("--max-batches", type=int, default=250)
    args = parser.parse_args()
    if not 1 <= args.batch_size <= 5000:
        raise SystemExit("batch-size must be between 1 and 5000")
    if not 1 <= args.max_batches <= 1000:
        raise SystemExit("max-batches must be between 1 and 1000")
    result = run(apply=args.apply, batch_size=args.batch_size, max_batches=args.max_batches)
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
