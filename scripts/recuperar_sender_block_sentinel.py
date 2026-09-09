#!/usr/bin/env python3
"""Retired automatic sender-block recovery entrypoint.

Production is Brevo-only and the canonical sender-block sentinel is never
removed automatically. Recovery requires external provider/endpoint validation
followed by an explicit operator action after ``runtime_sender_preflight.py``
passes. This tombstone cannot send probes or mutate the sentinel.
"""
from __future__ import annotations

import os
from pathlib import Path

SENTINEL_PATH = Path(
    os.getenv(
        "SENDER_BLOCK_SENTINEL_PATH",
        "/var/lib/mei-mg-email/sender_blocked.pause",
    )
)


def main() -> int:
    if not SENTINEL_PATH.is_file():
        print("SENDER_BLOCK_SENTINEL_ABSENT=true")
        return 0
    print("RETIRED_AUTOMATIC_SENDER_RECOVERY=true")
    print("SENDER_BLOCK_SENTINEL_PRESERVED=true")
    print("ACTION_REQUIRED=validate_current_provider_and_public_unsubscribe_then_remove_sentinel_explicitly")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
