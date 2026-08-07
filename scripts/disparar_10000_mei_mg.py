#!/usr/bin/env python3
"""Enfileira a meta diaria sem ultrapassar o teto local de 10.000/24h.

O script usa o template HTML oficial, considera a janela movel de 24 horas e a
fila ja existente e so seleciona destinatarios presentes em
vw_empresas_elegiveis. A view e fail-closed: ativo, autorizado, sem opt-out,
nao-terceiro e nunca previamente enfileirado/contatado pelo mesmo e-mail.
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

TEMPLATE_PATH = BASE_DIR / "templates" / "mei-contabilidade-melo.html"
EXPECTED_DAILY_TARGET = 9950


def carregar_template_html() -> str:
    template = TEMPLATE_PATH.read_text(encoding="utf-8")
    lower = template.casefold()
    required = (
        "<html",
        "{{unsubscribe_url}}",
        "{{nome_fantasia}}",
        "logo-contabilidade-melo-transparente.png",
    )
    missing = [token for token in required if token.casefold() not in lower]
    if missing:
        raise RuntimeError(f"template HTML incompleto; faltando={','.join(missing)}")
    return template


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
                 where status in ('pendente', 'enviando')
                """
            )
            pendentes = cur.fetchone()[0]

    comprometido = enviados_24h + pendentes
    pela_meta = max(settings.meta_envios_por_dia - comprometido, 0)
    pelo_teto = max(settings.max_envios_por_dia - comprometido, 0)
    disponivel = min(pela_meta, pelo_teto)
    return disponivel, enviados_24h, pendentes


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

    template_html = carregar_template_html()
    disponivel, enviados_24h, pendentes = capacidade_para_nova_fila()
    print(
        f"Enviados nas ultimas 24h: {enviados_24h}/{settings.max_envios_por_dia}",
        flush=True,
    )
    print(f"Meta operacional: {settings.meta_envios_por_dia}", flush=True)
    print(f"Ja pendentes na fila: {pendentes}", flush=True)
    print(f"Capacidade adicional para a meta: {disponivel}", flush=True)

    if disponivel <= 0:
        print("Nenhuma nova campanha criada: a meta de 24h ja esta comprometida.", flush=True)
        return 0

    agora_sp = datetime.now(ZoneInfo("America/Sao_Paulo"))
    payload = CampanhaCreate(
        nome=f"MEI MG Diario {agora_sp:%Y-%m-%d} - Contabilidade Melo",
        assunto="Aviso Importante para MEI - Regularizacao Fiscal",
        corpo_template=template_html,
        filtro_tipo_regime="MEI",
        filtro_uf="MG",
        tamanho_lote=100,
        limite_empresas=disponivel,
    )
    campanha = criar_campanha(payload)
    print(
        f"Campanha enfileirada: id={campanha['id']} total={campanha['total_empresas']} "
        f"meta_24h={settings.meta_envios_por_dia} teto_24h={settings.max_envios_por_dia}",
        flush=True,
    )
    print("O worker unico processara a fila no rate limit configurado.", flush=True)
    return 0


# Alias mantido para automacoes antigas que importavam o nome anterior.
def enfileirar_ate_10000_mei_mg() -> int:
    return enfileirar_meta_diaria_mei_mg()


if __name__ == "__main__":
    raise SystemExit(enfileirar_meta_diaria_mei_mg())
