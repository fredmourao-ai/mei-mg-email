#!/usr/bin/env python3
"""Monitor residente de envios, fila e atualizacao diaria da base.

Este processo NAO envia e-mails e NAO altera a fila. Ele observa o PostgreSQL,
o lock do worker e os units systemd, grava snapshots em JSON/JSONL e emite
alertas no journald. Deve continuar ativo mesmo quando o worker cair.
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

import psycopg
from dotenv import load_dotenv
from psycopg.rows import dict_row

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env", override=True)

from app.config import settings

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("mei_mg_email.monitor")

WORKER_ADVISORY_LOCK_ID = 100002026
MONITOR_INTERVAL_SECONDS = max(int(os.getenv("MONITOR_INTERVAL_SECONDS", "60")), 10)
MONITOR_SEND_STALL_MINUTES = max(int(os.getenv("MONITOR_SEND_STALL_MINUTES", "10")), 2)
MONITOR_BASE_MAX_AGE_HOURS = max(float(os.getenv("MONITOR_BASE_MAX_AGE_HOURS", "26")), 1.0)
MONITOR_STATUS_DIR = Path(os.getenv("MONITOR_STATUS_DIR", str(BASE_DIR / "runtime" / "monitor")))
MONITOR_WORKER_UNIT = os.getenv("MONITOR_WORKER_UNIT", "mei-mg-email-worker.service").strip()
MONITOR_BASE_TIMER_UNIT = os.getenv("MONITOR_BASE_TIMER_UNIT", "mei-mg-email-base-sync.timer").strip()


def _iso(value):
    if value is None:
        return None
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


def _systemctl(command: str, unit: str) -> str:
    if not unit:
        return "not_configured"
    try:
        result = subprocess.run(
            ["systemctl", command, unit],
            text=True,
            capture_output=True,
            timeout=10,
            check=False,
        )
        text = (result.stdout or result.stderr).strip()
        return text or f"exit_{result.returncode}"
    except (OSError, subprocess.SubprocessError) as exc:
        return f"unavailable:{type(exc).__name__}"


def _worker_lock_held(cur) -> bool:
    high = (WORKER_ADVISORY_LOCK_ID >> 32) & 0xFFFFFFFF
    low = WORKER_ADVISORY_LOCK_ID & 0xFFFFFFFF
    cur.execute(
        """
        select exists (
          select 1
            from pg_locks
           where locktype = 'advisory'
             and granted
             and classid = %s
             and objid = %s
        )
        """,
        (high, low),
    )
    return bool(cur.fetchone()[0])


def coletar_snapshot(conn: psycopg.Connection) -> dict:
    agora = datetime.now(timezone.utc)
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            select
              count(*) filter (where status::text in ('pendente','enviando')) as fila,
              count(*) filter (where status::text = 'pendente') as pendentes,
              count(*) filter (where status::text = 'enviando') as enviando,
              count(*) filter (
                where status::text in ('submitted','enviado')
                  and enviado_em >= now() - interval '24 hours'
              ) as enviados_24h,
              count(*) filter (
                where status::text in ('submitted','enviado')
                  and enviado_em >= now() - interval '60 minutes'
              ) as enviados_60m,
              count(*) filter (
                where status::text in ('submitted','enviado')
                  and enviado_em >= now() - interval '15 minutes'
              ) as enviados_15m,
              count(*) filter (
                where status::text in ('submitted','enviado')
                  and enviado_em >= now() - interval '5 minutes'
              ) as enviados_5m,
              count(*) filter (
                where status::text = 'falhou'
                  and criado_em >= now() - interval '24 hours'
              ) as falhas_24h,
              count(*) filter (
                where status::text = 'sender_blocked'
                  and criado_em >= now() - interval '24 hours'
              ) as sender_blocked_24h,
              max(enviado_em) filter (where status::text in ('submitted','enviado')) as ultimo_envio
            from mei_email.envios
            """
        )
        envio = dict(cur.fetchone())

        cur.execute("select count(*) as elegiveis from mei_email.vw_empresas_elegiveis")
        elegiveis = int(cur.fetchone()["elegiveis"] or 0)

        cur.execute(
            """
            select id, source_name, source_revision, source_last_modified, status,
                   started_at, finished_at, rows_before, rows_after, rows_added, error
              from mei_email.base_sync_runs
             order by started_at desc, id desc
             limit 1
            """
        )
        base_row = cur.fetchone()
        base = dict(base_row) if base_row else None

        worker_lock_held = _worker_lock_held(cur)

    ultimo_envio = envio.get("ultimo_envio")
    ultimo_envio_age_minutes = None
    if ultimo_envio is not None:
        ultimo_envio_age_minutes = max(
            (agora - ultimo_envio.astimezone(timezone.utc)).total_seconds() / 60.0,
            0.0,
        )

    base_age_hours = None
    if base:
        base_reference = base.get("finished_at") or base.get("started_at")
        if base_reference:
            base_age_hours = max(
                (agora - base_reference.astimezone(timezone.utc)).total_seconds() / 3600.0,
                0.0,
            )
        for key in ("source_last_modified", "started_at", "finished_at"):
            base[key] = _iso(base.get(key))

    snapshot = {
        "captured_at": agora.isoformat(),
        "limits": {
            "meta_24h": settings.meta_envios_por_dia,
            "max_24h": settings.max_envios_por_dia,
            "rate_per_minute": settings.rate_limit_envios_por_minuto,
            "queue_min_pending": settings.queue_min_pending,
            "queue_target_pending": settings.queue_target_pending,
        },
        "queue": {
            "total": int(envio.get("fila") or 0),
            "pendentes": int(envio.get("pendentes") or 0),
            "enviando": int(envio.get("enviando") or 0),
            "elegiveis_restantes": elegiveis,
        },
        "sending": {
            "submitted_enviado_24h": int(envio.get("enviados_24h") or 0),
            "submitted_enviado_60m": int(envio.get("enviados_60m") or 0),
            "submitted_enviado_15m": int(envio.get("enviados_15m") or 0),
            "submitted_enviado_5m": int(envio.get("enviados_5m") or 0),
            "last_submission_at": _iso(ultimo_envio),
            "last_submission_age_minutes": round(ultimo_envio_age_minutes, 2)
            if ultimo_envio_age_minutes is not None
            else None,
            "failures_24h": int(envio.get("falhas_24h") or 0),
            "sender_blocked_24h": int(envio.get("sender_blocked_24h") or 0),
        },
        "worker": {
            "advisory_lock_held": worker_lock_held,
            "systemd_active": _systemctl("is-active", MONITOR_WORKER_UNIT),
        },
        "base_sync": {
            "latest": base,
            "age_hours": round(base_age_hours, 2) if base_age_hours is not None else None,
            "timer_active": _systemctl("is-active", MONITOR_BASE_TIMER_UNIT),
            "timer_enabled": _systemctl("is-enabled", MONITOR_BASE_TIMER_UNIT),
        },
    }
    snapshot["alerts"] = construir_alertas(snapshot)
    snapshot["health"] = "critical" if any(a["level"] == "critical" for a in snapshot["alerts"]) else (
        "warning" if snapshot["alerts"] else "ok"
    )
    return snapshot


