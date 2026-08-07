#!/usr/bin/env python3
"""Enfileira capacidade diaria para ate 10.000 destinatarios em 24h.

Este script nao tenta burlar limites do Exchange. Ele considera os envios das
ultimas 24 horas e a fila pendente existente antes de criar uma nova campanha.
O worker unico e responsavel pelo envio real no ritmo configurado.
"""
from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import psycopg

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from app.config import settings
from app.routes.campanhas import criar_campanha
from app.schemas import CampanhaCreate


def capacidade_para_nova_fila() -> tuple[int, int, int]:
    with psycopg.connect(settings.database_url) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                select count(*)
                  from mei_email.envios
                 where status = 'enviado'
                   and enviado_em >= now() - interval '24 hours'
                """
            )
            enviados_24h = cur.fetchone()[0]

            cur.execute(
                """
                select count(*)
                  from mei_email.envios
                 where status = 'pendente'
                """
            )
            pendentes = cur.fetchone()[0]

    disponivel = max(settings.max_envios_por_dia - enviados_24h - pendentes, 0)
    return disponivel, enviados_24h, pendentes


def enfileirar_ate_10000_mei_mg() -> int:
    if settings.max_envios_por_dia != 10000:
        raise RuntimeError(
            f"MAX_ENVIOS_POR_DIA precisa estar em 10000; atual={settings.max_envios_por_dia}"
        )
    if settings.rate_limit_envios_por_minuto > 30:
        raise RuntimeError("RATE_LIMIT_ENVIOS_POR_MINUTO excede o limite de 30/min do Exchange Online.")

    disponivel, enviados_24h, pendentes = capacidade_para_nova_fila()
    print(f"Enviados nas ultimas 24h: {enviados_24h}/10000", flush=True)
    print(f"Ja pendentes na fila: {pendentes}", flush=True)
    print(f"Capacidade adicional para enfileirar: {disponivel}", flush=True)

    if disponivel <= 0:
        print("Nenhuma nova campanha criada: a capacidade de 24h ja esta comprometida.", flush=True)
        return 0

    agora_sp = datetime.now(ZoneInfo("America/Sao_Paulo"))
    payload = CampanhaCreate(
        nome=f"MEI MG Diario {agora_sp:%Y-%m-%d} - Contabilidade Melo",
        assunto="Aviso Importante para MEI - Regularizacao Fiscal",
        corpo_template=(
            "Ola, {{razao_social}}.\n\n"
            "A Contabilidade Melo esta disponivel para apoiar seu MEI na organizacao de obrigacoes fiscais.\n\n"
            "Conheca nossos canais oficiais: https://contabilidademelo.com.br\n\n"
            "Caso nao deseje mais receber nossas mensagens, acesse: {{unsubscribe_url}}"
        ),
        filtro_tipo_regime="MEI",
        filtro_uf="MG",
        tamanho_lote=100,
        limite_empresas=disponivel,
    )
    campanha = criar_campanha(payload)
    print(
        f"Campanha enfileirada: id={campanha['id']} total={campanha['total_empresas']} "
        f"capacidade_24h={settings.max_envios_por_dia}",
        flush=True,
    )
    print("O worker unico processara a fila no rate limit configurado.", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(enfileirar_ate_10000_mei_mg())
