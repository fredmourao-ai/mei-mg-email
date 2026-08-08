#!/usr/bin/env python3
"""Rotina completa fail-closed: sincroniza, audita e enfileira a meta autorizada.

A sincronizacao de dados e separada do envio e possui trilha em base_sync_runs.
Se a fonte estiver obsoleta, a sincronizacao falha e esta rotina NAO cria fila.
Esta rotina tambem nao contorna limites do Microsoft 365 nem autoriza registros:
somente marketing_autorizado=true pode entrar na campanha.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = BASE_DIR / "scripts"


def run_step(script: str) -> None:
    path = SCRIPTS_DIR / script
    print(f"\n=== {script} ===", flush=True)
    result = subprocess.run(
        [sys.executable, str(path)],
        cwd=str(BASE_DIR),
        text=True,
    )
    if result.returncode != 0:
        raise SystemExit(f"ROTINA_ABORTADA etapa={script} exit={result.returncode}")


def main() -> int:
    run_step("sincronizar_base_diaria.py")
    run_step("auditar_exchange_10000.py")
    run_step("disparar_10000_mei_mg.py")
    print("ROTINA_DIARIA_ENFILEIRADA_COM_SEGURANCA", flush=True)
    print("NOTE=Somente destinatarios ativos e explicitamente autorizados entram na fila.", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
