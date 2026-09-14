#!/usr/bin/env python3
"""15-minute throughput supervisor for the MEI sender.

A live process is not sufficient evidence of a healthy sender. This supervisor
checks real submission progress, open queue, strict eligibility and DB blockers.
When a campaign is active, below target, with zero recent sends and an empty
queue, it performs one bounded autoqueue refill using the same consent,
suppression, replay and quota guards as the worker.

It also treats the PostgreSQL runtime as part of sender availability. If the DB
container is unavailable while there is no Microsoft sender-block sentinel, the
supervisor first restarts the existing DB container without recreating it. Only
if the container is absent or cannot be started does it fall back to
``docker compose up -d db``. This avoids leaving PostgreSQL stopped if a compose
recreate is interrupted. It never stops a healthy worker merely for diagnostics.

It never clears the Microsoft sender-block sentinel, never grants consent,
never relaxes eligibility and never sends mail directly.
"""
from __future__ import annotations

import json
import os
import signal
import subprocess
import time
from urllib.error import URLError
from urllib.request import urlopen
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
API_UNIT = "mei-mg-email-api.service"
API_HEALTH_URL = "http://127.0.0.1:8010/health"
API_UNIT_SOURCE = BASE_DIR / "deploy" / "systemd" / API_UNIT
API_UNIT_INSTALLED = Path("/etc/systemd/system") / API_UNIT
DB_CONTAINER = os.getenv("MEI_DB_CONTAINER", "mei-mg-email-db")
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


def _api_health() -> tuple[bool, str]:
    try:
        with urlopen(API_HEALTH_URL, timeout=4) as response:
            body = response.read(200).decode("utf-8", "replace")
            ok = int(response.status) == 200 and '"status":"ok"' in body.replace(" ", "")
            return ok, f"http_{response.status}"
    except (URLError, OSError, ValueError) as exc:
        return False, f"{type(exc).__name__}: {str(exc)[:200]}"


def _api_state() -> str:
    cp = _systemctl("is-active", API_UNIT, timeout=8)
    return (cp.stdout or cp.stderr).strip() or f"exit_{cp.returncode}"


def _sync_api_unit(result: dict[str, object]) -> None:
    if not API_UNIT_SOURCE.is_file():
        return
    source = API_UNIT_SOURCE.read_bytes()
    installed = API_UNIT_INSTALLED.read_bytes() if API_UNIT_INSTALLED.is_file() else b""
    if source == installed:
        return
    API_UNIT_INSTALLED.write_bytes(source)
    cp = _systemctl("daemon-reload", timeout=20)
    if cp.returncode != 0:
        raise RuntimeError(f"api daemon-reload failed: {(cp.stderr or cp.stdout)[-500:]}")
    result["actions"].append("api_unit_synced")


def _api_orphan_pids() -> list[int]:
    pids: list[int] = []
    for proc in Path("/proc").iterdir():
        if not proc.name.isdigit():
            continue
        try:
            cmd = (proc / "cmdline").read_bytes().replace(b"\x00", b" ").decode("utf-8", "replace")
        except OSError:
            continue
        if "uvicorn app.main:app" in cmd and "--port 8010" in cmd:
            pids.append(int(proc.name))
    return pids


def _ensure_api_active(result: dict[str, object]) -> bool:
    _sync_api_unit(result)
    before_state = _api_state()
    before_ok, before_detail = _api_health()
    result["api_before"] = {"systemd": before_state, "api_health": before_ok, "detail": before_detail}
    if before_state == "active" and before_ok:
        result["api_after"] = result["api_before"]
        return True

    if before_state != "active":
        orphan_pids = _api_orphan_pids()
        if orphan_pids:
            for pid in orphan_pids:
                os.kill(pid, signal.SIGTERM)
            result["actions"].append("api_orphan_terminated")
            time.sleep(2)

    enabled = _systemctl("is-enabled", API_UNIT, timeout=8)
    if (enabled.stdout or "").strip() != "enabled":
        cp = _systemctl("enable", API_UNIT, timeout=20)
        if cp.returncode != 0:
            result["api_after"] = {"systemd": _api_state(), "api_health": False, "detail": "enable_failed"}
            return False
        result["actions"].append("api_enabled")

    _systemctl("reset-failed", API_UNIT, timeout=10)
    cp = _systemctl("restart", API_UNIT, timeout=35)
    if cp.returncode != 0:
        result["api_after"] = {"systemd": _api_state(), "api_health": False, "detail": (cp.stderr or cp.stdout)[-500:]}
        return False
    result["actions"].append("api_restarted")
    for _ in range(10):
        time.sleep(1)
        ok, detail = _api_health()
        state = _api_state()
        if state == "active" and ok:
            result["api_after"] = {"systemd": state, "api_health": True, "detail": detail}
            return True
    ok, detail = _api_health()
    result["api_after"] = {"systemd": _api_state(), "api_health": ok, "detail": detail}
    return False


def _db_probe() -> tuple[bool, str]:
    try:
        with psycopg.connect(os.environ["DATABASE_URL"], connect_timeout=4) as conn:
            with conn.cursor() as cur:
                cur.execute("select 1")
                if cur.fetchone()[0] == 1:
                    return True, "ok"
        return False, "probe_returned_no_row"
    except Exception as exc:
        return False, f"{type(exc).__name__}: {str(exc)[:400]}"


def _run_process(args: list[str], *, timeout: int, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        cwd=cwd,
        text=True,
        capture_output=True,
        timeout=timeout,
        check=False,
    )


