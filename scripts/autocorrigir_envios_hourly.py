#!/usr/bin/env python3
"""Hourly production repair wrapper with an explicit empty-queue guard.

The core repair already recovers legacy states, orphan lots, stalled workers and
sender-block fail-closed behavior. This wrapper closes one remaining blind spot:
when the rolling total is below target and the queue is empty, a failed/deferred
refill must not be reported as healthy. It retries only the existing bounded,
consent-filtered replenisher and never removes a sender-block sentinel.
"""
from __future__ import annotations

import json
import os
import time

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


def _collect() -> dict:
    with psycopg.connect(core.settings.database_url) as conn:
        return core._collect(conn)


def _below_target_and_empty(state: dict) -> bool:
    return (
        int(state.get("sent_24h") or 0) < core.settings.meta_envios_por_dia
        and int(state.get("open_queue") or 0) == 0
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
    # Hold the same global repair lock across the core pass and all bounded
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
