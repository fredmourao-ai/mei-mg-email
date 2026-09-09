#!/usr/bin/env python3
"""Rotina de validação contínua e autocorreção da operação de envios (15 minutos).

Executa a cada 15 minutos via systemd timer para assegurar:
1. Worker de envio ativo e rodando;
2. Recuperação automática de lotes/envios travados;
3. Supervisao da fila, cuja reposicao pertence ao serviço dedicado;
4. Monitoramento da integridade do banco de dados e da operacao Brevo;
5. Registro detalhado de metricas operacionais.
"""
from __future__ import annotations

import json
import logging
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import psycopg
from psycopg.rows import dict_row, tuple_row
from dotenv import load_dotenv

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [AUTOREPAIR-15M] %(message)s"
)
logger = logging.getLogger("autorepair_15m")

APP_DIR = Path(__file__).resolve().parent.parent
load_dotenv(APP_DIR / ".env")

from app.config import settings
from app.queue_manager import contar_pendentes

STATE_DIR = Path("/var/lib/mei-mg-email")
SENTINEL_PATH = STATE_DIR / "sender_blocked.pause"
HEALTH_FILE = STATE_DIR / "health_15min.json"


def _run_cmd(cmd: list[str]) -> tuple[int, str]:
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        return res.returncode, (res.stdout or res.stderr).strip()
    except Exception as exc:
        return -1, str(exc)


def verificar_e_recuperar_servico_worker() -> bool:
    code, out = _run_cmd(["systemctl", "is-active", "mei-mg-email-worker.service"])
    if out == "active":
        logger.info("Worker service: ACTIVE (running)")
        return True

    logger.warning("Worker service nao esta ativo (status=%s). Reiniciando...", out)
    code_restart, out_restart = _run_cmd(["systemctl", "restart", "mei-mg-email-worker.service"])
    if code_restart == 0:
        logger.info("Worker service reiniciado com sucesso.")
        return True
    else:
        logger.error("Falha ao reiniciar worker: %s", out_restart)
        return False


def recuperar_lotes_travados(conn: psycopg.Connection) -> int:
    with conn.cursor() as cur:
        cur.execute(
            """
            update mei_email.lotes
               set status = 'pendente',
                   iniciado_em = null,
                   erro = 'recuperado automaticamente pela rotina de 15min'
             where status = 'processando'
               and (iniciado_em is null or iniciado_em < now() - interval '15 minutes')
            """
        )
        recuperados = cur.rowcount
    conn.commit()
    if recuperados > 0:
        logger.warning("Lotes destravados para 'pendente': %d", recuperados)
    else:
        logger.info("Nenhum lote travado em 'processando'.")
    return recuperados


def verificar_e_repor_fila(conn: psycopg.Connection) -> dict:
    pendentes = contar_pendentes(conn)
    logger.info("Fila atual de pendentes/processando: %d (min=%d, target=%d)",
                pendentes, settings.queue_min_pending, settings.queue_target_pending)

    if pendentes <= settings.queue_min_pending:
        logger.info(
            "Fila no gatilho de reposicao (%d <= %d); escrita delegada exclusivamente ao mei-mg-email-queue-replenisher.service.",
            pendentes,
            settings.queue_min_pending,
        )

    novo_total = contar_pendentes(conn)
    return {"antes": pendentes, "adicionados": 0, "depois": novo_total}


def coletar_metricas(conn: psycopg.Connection) -> dict:
    agora = datetime.now(timezone.utc)
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            select
                count(*) filter (where status::text in ('submitted', 'enviado') and enviado_em >= now() - interval '24 hours') as sent_24h,
                count(*) filter (where status::text in ('submitted', 'enviado') and enviado_em >= now() - interval '1 hour') as sent_1h,
                count(*) filter (where status::text in ('submitted', 'enviado') and enviado_em >= now() - interval '15 minutes') as sent_15m,
                count(*) filter (where status::text in ('pendente', 'enviando', 'pending', 'processing')) as pending_queue,
                count(*) filter (where status::text in ('submitted', 'enviado')) as total_submitted,
                count(*) filter (where status::text in ('falhou', 'failed')) as total_failed
            from mei_email.envios
            """
        )
        stats = cur.fetchone() or {}

        cur.execute("select status, count(*) as count from mei_email.lotes group by status")
        lotes = {r["status"]: r["count"] for r in cur.fetchall()}

    return {
        "timestamp_utc": agora.isoformat(),
        "envios_24h": stats.get("sent_24h", 0),
        "envios_1h": stats.get("sent_1h", 0),
        "envios_15m": stats.get("sent_15m", 0),
        "fila_pendente": stats.get("pending_queue", 0),
        "total_enviados": stats.get("total_submitted", 0),
        "total_falhas": stats.get("total_failed", 0),
        "lotes": lotes,
        "sentinel_blocked": SENTINEL_PATH.is_file(),
    }


def executar_validacao_completa():
    logger.info("=== INICIANDO CICLO DE VALIDACAO E AUTOCORRECAO (15 MIN) ===")

    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        logger.error("DATABASE_URL nao configurada.")
        return 1

    # 1. Verificar e recuperar servico worker
    worker_ok = verificar_e_recuperar_servico_worker()

    # 2. Conectar ao banco e executar recuperacoes
    conn = psycopg.connect(db_url, autocommit=False)
    try:
        # Destravar lotes antigos
        lotes_recuperados = recuperar_lotes_travados(conn)

        # Repor fila se necessario
        info_fila = verificar_e_repor_fila(conn)

        # Coletar snapshot de metricas
        metricas = coletar_metricas(conn)
        metricas["worker_active"] = worker_ok
        metricas["lotes_recuperados"] = lotes_recuperados
        metricas["fila_info"] = info_fila

        # Gravar arquivo de status
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        HEALTH_FILE.write_text(json.dumps(metricas, indent=2), encoding="utf-8")

        logger.info("=== RESUMO DO CICLO ===")
        logger.info("Envios 24h: %d | Ultimos 15m: %d | Fila: %d | Worker: %s | Bloqueado: %s",
                    metricas["envios_24h"], metricas["envios_15m"], metricas["fila_pendente"],
                    worker_ok, metricas["sentinel_blocked"])
        logger.info("Ciclo de 15 minutos finalizado com sucesso.")
        return 0
    except Exception as exc:
        logger.error("Erro durante validacao/autocorrecao: %s", exc, exc_info=True)
        return 2
    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(executar_validacao_completa())