def _wait_for_db(result: dict[str, object], label: str, attempts: int = 10) -> bool:
    detail = "not_probed"
    for attempt in range(1, attempts + 1):
        time.sleep(2)
        available, detail = _db_probe()
        if available:
            result["actions"].append("db_recovered")
            result.setdefault("db_recovery", {}).update(
                {"success": True, "method": label, "ready_attempt": attempt}
            )
            result["db_after"] = {"available": True, "detail": detail}
            return True
    result["db_after"] = {"available": False, "detail": detail}
    return False


def _ensure_db_available(result: dict[str, object]) -> bool:
    available, detail = _db_probe()
    result["db_before"] = {"available": available, "detail": detail}
    if available:
        result["db_after"] = result["db_before"]
        return True

    result["actions"].append("db_unavailable_detected")
    result["db_recovery"] = {"attempted": True}

    try:
        inspect = _run_process(
            ["docker", "inspect", DB_CONTAINER],
            timeout=10,
        )
        result["db_recovery"]["container_present"] = inspect.returncode == 0
        if inspect.returncode == 0:
            _run_process(
                ["docker", "update", "--restart", "unless-stopped", DB_CONTAINER],
                timeout=10,
            )
            start = _run_process(["docker", "start", DB_CONTAINER], timeout=20)
            result["db_recovery"].update(
                {
                    "docker_start_rc": start.returncode,
                    "docker_start_stdout": (start.stdout or "")[-500:],
                    "docker_start_stderr": (start.stderr or "")[-500:],
                }
            )
            if start.returncode == 0 and _wait_for_db(result, "docker_start", attempts=10):
                return True
    except Exception as exc:
        result["db_recovery"]["docker_start_error"] = (
            f"{type(exc).__name__}: {str(exc)[:500]}"
        )

    try:
        compose = _run_process(
            ["docker", "compose", "up", "-d", "db"],
            cwd=BASE_DIR,
            timeout=45,
        )
        result["db_recovery"].update(
            {
                "compose_rc": compose.returncode,
                "compose_stdout": (compose.stdout or "")[-800:],
                "compose_stderr": (compose.stderr or "")[-800:],
            }
        )
    except Exception as exc:
        result["db_recovery"].update(
            {
                "success": False,
                "compose_error": f"{type(exc).__name__}: {str(exc)[:500]}",
            }
        )
        result["db_after"] = {"available": False, "detail": "compose_start_exception"}
        return False

    if compose.returncode != 0:
        result["db_recovery"]["success"] = False
        result["db_after"] = {"available": False, "detail": "compose_start_failed"}
        return False

    if _wait_for_db(result, "docker_compose_up", attempts=15):
        return True

    result["db_recovery"]["success"] = False
    return False


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
                    where provider_message_id like 'brevo:%'
                      and submitted_at >= statement_timestamp() - interval '24 hours'
                  ) as quota_24h,
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
            cur.execute("select to_regclass('mei_email.envios_externos_cota')")
            if cur.fetchone()[0] is not None:
                cur.execute("""
                    select count(*) from mei_email.envios_externos_cota
                     where (provider_message_id like 'brevo:%' or source like 'brevo%')
                       and sent_at >= statement_timestamp() - interval '24 hours'
                """)
                row["quota_24h"] = int(row.get("quota_24h") or 0) + int(cur.fetchone()[0] or 0)
            cur.execute(
                """
                select exists (
                  select 1 from mei_email.campanhas
                   where status::text in ('enfileirada','em_andamento')
                ) as active_campaign
                """
            )
            row["active_campaign"] = bool(cur.fetchone()["active_campaign"])
    for key in ("quota_24h", "sent_24h", "sent_10m", "open_queue"):
        row[key] = int(row.get(key) or 0)
    if row.get("last_sent_at") is not None:
        row["last_sent_at"] = row["last_sent_at"].isoformat()
    return row


def _strict_eligible_probe() -> dict[str, object]:
    try:
        with psycopg.connect(os.environ["DATABASE_URL"], connect_timeout=5) as conn:
            with conn.cursor() as cur:
                cur.execute("set statement_timeout='5s'")
                cur.execute("""
                    select exists(
                      select 1 from mei_email.empresas e
                       where e.situacao_cadastral='ATIVA'
                         and e.email is not null
                         and btrim(e.email::text)<>''
                         and mei_email.is_valid_email_address(e.email)
                         and position('contabil' in lower(btrim(e.email::text)))=0
                       limit 1
                    )
                """)
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
    try:
        api_ok = _ensure_api_active(result)
    except Exception as exc:
        api_ok = False
        result["api_after"] = {"systemd": _api_state(), "api_health": False, "detail": f"{type(exc).__name__}: {str(exc)[:500]}"}

    if result["sender_block_sentinel"]:
        if result["worker_before"] not in {"inactive", "failed"}:
            _systemctl("stop", WORKER_UNIT, timeout=35)
            result["actions"].append("worker_stopped_for_current_sender_block")
        result["worker_after"] = _state()
        result["result"] = "blocked_fail_closed"
        _persist(result)
        print(json.dumps(result, sort_keys=True))
        return 0

    if not _ensure_db_available(result):
        result["worker_after"] = _state()
        result["result"] = "degraded_db_unavailable"
        _persist(result)
        print(json.dumps(result, sort_keys=True))
        return 1

    _ensure_worker_active(result)
    before = _collect()
    result["before"] = before

    below_target = int(before["quota_24h"]) < int(settings.meta_envios_por_dia)
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

    if not api_ok:
        result["result"] = "degraded_api_unavailable_or_unsupervised"
    elif result["worker_after"] != "active":
        result["result"] = "degraded_worker_inactive"
    elif bool(after["active_campaign"]) and int(after["quota_24h"]) < int(settings.meta_envios_por_dia):
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
