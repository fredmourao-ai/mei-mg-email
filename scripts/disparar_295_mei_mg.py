#!/usr/bin/env python3
"""Compatibilidade com o antigo agendador de 295/dia.

O limite operacional atual e controlado por scripts/disparar_10000_mei_mg.py.
Manter este arquivo evita quebrar cron/agendadores antigos enquanto a VM e
atualizada.
"""
from disparar_10000_mei_mg import enfileirar_ate_10000_mei_mg


if __name__ == "__main__":
    print("AVISO: disparar_295_mei_mg.py e legado; usando controlador de ate 10000/24h.", flush=True)
    raise SystemExit(enfileirar_ate_10000_mei_mg())
