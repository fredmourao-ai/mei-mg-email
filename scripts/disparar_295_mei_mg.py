#!/usr/bin/env python3
"""Compatibility entrypoint for the obsolete scheduler name.

No independent quota or sending rule lives here. All eligibility and queue
behavior is delegated to the canonical queue refill implementation.
"""
from disparar_10000_mei_mg import enfileirar_fila_canonica


if __name__ == "__main__":
    print("COMPAT_ONLY: using canonical queue refill; no legacy quota applies.", flush=True)
    raise SystemExit(enfileirar_fila_canonica())
