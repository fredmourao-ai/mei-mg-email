#!/usr/bin/env python3
from __future__ import annotations

import logging
import os
import time
from pathlib import Path

import psycopg
from dotenv import load_dotenv

from app.queue_manager import repor_fila_automatica

ROOT = Path(__file__).resolve().parents[1]
CANONICAL_PAUSE = Path("/var/lib/mei-mg-email/sender_blocked.pause")
LEGACY_PAUSE = ROOT / "runtime" / "sender_blocked.pause"
POLL_SECONDS = 5

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("mei_mg_email.queue_replenisher")


def run_once(database_url: str) -> int:
    if CANONICAL_PAUSE.exists() or LEGACY_PAUSE.exists():
        log.warning("REPLENISHER_PAUSED sender-block sentinel present")
        return 0
    with psycopg.connect(database_url, connect_timeout=5) as conn:
        added = repor_fila_automatica(conn)
    if added:
        log.warning("REPLENISHER_ADDED=%d", added)
    return added


def main() -> int:
    load_dotenv(ROOT / ".env")
    database_url = os.environ["DATABASE_URL"]
    once = os.getenv("QUEUE_REPLENISHER_ONCE") == "1"
    while True:
        try:
            run_once(database_url)
        except Exception:
            log.exception("replenisher cycle failed")
        if once:
            return 0
        time.sleep(POLL_SECONDS)


if __name__ == "__main__":
    raise SystemExit(main())
