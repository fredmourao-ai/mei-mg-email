#!/usr/bin/env python3
"""Hourly fail-closed verification and repair for the MEI email sender.

The routine never bypasses the rolling quota and never removes a sender-block
sentinel. It repairs only local queue invariants, restarts a stalled worker and
persists before/after evidence for operations. A session advisory lock is held
for the entire repair so overlapping timer/manual runs cannot race each other.
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import subprocess
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

import psycopg
from dotenv import load_dotenv
from psycopg.rows import dict_row

BASE_DIR = Path(__file__).resolve().parents[1]
load_dotenv(BASE_DIR / ".env", override=True)

from app.config import settings
from app.queue_recovery import (
    QUEUE_REPAIR_ADVISORY_LOCK_ID,
    recuperar_fila_legada_e_lotes_orfaos,
    repor_fila_automatica_isolada,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
logger = logging.getLogger("mei_mg_email.autorepair")

WORKER_UNIT = os.getenv(
    "AUTOREPAIR_WORKER_UNIT",
    "mei-mg-email-worker.service",
).strip()
STATE_PATH = Path(
    os.getenv(
        "AUTOREPAIR_STATE_PATH",
        "/var/lib/mei-mg-email/autorepair-state.json",
    )
)
CANONICAL_SENTINEL = Path(
    os.getenv(
        "SENDER_BLOCK_SENTINEL_PATH",
        "/var/lib/mei-mg-email/sender_blocked.pause",
    )
)
LEGACY_SENTINEL = BASE_DIR / "runtime" / "sender_blocked.pause"
STALL_MINUTES = max(int(os.getenv("AUTOREPAIR_STALL_MINUTES", "20")), 10)


def _systemctl(*args: str, timeout: int = 40) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["systemctl", *args],
        text=True,
        capture_output=True,
        timeout=timeout,
        check=False,
    )


def _worker_state() -> str:
    result = _systemctl("is-active", WORKER_UNIT, timeout=10)
    return (result.stdout or result.stderr).strip() or f"exit_{result.returncode}"


def _sentinel_active() -> bool:
    return CANONICAL_SENTINEL.is_file() or LEGACY_SENTINEL.is_file()


@contextmanager
def _repair_lock():
    """Hold the global repair lock for the full execution lifetime."""
    conn = psycopg.connect(settings.database_url)
    acquired = False
    try:
        with conn.cursor() as cur:
            cur.execute(
                "select pg_try_advisory_lock(%s)",
                (QUEUE_REPAIR_ADVISORY_LOCK_ID,),
            )
            acquired = bool(cur.fetchone()[0])
        if not acquired:
            raise RuntimeError("another hourly repair is already active")
        yield
    finally:
        if acquired:
            try:
                with conn.cursor() as cur:
                    cur.execute(
                        "select pg_advisory_unlock(%s)",
                        (QUEUE_REPAIR_ADVISORY_LOCK_ID,),
                    )
            except Exception:
                logger.exception("failed to explicitly release repair advisory lock")
        conn.close()


def _collect(conn: psycopg.Connection) -> dict:
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            select
              count(*) filter (
                where status in ('submitted', 'enviado')
                  and enviado_em >= now() - interval '24 hours'
              ) as sent_24h,
              count(*) filter (
                where status in ('submitted', 'enviado')
                  and enviado_em >= now() - interval '20 minutes'
              ) as sent_20m,
              count(*) filter (
                where status in ('submitted', 'enviado')
                  and enviado_em >= now() - make_interval(mins => %s)
              ) as sent_stall_window,
              max(enviado_em) filter (
                where status in ('submitted', 'enviado')
              ) as last_sent_at,
              count(*) filter (
                where status in ('pendente', 'enviando', 'pending', 'processing')
              ) as open_queue,
              count(*) filter (
                where status in ('pending', 'processing')
              ) as legacy_open,
              count(*) filter (
                where status = 'sender_blocked'
                  and criado_em >= now() - interval '24 hours'
              ) as sender_blocked_24h
            from mei_email.envios
            """,
            (STALL_MINUTES,),
        )
        row = dict(cur.fetchone())

        cur.execute(
            """
            select count(*) as pending_lots
              from mei_email.lotes
             where status = 'pendente'
            """
        )
        row["pending_lots"] = int(cur.fetchone()["pending_lots"] or 0)

        cur.execute(
            """
            select count(*) as orphan_lots
              from mei_email.lotes l
             where l.status <> 'pendente'
               and exists (
                   select 1
                     from mei_email.envios e
                    where e.lote_id = l.id
                      and e.status in (
                          'pendente', 'enviando', 'pending', 'processing'
                      )
               )
            """
        )
        row["orphan_lots"] = int(cur.fetchone()["orphan_lots"] or 0)

        cur.execute(
            """
            select to_regclass('mei_email.envios_externos_cota') is not null as exists
            """
        )
        external_ledger_exists = bool(cur.fetchone()["exists"])
        external_sent_24h = 0
        external_last_sent_at = None
        if external_ledger_exists:
            cur.execute(
                """
                select
                  count(*) filter (
                    where sent_at >= now() - interval '24 hours'
                  ) as sent_24h,
                  max(sent_at) as last_sent_at
                from mei_email.envios_externos_cota
                """
            )
            external = dict(cur.fetchone())
            external_sent_24h = int(external.get("sent_24h") or 0)
            external_last_sent_at = external.get("last_sent_at")

    queue_sent_24h = int(row.get("sent_24h") or 0)
    row["queue_sent_24h"] = queue_sent_24h
    row["external_sent_24h"] = external_sent_24h
    row["sent_24h"] = queue_sent_24h + external_sent_24h

    for key in (
        "sent_20m",
        "sent_stall_window",
        "open_queue",
        "legacy_open",
        "sender_blocked_24h",
    ):
        row[key] = int(row.get(key) or 0)
    if row.get("last_sent_at") is not None:
        row["last_sent_at"] = row["last_sent_at"].isoformat()
    row["external_last_sent_at"] = (
        external_last_sent_at.isoformat() if external_last_sent_at is not None else None
    )
    return row


