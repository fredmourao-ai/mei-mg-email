#!/usr/bin/env python3
"""Hourly compatibility wrapper for the canonical fail-closed autorepair.

There is one repair implementation: ``autocorrigir_envios_2h``. This wrapper
must never remove the sender-block sentinel, send a probe message, relax the
recipient policy, or define a second queue/quota contract.
"""
from __future__ import annotations

import json

import autocorrigir_envios_2h as core


def execute() -> dict:
    return core.execute(apply=True)


def main() -> int:
    result = execute()
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
