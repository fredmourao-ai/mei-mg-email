#!/usr/bin/env python3
"""Compatibilidade: executa uma reposicao do buffer continuo da fila MEI/MG.

A meta de 9.950 continua sendo uma cota de ENVIO em janela movel de 24 horas.
A fila e um estoque independente, mantido entre QUEUE_MIN_PENDING e
QUEUE_TARGET_PENDING pelo proprio worker. Enfileirar nao consome a cota antes
da submissao ao Microsoft Graph.
"""
from __future__ import annotations

import sys
from pathlib import Path

import psycopg

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from app.config import settings
from app.queue_manager import (
    carregar_template_html,
    contar_pendentes,
    quantidade_para_repor,
    repor_fila_automatica,
)

EXPECTED_DAILY_TARGET = 9950


def capacidade_para_nova_fila() -> tuple[int, int, int]:
    with psycopg.connect(settings.database_url) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                select count(*)
                  from mei_email.envios
                 where status in ('submitted', 'enviado')
                   and enviado_em >= now() - interval '24 hours'
                """
            )
            consumidos_24h = int(cur.fetchone()[0] or 0)
        pendentes = contar_pendentes(conn)
    return quantidade_para_repor(pendentes), consumidos_24h, pendentes


def enfileirar_meta_diaria_mei_mg() -> int:
    if settings.max_envios_por_dia != 10000:
        raise RuntimeError(
            f"MAX_ENVIOS_POR_DIA precisa permanecer em 10000; atual={settings.max_envios_por_dia}"
        )
    if settings.meta_envios_por_dia != EXPECTED_DAILY_TARGET:
        raise RuntimeError(
            f"META_ENVIOS_POR_DIA precisa estar em {EXPECTED_DAILY_TARGET}; atual={settings.meta_envios_por_dia}"
        )
    if settings.rate_limit_envios_por_minuto > 30:
        raise RuntimeError("RATE_LIMIT_ENVIOS_POR_MINUTO excede o limite local permitido.")

    # Valida o template mesmo quando o buffer ja estiver cheio.
    carregar_template_html()

    with psycopg.connect(settings.database_url) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                select count(*)
                  from mei_email.envios
                 where status in ('submitted', 'enviado')
                   and enviado_em >= now() - interval '24 hours'
                """
            )
            consumidos_24h = int(cur.fetchone()[0] or 0)
        pendentes_antes = contar_pendentes(conn)
        adicionados = repor_fila_automatica(conn)
        pendentes_depois = contar_pendentes(conn)

    print(
        f"Submitted/enviados nas ultimas 24h: {consumidos_24h}/{settings.max_envios_por_dia}",
        flush=True,
    )
    print(f"Meta operacional de envio: {settings.meta_envios_por_dia}", flush=True)
    print(
        f"Buffer da fila: antes={pendentes_antes} adicionados={adicionados} depois={pendentes_depois} "
        f"min={settings.queue_min_pending} target={settings.queue_target_pending}",
        flush=True,
    )
    print(
        "A fila fica preparada continuamente; o worker aplica a cota movel antes de cada envio.",
        flush=True,
    )
    return 0


# Alias mantido para automacoes antigas que importavam o nome anterior.
def enfileirar_ate_10000_mei_mg() -> int:
    return enfileirar_meta_diaria_mei_mg()


if __name__ == "__main__":
    raise SystemExit(enfileirar_meta_diaria_mei_mg())