def construir_alertas(snapshot: dict) -> list[dict]:
    alerts: list[dict] = []
    queue = snapshot["queue"]
    sending = snapshot["sending"]
    worker = snapshot["worker"]
    base_sync = snapshot["base_sync"]
    limits = snapshot["limits"]

    def add(level: str, code: str, detail: str) -> None:
        alerts.append({"level": level, "code": code, "detail": detail})

    if queue["total"] == 0:
        add("critical", "queue_empty", "Fila zerou; a reposicao automatica nao manteve estoque.")
    elif queue["total"] <= limits["queue_min_pending"]:
        add(
            "warning",
            "queue_low",
            f"Fila em {queue['total']}, no/abaixo do gatilho {limits['queue_min_pending']}.",
        )

    if queue["elegiveis_restantes"] == 0:
        add("critical", "eligible_base_exhausted", "Nao ha novos destinatarios elegiveis para repor a fila.")

    if sending["sender_blocked_24h"] > 0:
        add(
            "critical",
            "sender_blocked",
            f"Existem {sending['sender_blocked_24h']} registros sender_blocked nas ultimas 24h.",
        )

    quota_reached = sending["submitted_enviado_24h"] >= limits["meta_24h"]
    has_capacity = not quota_reached
    if queue["total"] > 0 and has_capacity:
        if not worker["advisory_lock_held"]:
            add("critical", "worker_lock_missing", "Ha fila e cota disponivel, mas o lock do worker nao esta ativo.")
        age = sending["last_submission_age_minutes"]
        if sending["submitted_enviado_15m"] == 0 and (age is None or age >= MONITOR_SEND_STALL_MINUTES):
            add(
                "critical",
                "sending_stalled",
                f"Ha fila/cota disponivel e nenhum envio recente; limite={MONITOR_SEND_STALL_MINUTES} min.",
            )

    if sending["submitted_enviado_24h"] > limits["max_24h"]:
        add(
            "critical",
            "rolling_cap_exceeded",
            f"Contador 24h={sending['submitted_enviado_24h']} acima do teto {limits['max_24h']}.",
        )

    latest = base_sync.get("latest")
    if latest is None:
        add("critical", "base_sync_never_ran", "Nao existe execucao registrada em base_sync_runs.")
    else:
        status = latest.get("status")
        if status in {"failed", "source_stale"}:
            add("critical", "base_sync_failed", f"Ultima sincronizacao da base terminou como {status}.")
        elif status == "running" and (base_sync.get("age_hours") or 0) > 2:
            add("critical", "base_sync_stuck", "Sincronizacao da base esta running ha mais de 2 horas.")
        age_hours = base_sync.get("age_hours")
        if age_hours is not None and age_hours > MONITOR_BASE_MAX_AGE_HOURS:
            add(
                "critical",
                "base_sync_overdue",
                f"Ultima verificacao da base tem {age_hours:.2f}h; maximo={MONITOR_BASE_MAX_AGE_HOURS:.2f}h.",
            )

    if base_sync.get("timer_enabled") not in {"enabled", "static"}:
        add(
            "critical",
            "base_timer_not_enabled",
            f"Timer diario da base nao esta habilitado: {base_sync.get('timer_enabled')}.",
        )
    if base_sync.get("timer_active") != "active":
        add(
            "critical",
            "base_timer_not_active",
            f"Timer diario da base nao esta ativo: {base_sync.get('timer_active')}.",
        )

    return alerts


