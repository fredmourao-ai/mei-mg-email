#!/usr/bin/env python3
"""Sincronizacao diaria auditavel da base de CNPJ, independente do disparo.

Por padrao a rotina usa a pesquisa v5 da Casa dos Dados para descobrir novos
CNPJs de MG em uma janela diaria sobreposta. A fonte espelho do Hugging Face
continua disponivel apenas como fallback explicito.

Toda execucao grava trilha em mei_email.base_sync_runs. Ausencia de credencial,
fonte obsoleta ou falha de ingestao retorna codigo diferente de zero para que o
monitoramento nao confunda "timer executou" com "dados novos foram avaliados".

Esta rotina NAO cria campanhas e NAO inicia o worker de e-mail.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

import psycopg
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env", override=True)

DAILY_SOURCE = os.getenv("CNPJ_DAILY_SOURCE", "casadosdados").strip().casefold()
SOURCE_NAME = (
    "casa_dos_dados_v5"
    if DAILY_SOURCE in {"casadosdados", "casa_dos_dados", "cdd"}
    else os.getenv("CNPJ_BASE_SOURCE_NAME", "huggingface_fluowai_datacorp_cnpj").strip()
)
SOURCE_API = os.getenv(
    "CNPJ_BASE_SOURCE_METADATA_URL",
    "https://huggingface.co/api/datasets/fluowai/datacorp-cnpj-data",
).strip()
MAX_SOURCE_AGE_HOURS = int(os.getenv("CNPJ_BASE_MAX_SOURCE_AGE_HOURS", "48"))
FORCE_REFRESH = os.getenv("CNPJ_BASE_FORCE_REFRESH", "0").strip().lower() in {"1", "true", "yes", "sim"}
LOCK_ID = 14082026
TZ = ZoneInfo(os.getenv("CNPJ_DAILY_TIMEZONE", "America/Sao_Paulo"))


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    text = value.strip().replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def fetch_source_metadata() -> tuple[str, datetime | None, dict]:
    req = Request(
        SOURCE_API,
        headers={"User-Agent": "ShopVivaliz-MEI-base-sync/1.0", "Accept": "application/json"},
    )
    with urlopen(req, timeout=30) as response:
        payload = json.loads(response.read().decode("utf-8"))
    revision = str(payload.get("sha") or payload.get("id") or "").strip()
    if not revision:
        raise RuntimeError("Fonte nao informou uma revisao identificavel")
    last_modified = _parse_datetime(str(payload.get("lastModified") or ""))
    summary = {
        "dataset_id": payload.get("id"),
        "sha": revision,
        "lastModified": payload.get("lastModified"),
        "private": payload.get("private"),
        "disabled": payload.get("disabled"),
    }
    return revision, last_modified, summary


def source_age_hours(last_modified: datetime | None) -> float | None:
    if last_modified is None:
        return None
    return max((datetime.now(timezone.utc) - last_modified.astimezone(timezone.utc)).total_seconds() / 3600.0, 0.0)


def finish_run(conn, run_id: int, status: str, **fields) -> None:
    details = fields.pop("details", {})
    with conn.cursor() as cur:
        cur.execute(
            """
            update mei_email.base_sync_runs
               set status=%s,
                   finished_at=now(),
                   source_revision=coalesce(%s,source_revision),
                   source_last_modified=coalesce(%s,source_last_modified),
                   rows_before=%s,
                   rows_after=%s,
                   rows_added=%s,
                   details=%s::jsonb,
                   error=%s
             where id=%s
            """,
            (
                status,
                fields.get("source_revision"),
                fields.get("source_last_modified"),
                fields.get("rows_before"),
                fields.get("rows_after"),
                fields.get("rows_added"),
                json.dumps(details, ensure_ascii=False, default=str),
                fields.get("error"),
                run_id,
            ),
        )
    conn.commit()


def _count_companies(conn) -> int:
    with conn.cursor() as cur:
        cur.execute("select count(*) from mei_email.empresas")
        return int(cur.fetchone()[0])


def _parse_result_line(stdout: str, prefix: str) -> dict:
    for line in stdout.splitlines():
        if line.startswith(prefix):
            raw = line[len(prefix) :].strip()
            return json.loads(raw) if raw else {}
    return {}


def sync_casa_dos_dados(conn, run_id: int) -> int:
    if not os.getenv("CASA_DOS_DADOS_API_KEY", "").strip():
        details = {
            "daily_source": "casadosdados",
            "missing_secret": "CASA_DOS_DADOS_API_KEY",
            "action_required": "configure_api_key_in_vm_secret_environment",
        }
        finish_run(
            conn,
            run_id,
            "failed",
            details=details,
            error="CASA_DOS_DADOS_API_KEY nao configurada",
        )
        print("BASE_SYNC_STATUS=failed", flush=True)
        print("BASE_SYNC_REASON=missing_secret", flush=True)
        print("MISSING_SECRET=CASA_DOS_DADOS_API_KEY", flush=True)
        return 3

    rows_before = _count_companies(conn)
    # SELECT count(*) opens a transaction in psycopg. The ingest subprocess can
    # take a long time, so close that read transaction before waiting on it.
    # The session-level advisory lock remains held and still guarantees a
    # single base-sync execution without an hours-long idle-in-transaction.
    conn.commit()
    ingest = subprocess.run(
        [sys.executable, str(BASE_DIR / "scripts" / "ingest_casa_dos_dados_daily.py")],
        cwd=str(BASE_DIR),
        text=True,
        capture_output=True,
    )
    if ingest.stdout:
        print(ingest.stdout, end="" if ingest.stdout.endswith("\n") else "\n", flush=True)
    if ingest.stderr:
        print(ingest.stderr, end="" if ingest.stderr.endswith("\n") else "\n", file=sys.stderr, flush=True)
    if ingest.returncode != 0:
        raise RuntimeError(f"ingest_casa_dos_dados_daily.py exit={ingest.returncode}")

    rows_after = _count_companies(conn)
    result = _parse_result_line(ingest.stdout, "CASA_DOS_DADOS_RESULT=")
    rows_added = max(rows_after - rows_before, 0)
    today = datetime.now(TZ).date().isoformat()
    revision = f"daily-window:{result.get('window_start','?')}:{result.get('window_end',today)}"
    details = {
        "daily_source": "casadosdados",
        "api_result": result,
        "safety": "no_campaign_creation_no_worker_start",
    }
    finish_run(
        conn,
        run_id,
        "success",
        source_revision=revision,
        rows_before=rows_before,
        rows_after=rows_after,
        rows_added=rows_added,
        details=details,
    )
    print("BASE_SYNC_STATUS=success", flush=True)
    print(f"SOURCE_REVISION={revision}", flush=True)
    print(f"ROWS_BEFORE={rows_before}", flush=True)
    print(f"ROWS_AFTER={rows_after}", flush=True)
    print(f"ROWS_ADDED={rows_added}", flush=True)
    return 0


def sync_huggingface_fallback(conn, run_id: int) -> int:
    revision, last_modified, source_summary = fetch_source_metadata()
    age_hours = source_age_hours(last_modified)
    stale = age_hours is None or age_hours > MAX_SOURCE_AGE_HOURS

    with conn.cursor() as cur:
        cur.execute(
            """
            select source_revision
              from mei_email.base_sync_runs
             where source_name=%s
               and id<>%s
               and status in ('success','no_change','source_stale')
               and source_revision is not null
             order by finished_at desc nulls last, id desc
             limit 1
            """,
            (SOURCE_NAME, run_id),
        )
        row = cur.fetchone()
        previous_revision = row[0] if row else None

    details = {
        "source": source_summary,
        "source_age_hours": round(age_hours, 2) if age_hours is not None else None,
        "max_source_age_hours": MAX_SOURCE_AGE_HOURS,
        "previous_revision": previous_revision,
        "force_refresh": FORCE_REFRESH,
        "fallback_only": True,
    }

    if previous_revision == revision and not FORCE_REFRESH:
        status = "source_stale" if stale else "no_change"
        finish_run(
            conn,
            run_id,
            status,
            source_revision=revision,
            source_last_modified=last_modified,
            details=details,
        )
        print(f"BASE_SYNC_STATUS={status}", flush=True)
        print(f"SOURCE_REVISION={revision}", flush=True)
        print(f"SOURCE_AGE_HOURS={details['source_age_hours']}", flush=True)
        if stale:
            print("SOURCE_FRESHNESS_ERROR=fonte_nao_ofereceu_revisao_nova_no_limite_configurado", flush=True)
            return 2
        return 0

    rows_before = _count_companies(conn)
    conn.commit()
    ingest = subprocess.run(
        [sys.executable, str(BASE_DIR / "scripts" / "ingest_from_huggingface.py")],
        cwd=str(BASE_DIR),
        text=True,
    )
    if ingest.returncode != 0:
        raise RuntimeError(f"ingest_from_huggingface.py exit={ingest.returncode}")

    rows_after = _count_companies(conn)
    rows_added = max(rows_after - rows_before, 0)
    details["source_stale_at_import"] = stale
    finish_run(
        conn,
        run_id,
        "success",
        source_revision=revision,
        source_last_modified=last_modified,
        rows_before=rows_before,
        rows_after=rows_after,
        rows_added=rows_added,
        details=details,
    )
    print("BASE_SYNC_STATUS=success", flush=True)
    print(f"SOURCE_REVISION={revision}", flush=True)
    print(f"ROWS_BEFORE={rows_before}", flush=True)
    print(f"ROWS_AFTER={rows_after}", flush=True)
    print(f"ROWS_ADDED={rows_added}", flush=True)
    if stale:
        print("WARNING=fonte_importada_esta_mais_antiga_que_o_limite_de_frescor", flush=True)
    return 0


def main() -> int:
    database_url = os.environ["DATABASE_URL"]
    with psycopg.connect(database_url) as conn:
        with conn.cursor() as cur:
            cur.execute("select pg_try_advisory_lock(%s)", (LOCK_ID,))
            if not cur.fetchone()[0]:
                print("BASE_SYNC_SKIPPED=outra_sincronizacao_ja_esta_em_execucao", flush=True)
                return 0

        with conn.cursor() as cur:
            cur.execute(
                """
                insert into mei_email.base_sync_runs(source_name,status)
                values (%s,'running') returning id
                """,
                (SOURCE_NAME,),
            )
            run_id = cur.fetchone()[0]
        conn.commit()

        try:
            if DAILY_SOURCE in {"casadosdados", "casa_dos_dados", "cdd"}:
                return sync_casa_dos_dados(conn, run_id)
            if DAILY_SOURCE in {"huggingface", "hf", "mirror"}:
                return sync_huggingface_fallback(conn, run_id)
            raise RuntimeError(f"CNPJ_DAILY_SOURCE invalida: {DAILY_SOURCE}")
        except Exception as exc:
            conn.rollback()
            try:
                finish_run(conn, run_id, "failed", error=f"{type(exc).__name__}: {exc}")
            except Exception as audit_exc:
                conn.rollback()
                print(
                    f"BASE_SYNC_AUDIT_ERROR={type(audit_exc).__name__}:{audit_exc}",
                    flush=True,
                )
            print(f"BASE_SYNC_STATUS=failed error={type(exc).__name__}:{exc}", flush=True)
            return 1


if __name__ == "__main__":
    raise SystemExit(main())
