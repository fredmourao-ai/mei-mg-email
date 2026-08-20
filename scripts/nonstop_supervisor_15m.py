#!/usr/bin/env python3
"""15-minute throughput supervisor for the MEI sender.

A live process is not sufficient evidence of a healthy sender. This supervisor
checks real submission progress, open queue, strict eligibility and DB blockers.
When a campaign is active, below target, with zero recent sends and an empty
queue, it performs one bounded autoqueue refill using the same consent,
suppression, replay and quota guards as the worker.

It never clears the Microsoft sender-block sentinel, never grants consent,
never relaxes eligibility and never sends mail directly.
"""
from __future__ import annotations

import json
import os
import subprocess
import time
from pathlib import Path

import psycopg
from dotenv import load_dotenv
from psycopg.rows import dict_row

BASE_DIR = Path(__file__).resolve().parents[1]
load_dotenv(BASE_DIR / ".env", override=True)

from app.config import settings
from app.queue_recovery import repor_fila_automatica_isolada

CANONICAL_SENTINEL = Path(
    os.getenv("SENDER_BLOCK_SENTINEL_PATH", "/var/lib/mei-mg-email/sender_blocked.pause")
)
LEGACY_SENTINEL = BASE_DIR / "runtime" / "sender_blocked.pause"
WORKER_UNIT = "mei-mg-email-worker.service"
STATE_PATH = Path(
    os.getenv(
        "THROUGHPUT_SUPERVISOR_STATE_PATH",
        "/var/lib/mei-mg-email/throughput-supervisor-state.json",
    )
)


def _systemctl(*args: str, timeout: int = 20) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["systemctl", *args],
        text=True,
        capture_output=True,
        timeout=timeout,
        check=False,
    )


def _state() -> str:
    cp = _systemctl("is-active", WORKER_UNIT, timeout=8)
    return (cp.stdout or cp.stderr).strip() or f"exit_{cp.returncode}"


def _sentinel() -> bool:
    return CANONICAL_SENTINEL.is_file() or LEGACY_SENTINEL.is_file()


def _ensure_worker_active(result: dict[str, object]) -> None:
    enabled = _systemctl("is-enabled", WORKER_UNIT, timeout=8)
    if (enabled.stdout or "").strip() != "enabled":
        cp = _systemctl("enable", WORKER_UNIT, timeout=20)
        if cp.returncode != 0:
            raise RuntimeError(f"worker enable failed: {(cp.stderr or cp.stdout)[-500:]}")
        result["actions"].append("worker_enabled")

    if _state() != "active":
        _systemctl("reset-failed", WORKER_UNIT, timeout=10)
        cp = _systemctl("restart", WORKER_UNIT, timeout=35)
        if cp.returncode != 0:
            raise RuntimeError(f"worker restart failed: {(cp.stderr or cp.stdout)[-800:]}")
        result["actions"].append("worker_restarted")