def persistir_snapshot(snapshot: dict) -> None:
    MONITOR_STATUS_DIR.mkdir(parents=True, exist_ok=True)
    current = MONITOR_STATUS_DIR / "status.json"
    tmp = MONITOR_STATUS_DIR / ".status.json.tmp"
    history = MONITOR_STATUS_DIR / "history.jsonl"
    payload = json.dumps(snapshot, ensure_ascii=False, sort_keys=True, default=str)
    tmp.write_text(payload + "\n", encoding="utf-8")
    tmp.replace(current)
    with history.open("a", encoding="utf-8") as handle:
        handle.write(payload + "\n")


def executar_uma_vez() -> dict:
    with psycopg.connect(settings.database_url) as conn:
        snapshot = coletar_snapshot(conn)
    persistir_snapshot(snapshot)
    logger.info(
        "MONITOR_SNAPSHOT health=%s fila=%d enviados_24h=%d enviados_15m=%d elegiveis=%d base_age_h=%s",
        snapshot["health"],
        snapshot["queue"]["total"],
        snapshot["sending"]["submitted_enviado_24h"],
        snapshot["sending"]["submitted_enviado_15m"],
        snapshot["queue"]["elegiveis_restantes"],
        snapshot["base_sync"]["age_hours"],
    )
    for alert in snapshot["alerts"]:
        level = logging.CRITICAL if alert["level"] == "critical" else logging.WARNING
        logger.log(level, "MONITOR_ALERT code=%s detail=%s", alert["code"], alert["detail"])
    return snapshot


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true", help="Gera um snapshot e termina.")
    args = parser.parse_args()

    if args.once:
        snapshot = executar_uma_vez()
        print(json.dumps(snapshot, ensure_ascii=False, indent=2, default=str))
        return 2 if snapshot["health"] == "critical" else 0

    logger.info(
        "Monitor iniciado interval=%ss stall=%smin base_max_age=%sh status_dir=%s",
        MONITOR_INTERVAL_SECONDS,
        MONITOR_SEND_STALL_MINUTES,
        MONITOR_BASE_MAX_AGE_HOURS,
        MONITOR_STATUS_DIR,
    )
    while True:
        started = time.monotonic()
        try:
            executar_uma_vez()
        except Exception:
            logger.exception("MONITOR_ALERT code=monitor_iteration_failed")
        elapsed = time.monotonic() - started
        time.sleep(max(MONITOR_INTERVAL_SECONDS - elapsed, 1.0))


if __name__ == "__main__":
    raise SystemExit(main())
