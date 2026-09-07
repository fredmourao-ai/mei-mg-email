import sys
from pathlib import Path
import re
import time

import duckdb
import psycopg

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from app.config import settings

PARQUET_FILES = [
    f"https://huggingface.co/datasets/fluowai/datacorp-cnpj-data/resolve/main/cnpj_prefix_{i:02d}_{(i+9):02d}.parquet"
    for i in range(0, 100, 10)
]

SITUACAO_MAP = {
    "01": "NULA",
    "02": "ATIVA",
    "03": "SUSPENSA",
    "04": "INAPTA",
    "08": "BAIXADA",
}

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
TRANSIENT_HTTP_RE = re.compile(r"HTTP\s+(?:429|5\d\d)\b", re.IGNORECASE)


def execute_parquet_query_with_retry(
    conn_duck,
    query: str,
    *,
    attempts: int = 3,
    base_delay_seconds: float = 2.0,
):
    """Retry only transient HTTP source failures; preserve fail-closed behavior."""
    attempts = max(int(attempts), 1)
    for attempt in range(1, attempts + 1):
        try:
            return conn_duck.execute(query)
        except Exception as exc:
            transient = bool(TRANSIENT_HTTP_RE.search(str(exc)))
            if not transient or attempt >= attempts:
                raise
            delay = base_delay_seconds * attempt
            print(
                f"  -> fonte temporariamente indisponivel; retry {attempt}/{attempts - 1} em {delay:.1f}s: {exc}",
                flush=True,
            )
            if delay > 0:
                time.sleep(delay)


def format_date(dt_str: str | None) -> str | None:
    if not dt_str:
        return None
    value = str(dt_str).strip()
    if len(value) != 8 or not value.isdigit():
        return None
    return f"{value[:4]}-{value[4:6]}-{value[6:8]}"


def clean_str(val: str | None, max_len: int | None = None) -> str | None:
    if not val:
        return None
    value = str(val).strip()
    if not value:
        return None
    return value[:max_len] if max_len else value


def situacao_cadastral(code: str | None) -> str:
    return SITUACAO_MAP.get(
        str(code or "").strip().zfill(2),
        "DESCONHECIDA",
    )


def gravar_chunk_no_postgres(empresas: list[dict]) -> None:
    """Insert new rows and refresh only fields allowed by operator policy."""
    if not empresas:
        return

    with psycopg.connect(settings.database_url) as conn:
        with conn.cursor() as cur:
            cur.executemany(
                """
                insert into mei_email.empresas
                    (cnpj, razao_social, nome_fantasia, situacao_cadastral,
                     uf, email, ddd_1, telefone_1, data_abertura)
                values
                    (%(cnpj)s, %(razao_social)s, %(nome_fantasia)s,
                     %(situacao_cadastral)s, %(uf)s, %(email)s, %(ddd_1)s,
                     %(telefone_1)s, %(data_abertura)s)
                on conflict (cnpj) do update set
                    situacao_cadastral = excluded.situacao_cadastral,
                    uf = excluded.uf,
                    email = case
                        when mei_email.empresas.email is null
                          or btrim(mei_email.empresas.email::text) = ''
                        then excluded.email
                        else mei_email.empresas.email
                    end,
                    ddd_1 = coalesce(mei_email.empresas.ddd_1, excluded.ddd_1),
                    telefone_1 = coalesce(mei_email.empresas.telefone_1, excluded.telefone_1),
                    data_abertura = coalesce(excluded.data_abertura, mei_email.empresas.data_abertura)
                    -- opt_out e historico de envio nunca sao sobrescritos.
                """,
                empresas,
            )
        conn.commit()


def fetch_and_ingest_mg_data() -> None:
    print(
        "=== SINCRONIZACAO CNPJ VIA FONTE ESPELHO CONFIGURADA ===",
        flush=True,
    )
    print(
        "NOTE=importacao cadastral; envio usa somente a politica operacional atual.",
        flush=True,
    )
    conn_duck = duckdb.connect()
    total_processado = 0
    lotes_com_erro = 0

    for idx, parquet_url in enumerate(PARQUET_FILES, 1):
        print(f"\n[Fonte] Lendo lote {idx}/10...", flush=True)
        try:
            query = f"""
                select
                    lpad(cast(cnpj_base as varchar), 8, '0')
                    || lpad(cast(ordem as varchar), 4, '0')
                    || lpad(cast(dv as varchar), 2, '0') as cnpj,
                    razao_social,
                    fantasia as nome_fantasia,
                    sit_cadastral,
                    uf,
                    email,
                    ddd1 as ddd_1,
                    tel1 as telefone_1,
                    data_sit_cad as data_abertura
                from '{parquet_url}'
                where email is not null
                  and trim(email) != ''
                  and lower(trim(email)) not like '%contabil%'
                  and sit_cadastral = '02'
            """
            cursor = execute_parquet_query_with_retry(conn_duck, query)

            total_lote = 0
            while True:
                rows = cursor.fetchmany(10000)
                if not rows:
                    break

                empresas_chunk = []
                for row in rows:
                    cnpj = str(row[0]).strip().upper().zfill(14)
                    email = str(row[5]).strip().lower()
                    if not EMAIL_RE.fullmatch(email) or "contabil" in email:
                        continue

                    empresas_chunk.append(
                        {
                            "cnpj": cnpj,
                            "razao_social": clean_str(row[1]),
                            "nome_fantasia": clean_str(row[2]),
                            "situacao_cadastral": situacao_cadastral(row[3]),
                            "uf": clean_str(row[4], 2),
                            "email": email,
                            "ddd_1": clean_str(row[6], 3),
                            "telefone_1": clean_str(row[7], 15),
                            "data_abertura": format_date(row[8]),
                        }
                    )

                gravar_chunk_no_postgres(empresas_chunk)
                total_lote += len(empresas_chunk)
                print(
                    f"  -> {total_lote} registros processados "
                    f"no lote {idx}...",
                    flush=True,
                )

            total_processado += total_lote
            print(
                f"Lote {idx} concluido. Subtotal={total_lote}",
                flush=True,
            )
        except Exception as exc:
            lotes_com_erro += 1
            print(
                f"  -> ERRO lote {idx}: {type(exc).__name__}: {exc}",
                flush=True,
            )

    if lotes_com_erro:
        raise RuntimeError(
            f"Sincronizacao incompleta: {lotes_com_erro}/10 lotes falharam. "
            "Nenhum disparo deve depender desta carga parcial."
        )

    print(
        f"\n=== SINCRONIZACAO CONCLUIDA: {total_processado} REGISTROS "
        "PROCESSADOS ===",
        flush=True,
    )
    print(
        "Politica aplicada na entrada: ativa, email valido e sem contabil. "
        "Opt_out e enviado permanecem soberanos.",
        flush=True,
    )


if __name__ == "__main__":
    fetch_and_ingest_mg_data()
