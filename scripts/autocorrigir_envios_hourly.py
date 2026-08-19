#!/usr/bin/env python3
"""Hourly production repair wrapper with fail-closed sender recovery.

The core repair recovers legacy states, orphan lots, stalled workers and queue
refill failures. If a sender-block sentinel is present, this wrapper may invoke
the dedicated stale-sentinel recovery probe before taking the repair lock. That
probe is allowed to clear only a local stale sentinel after Exchange reports the
sender unrestricted, a single internal Graph test is accepted, no blocking NDR
appears during the observation window, Exchange still reports unrestricted, and
the test is accounted in the rolling quota ledger. Any failed proof remains
fail-closed.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

import psycopg

import autocorrigir_envios_2h as core

EMPTY_QUEUE_RETRIES = min(
    max(int(os.getenv("AUTOREPAIR_EMPTY_QUEUE_RETRIES", "3")), 1),
    5,
)
EMPTY_QUEUE_RETRY_SECONDS = min(
    max(int(os.getenv("AUTOREPAIR_EMPTY_QUEUE_RETRY_SECONDS", "10")), 2),
    60,
)
SENDER_RECOVERY_TIMEOUT_SECONDS = min(
    max(int(os.getenv("AUTOREPAIR_SENDER_RECOVERY_TIMEOUT_SECONDS", "540")), 180),
    600,
)


def _collect() -> dict:
    with psycopg.connect(core.settings.database_url) as conn:
        return core._collect(conn)


def _below_target_and_empty(state: dict) -> bool:
    return (
        int(state.get("sent_24h") or 0) < core.settings.meta_envios_por_dia
        and int(state.get("open_queue") or 0) == 0
    )


def _attempt_verified_stale_sender_recovery() -> None:
    if not core._sentinel_active():
        return
    script = Path(__file__).resolve().with_name(
        "recuperar_sender_block_sentinel.py"
    )
    completed = subprocess.run(
        [sys.executable, str(script)],
        cwd=core.BASE_DIR,
        capture_output=True,
        text=True,
        timeout=SENDER_RECOVERY_TIMEOUT_SECONDS,
        check=False,
    )
    output = ((completed.stdout or "") + "\n" + (completed.stderr or "")).strip()
    if completed.returncode != 0:
        raise RuntimeError(
            "verified stale sender recovery failed; keeping fail-closed sentinel: "
            + output[-1800:]
        )
    if core._sentinel_active():
        raise RuntimeError(
            "verified stale sender recovery returned success but sentinel remains active"
        )
    if "SENDER_BLOCK_RECOVERY_VERIFIED=true" not in output:
        raise RuntimeError(
            "verified stale sender recovery lacked positive live proof marker"
        )


def _fail_if_sender_blocked(result: dict) -> None:
    if not core._sentinel_active():
        return
    result["sentinel_active"] = True
    result["result"] = "blocked_fail_closed"
    core._persist(result)
    raise RuntimeError(
        "current sender-block sentinel present; automatic resume is forbidden"
    )


def execute() -> dict:
    # Sender recovery is deliberately outside the queue-repair advisory lock:
    # its controlled Graph/NDR verification can take a few minutes and should
    # not block queue invariant maintenance in another process. A surviving
    # sentinel still prevents every send path.
    _attempt_verified_stale_sender_recovery()

    # Hold the global queue-repair lock across the core pass and all bounded
    # empty-queue retries. A manual repair cannot race this execution.
    with core._repair_lock():
        result = core._execute_locked(apply=True)
        state = dict(result.get("after") or result.get("before") or {})
        if not _below_target_and_empty(state):
            return result

        result.setdefault("actions", []).append("empty_queue_below_target_detected")
        queue_sent_before = int(state.get("queue_sent_24h") or 0)

        for attempt in range(1, EMPTY_QUEUE_RETRIES + 1):
            _fail_if_sender_blocked(result)
            added = core.repor_fila_automatica_isolada()
            result["actions"].append(
                {
                    "empty_queue_refill_attempt": attempt,
                    "added": int(added or 0),
                }
            )

            if core._worker_state() != "active":
                core._start_worker()
                result["actions"].append("worker_started_after_empty_queue")

            # A successful refill gets one normal worker observation window.
            if added:
                time.sleep(45)
                break
            if attempt < EMPTY_QUEUE_RETRIES:
                time.sleep(EMPTY_QUEUE_RETRY_SECONDS)

        _fail_if_sender_blocked(result)
        final = _collect()
        result["worker_after"] = core._worker_state()
        result["after"] = final

        if result["worker_after"] != "active":
            result["result"] = "failed_worker_inactive"
        elif final["legacy_open"] or final["orphan_lots"]:
            result["result"] = "failed_queue_invariant"
        elif _below_target_and_empty(final) and int(
            final.get("queue_sent_24h") or 0
        ) <= queue_sent_before:
            result["result"] = "failed_empty_queue_below_target"
        elif (
            int(final.get("sent_24h") or 0) < core.settings.meta_envios_por_dia
            and int(final.get("open_queue") or 0) > 0
            and int(final.get("sent_stall_window") or 0) == 0
        ):
            result["result"] = "failed_still_stalled"
        else:
            result["result"] = "healthy_or_progressing"

        core._persist(result)
        if result["result"].startswith("failed"):
            raise RuntimeError(result["result"])
        return result


def main() -> int:
    result = execute()
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
