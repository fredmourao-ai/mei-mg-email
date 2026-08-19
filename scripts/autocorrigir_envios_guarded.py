#!/usr/bin/env python3
"""Run hourly autorepair without ever stranding a healthy sender worker.

The hourly repair may intentionally stop the worker while it repairs queue
invariants. If an unexpected exception happens after that stop, this wrapper
restores the worker only when no sender-block sentinel is active. The worker
itself still enforces rolling quota, consent/opt-out and suppression guards.
"""
from __future__ import annotations

import logging

import autocorrigir_envios_2h as core
import autocorrigir_envios_hourly as hourly

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("mei_mg_email.autorepair_guard")


def main() -> int:
    try:
        return hourly.main()
    finally:
        if core._sentinel_active():
            logger.critical(
                "autorepair ended with sender-block sentinel active; worker remains fail-closed"
            )
        elif core._worker_state() != "active":
            logger.error(
                "autorepair left worker inactive without sender-block sentinel; restoring worker"
            )
            core._start_worker()


if __name__ == "__main__":
    raise SystemExit(main())
