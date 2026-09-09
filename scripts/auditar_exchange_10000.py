#!/usr/bin/env python3
"""Retired Microsoft Exchange auditor retained only as a fail-closed tombstone.

Production delivery is Brevo-only. Use ``scripts/runtime_policy_guard.py`` and
``scripts/monitor_operacao.py`` for current operational validation.
"""
from __future__ import annotations


def main() -> int:
    print("RETIRED_MICROSOFT_EXCHANGE_AUDITOR")
    print("Use scripts/runtime_policy_guard.py and scripts/monitor_operacao.py.")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
