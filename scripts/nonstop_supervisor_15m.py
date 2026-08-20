#!/usr/bin/env python3
"""Lightweight 15-minute availability supervisor for the MEI sender.

The supervisor never stops a healthy worker and never performs table-wide
queue/statistics scans. Its only global stop condition is a current sender-block
sentinel produced by the Microsoft send path. Every other local availability
failure is repaired by enabling/restarting the worker and letting the queue-first
process perform its bounded per-cycle recovery.

Consent, opt-out, suppressions, replay guards, quota and provider restrictions
remain enforced in the worker itself. This process never clears a sentinel,
grants consent, queues a new recipient, changes a provider limit, or sends mail.
"""
from __future__ import annotations

import json
import os
import subprocess
import time
from pathlib import Path

import psycopg
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parents[1]
CANONICAL_SENTINEL = Path(
    os.getenv("SENDER_BLOCK_SENTINEL_PATH", "/var/lib/mei-mg-email/sender_blocked.pause")
)
LEGACY_SENTINEL = BASE_DIR / "runtime" / "sender_blocked.pause"
WORKER_UNIT = "mei-mg-email-worker.service"


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


def _db_ping() -> None:
    load_dotenv(BASE_DIR / ".env", override=True)
    with psycopg.connect(os.environ["DATABASE_URL"], connect_timeout=5) as conn:
        with conn.cursor() as cur:
            cur.execute("set statement_timeout='3s'")
            cur.execute("select 1")
            if int(cur.fetchone()[0]) != 1:
                raise RuntimeError("unexpected database ping result")


def main() -> int:
    result: dict[str, object] = {
        "checked_at": time.time(),
        "sender_block_sentinel": _sentinel(),
        "worker_before": _state(),
        "actions": [],
    }

    # A current Microsoft sender-block sentinel is the one legitimate global
    # stop. Never clear it here and never probe around it with a send.
    if result["sender_block_sentinel"]:
        if result["worker_before"] not in {"inactive", "failed"}:
            _systemctl("stop", WORKER_UNIT, timeout=35)
            result["actions"].append("worker_stopped_for_current_sender_block")
        result["worker_after"] = _state()
        result["result"] = "blocked_fail_closed"
        print(json.dumps(result, sort_keys=True))
        return 0

    # Database/network startup is recoverable. Do not turn it into a global
    # sender block; fail this oneshot so the next timer pass can retry while
    # systemd's own Restart=always policy keeps attempting the worker.
    _db_ping()

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

    for _ in range(12):
        if _sentinel():
            _systemctl("stop", WORKER_UNIT, timeout=35)
            result["sender_block_sentinel"] = True
            result["worker_after"] = _state()
            result["result"] = "blocked_during_restart"
            print(json.dumps(result, sort_keys=True))
            return 0
        if _state() == "active":
            result["worker_after"] = "active"
            result["result"] = "healthy_or_repaired"
            print(json.dumps(result, sort_keys=True))
            return 0
        time.sleep(5)

    result["worker_after"] = _state()
    raise RuntimeError("worker did not become active within bounded supervisor window")


if __name__ == "__main__":
    raise SystemExit(main())