def _stop_worker() -> None:
    result = _systemctl("stop", WORKER_UNIT, timeout=35)
    if result.returncode == 0 and _worker_state() == "inactive":
        return
    logger.warning(
        "WORKER_STOP_ESCALATION rc=%d stderr=%s",
        result.returncode,
        (result.stderr or "")[-500:],
    )
    _systemctl("kill", "--kill-who=main", "--signal=SIGKILL", WORKER_UNIT)
    time.sleep(3)
    if _worker_state() not in {"inactive", "failed"}:
        raise RuntimeError("worker did not stop for safe queue repair")


def _start_worker() -> None:
    _systemctl("reset-failed", WORKER_UNIT)
    result = _systemctl("start", WORKER_UNIT)
    if result.returncode != 0:
        raise RuntimeError(
            f"worker start failed: {(result.stderr or result.stdout)[-500:]}"
        )
    for _ in range(20):
        if _worker_state() == "active":
            return
        time.sleep(2)
    raise RuntimeError("worker did not become active")


def _persist(payload: dict) -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = STATE_PATH.with_suffix(".tmp")
    tmp.write_text(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str) + "\n",
        encoding="utf-8",
    )
    tmp.replace(STATE_PATH)


def _execute_locked(*, apply: bool) -> dict:
    checked_at = datetime.now(timezone.utc).isoformat()
    worker_before = _worker_state()

    with psycopg.connect(settings.database_url) as conn:
        before = _collect(conn)

    quota_available = before["sent_24h"] < settings.meta_envios_por_dia
    stalled = (
        quota_available
        and before["open_queue"] > 0
        and before["sent_stall_window"] == 0
    )
    queue_broken = before["legacy_open"] > 0 or before["orphan_lots"] > 0
    worker_broken = worker_before != "active"
    repair_needed = queue_broken or worker_broken or stalled
    sentinel_active = _sentinel_active()

    payload = {
        "checked_at": checked_at,
        "mode": "apply" if apply else "check",
        "limits": {
            "target_24h": settings.meta_envios_por_dia,
            "hard_cap_24h": settings.max_envios_por_dia,
            "rate_per_minute": settings.rate_limit_envios_por_minuto,
            "stall_minutes": STALL_MINUTES,
        },
        "worker_before": worker_before,
        "before": before,
        "repair_needed": repair_needed,
        "reasons": {
            "queue_broken": queue_broken,
            "worker_broken": worker_broken,
            "sending_stalled": stalled,
        },
        "sentinel_active": sentinel_active,
        "historical_sender_blocked_24h": before["sender_blocked_24h"],
        "actions": [],
    }

    if not apply:
        payload["result"] = "repair_required" if repair_needed else "healthy"
        _persist(payload)
        return payload

    # Historical sender_blocked rows are telemetry, not a current circuit
    # breaker. Only the canonical/legacy sentinel represents an active block.
    # If the provider denies a new submission systemically, the worker recreates
    # the sentinel immediately and fails closed again.
    if sentinel_active:
        payload["result"] = "blocked_fail_closed"
        _persist(payload)
        raise RuntimeError(
            "current sender-block sentinel present; automatic resume is forbidden"
        )

    if repair_needed:
        _stop_worker()
        payload["actions"].append("worker_stopped_for_repair")
        with psycopg.connect(settings.database_url) as conn:
            recovery = recuperar_fila_legada_e_lotes_orfaos(conn)
            payload["actions"].append(
                {
                    "queue_recovery": {
                        "normalized_legacy": recovery.normalized_legacy,
                        "recovered_stale_sending": recovery.recovered_stale_sending,
                        "quarantined_uncertain_dispatches": recovery.quarantined_uncertain_dispatches,
                        "reopened_lots": recovery.reopened_lots,
                    }
                }
            )

    # Refill only after queue invariants are repaired. The helper has its own
    # statement/lock timeout and cannot freeze the sender connection.
    with psycopg.connect(settings.database_url) as conn:
        mid = _collect(conn)
    if (
        mid["open_queue"] <= settings.queue_min_pending
        and mid["sent_24h"] < settings.meta_envios_por_dia
    ):
        added = repor_fila_automatica_isolada()
        payload["actions"].append({"isolated_refill_added": added})

    if _worker_state() != "active":
        _start_worker()
        payload["actions"].append("worker_started")

    time.sleep(45)
    with psycopg.connect(settings.database_url) as conn:
        after = _collect(conn)
    payload["worker_after"] = _worker_state()
    payload["after"] = after

    if payload["worker_after"] != "active":
        payload["result"] = "failed_worker_inactive"
    elif after["legacy_open"] or after["orphan_lots"]:
        payload["result"] = "failed_queue_invariant"
    elif (
        after["sent_24h"] < settings.meta_envios_por_dia
        and after["open_queue"] > 0
        and after["sent_stall_window"] == 0
    ):
        payload["result"] = "failed_still_stalled"
    else:
        payload["result"] = "healthy_or_progressing"

    _persist(payload)
    if payload["result"].startswith("failed"):
        raise RuntimeError(payload["result"])
    return payload


def execute(*, apply: bool) -> dict:
    with _repair_lock():
        return _execute_locked(apply=apply)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--apply",
        action="store_true",
        help="apply safe queue repair and restart a stalled worker",
    )
    args = parser.parse_args()
    result = execute(apply=args.apply)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