def _collect() -> dict[str, object]:
    with psycopg.connect(os.environ["DATABASE_URL"], connect_timeout=5, row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            cur.execute("set statement_timeout='8s'")
            cur.execute(
                """
                select
                  count(*) filter (
                    where status::text in ('submitted','enviado')
                      and enviado_em >= now() - interval '24 hours'
                  ) as sent_24h,
                  count(*) filter (
                    where status::text in ('submitted','enviado')
                      and enviado_em >= now() - interval '10 minutes'
                  ) as sent_10m,
                  count(*) filter (
                    where status::text in ('pendente','enviando','pending','processing')
                  ) as open_queue,
                  max(enviado_em) filter (
                    where status::text in ('submitted','enviado')
                  ) as last_sent_at
                from mei_email.envios
                """
            )
            row = dict(cur.fetchone())
            cur.execute(
                """
                select exists (
                  select 1 from mei_email.campanhas
                   where status::text in ('enfileirada','em_andamento')
                ) as active_campaign
                """
            )
            row["active_campaign"] = bool(cur.fetchone()["active_campaign"])
    for key in ("sent_24h", "sent_10m", "open_queue"):
        row[key] = int(row.get(key) or 0)
    if row.get("last_sent_at") is not None:
        row["last_sent_at"] = row["last_sent_at"].isoformat()
    return row


def _strict_eligible_probe() -> dict[str, object]:
    try:
        with psycopg.connect(os.environ["DATABASE_URL"], connect_timeout=5) as conn:
            with conn.cursor() as cur:
                cur.execute("set statement_timeout='8s'")
                cur.execute("select exists(select 1 from mei_email.vw_empresas_elegiveis limit 1)")
                return {"state": "ok", "available": bool(cur.fetchone()[0])}
    except (psycopg.errors.QueryCanceled, psycopg.OperationalError) as exc:
        return {"state": "query_error", "error": f"{type(exc).__name__}: {str(exc)[:300]}"}


def _lock_diagnostics() -> dict[str, int]:
    try:
        with psycopg.connect(os.environ["DATABASE_URL"], connect_timeout=5, row_factory=dict_row) as conn:
            with conn.cursor() as cur:
                cur.execute("set statement_timeout='5s'")
                cur.execute(
                    """
                    select
                      count(*) filter (where not granted) as lock_waiters,
                      count(*) filter (where locktype='advisory' and granted) as advisory_locks
                    from pg_locks
                    """
                )
                row = dict(cur.fetchone())
                cur.execute(
                    """
                    select count(*) as long_active
                      from pg_stat_activity
                     where state = 'active'
                       and pid <> pg_backend_pid()
                       and query_start < now() - interval '30 seconds'
                    """
                )
                row["long_active"] = int(cur.fetchone()["long_active"] or 0)
        return {
            "lock_waiters": int(row.get("lock_waiters") or 0),
            "advisory_locks": int(row.get("advisory_locks") or 0),
            "long_active": int(row.get("long_active") or 0),
        }
    except Exception:
        return {"lock_waiters": -1, "advisory_locks": -1, "long_active": -1}


def _persist(result: dict[str, object]) -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = STATE_PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps(result, sort_keys=True, default=str) + "\n", encoding="utf-8")
    tmp.replace(STATE_PATH)


def main() -> int:
    result: dict[str, object] = {
        "checked_at": time.time(),
        "sender_block_sentinel": _sentinel(),
        "worker_before": _state(),
        "actions": [],
    }

    if result["sender_block_sentinel"]:
        if result["worker_before"] not in {"inactive", "failed"}:
            _systemctl("stop", WORKER_UNIT, timeout=35)
            result["actions"].append("worker_stopped_for_current_sender_block")
        result["worker_after"] = _state()
        result["result"] = "blocked_fail_closed"
        _persist(result)
        print(json.dumps(result, sort_keys=True))
        return 0

    _ensure_worker_active(result)
    before = _collect()
    result["before"] = before

    below_target = int(before["sent_24h"]) < int(settings.meta_envios_por_dia)
    stalled = bool(before["active_campaign"]) and below_target and int(before["sent_10m"]) == 0
    empty = int(before["open_queue"]) == 0

    if stalled and empty:
        result["actions"].append("throughput_stall_empty_queue_detected")
        probe = _strict_eligible_probe()
        result["strict_eligibility"] = probe
        if probe.get("state") == "query_error":
            result["db_diagnostics"] = _lock_diagnostics()
        added = repor_fila_automatica_isolada(
            statement_timeout_seconds=60,
            lock_timeout_seconds=5,
        )
        result["actions"].append({"bounded_autoqueue_refill_added": int(added or 0)})
        if added:
            time.sleep(8)
        after = _collect()
        result["after"] = after
    else:
        result["after"] = before

    after = result["after"]
    result["worker_after"] = _state()

    if result["worker_after"] != "active":
        result["result"] = "degraded_worker_inactive"
    elif bool(after["active_campaign"]) and int(after["sent_24h"]) < int(settings.meta_envios_por_dia):
        if int(after["sent_10m"]) > 0:
            result["result"] = "healthy_real_throughput"
        elif int(after["open_queue"]) > 0:
            result["result"] = "degraded_queue_present_no_recent_send"
        else:
            probe = result.get("strict_eligibility") or _strict_eligible_probe()
            result["strict_eligibility"] = probe
            if probe.get("state") == "query_error":
                result["db_diagnostics"] = result.get("db_diagnostics") or _lock_diagnostics()
                result["result"] = "degraded_eligibility_query_error"
            elif probe.get("available") is True:
                result["result"] = "degraded_empty_queue_with_eligible_candidates"
            else:
                result["result"] = "degraded_authorized_pool_exhausted"
    else:
        result["result"] = "healthy_target_or_no_active_campaign"

    _persist(result)
    print(json.dumps(result, sort_keys=True))
    return 1 if str(result["result"]).startswith("degraded") else 0


if __name__ == "__main__":
    raise SystemExit(main())
