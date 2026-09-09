#!/usr/bin/env python3
"""Compatibility entrypoint for obsolete schedulers.

The filename is historical. It does not send messages and it does not define a
quota. It performs one canonical queue-refill pass using the same policy and
queue targets as the production replenisher.
"""
from __future__ import annotations

import sys
from pathlib import Path

import psycopg

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from app.config import settings
from app.queue_manager import carregar_template_html, contar_pendentes, repor_fila_automatica


def enfileirar_fila_canonica() -> int:
    if settings.max_envios_por_dia > settings.brevo_free_hard_cap:
        raise RuntimeError("Teto local excede o contrato Brevo Free.")
    carregar_template_html()
    with psycopg.connect(settings.database_url) as conn:
        antes = contar_pendentes(conn)
        adicionados = repor_fila_automatica(conn)
        depois = contar_pendentes(conn)
    print(
        "COMPAT_QUEUE_REFILL "
        f"before={antes} added={adicionados} after={depois} "
        f"min={settings.queue_min_pending} target={settings.queue_target_pending}",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(enfileirar_fila_canonica())
