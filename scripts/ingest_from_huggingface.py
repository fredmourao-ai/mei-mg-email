import sys
from pathlib import Path

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


def format_date(dt_str: str | None) -> str | None:
    if not dt_str:
        return None
    s = str(dt_str).strip()
    if len(s) != 8 or not s.isdigit():
        return None
    return f"{s[:4]}-{s[4:6]}-{s[6:8]}"


def clean_str(val: str | None, max_len: int | None = None) -> str | None:
    if not val:
        return None
    s = str(val).strip()
    if not s:
        return None
    return s[:max_len] if max_len else s


def situacao_cadastral(code: str | None) -> str:
    return SITUACAO_MAP.get(str(code or "").strip().zfill(2), "DESCONHECIDA")


def gravar_chunk_no_postgres(empresas: list[dict]) -> None:
    """Insere cadastros novos e refresca apenas campos cadastrais seguros.

    Esta fonte nao contem o historico oficial de opcao pelo MEI. Portanto ela
    pode classificar somente MEI_CANDIDATO; nunca define mei_verificado=true.
    Consentimento, opt-out, verificacao MEI e historico de envio sao preservados.
    """
    if not empresas:
        return
    with psycopg.connect(settings.database_url) as conn:
        with conn.cursor() as cur:
            cur.executemany(
                """
                insert into mei_email.empresas
                    (cnpj, razao_social, nome_fantasia, situacao_cadastral,
                     uf, email, ddd_1, telefone_1, data_abertura, tipo_regime, provavel_terceiro)
                values
                    (%(cnpj)s, %(razao_social)s, %(nome_fantasia)s,
                     %(situacao_cadastral)s, %(uf)s, %(email)s, %(ddd_1)s, %(telefone_1)s,
                     %(data_abertura)s, %(tipo_regime)s, %(provavel_terceiro)s)
                on conflict (cnpj) do update set
                    situacao_cadastral = excluded.situacao_cadastral,
                    tipo_regime = case
                        when mei_email.empresas.mei_verificado then mei_email.empresas.tipo_regime
                        else excluded.tipo_regime
                    end
                    -- Contato, consentimento, verificacao MEI, enviado e opt_out
                    -- nunca sao sobrescritos por esta fonte espelho.
                """,
                empresas,
            )
        conn.commit()


def fetch_and_ingest_mg_data() -> None:
    print("=== SINCRONIZACAO CNPJ MG VIA FONTE ESPELHO CONFIGURADA ===", flush=True)
    print(
        "NOTE=Natureza juridica/porte geram apenas MEI_CANDIDATO; opcao MEI precisa de verificacao oficial separada.",
        flush=True,
    )
    conn_duck = duckdb.connect()
    total_processado = 0
    lotes_com_erro = 0

    for idx, parquet_url in enumerate(PARQUET_FILES, 1):
        print(f"\n[Fonte] Lendo lote {idx}/10...", flush=True)
        try:
            query = f"""
                SELECT
                    lpad(cast(cnpj_base as varchar), 8, '0') || lpad(cast(ordem as varchar), 4, '0') || lpad(cast(dv as varchar), 2, '0') AS cnpj,
                    razao_social,
                    fantasia AS nome_fantasia,
                    sit_cadastral,
                    uf,
                    email,
                    ddd1 AS ddd_1,
                    tel1 AS telefone_1,
                    data_sit_cad AS data_abertura,
                    nat_juridica,
                    porte
                FROM '{parquet_url}'
                WHERE email IS NOT NULL
                  AND trim(email) != ''
                  AND upper(trim(uf)) = 'MG'
            """
            cursor = conn_duck.execute(query)

            total_lote = 0
            while True:
                rows = cursor.fetchmany(10000)
                if not rows:
                    break

                empresas_chunk = []
                for r in rows:
                    cnpj = str(r[0]).strip().upper().zfill(14)
                    email = str(r[5]).strip().lower()
                    nat_jur = str(r[9]).strip() if r[9] else ""
                    porte = str(r[10]).strip() if r[10] else ""

                    if nat_jur == "2135" or porte == "01":
                        tipo_regime = "MEI_CANDIDATO"
                    elif porte in ("03", "05") or nat_jur in ("2062", "2305"):
                        tipo_regime = "SIMPLES"
                    else:
                        tipo_regime = "OUTROS"

                    empresas_chunk.append(
                        {
                            "cnpj": cnpj,
                            "razao_social": clean_str(r[1]),
                            "nome_fantasia": clean_str(r[2]),
                            "situacao_cadastral": situacao_cadastral(r[3]),
                            "uf": "MG",
                            "email": email,
                            "ddd_1": clean_str(r[6], 3),
                            "telefone_1": clean_str(r[7], 15),
                            "data_abertura": format_date(r[8]),
                            "tipo_regime": tipo_regime,
                            "provavel_terceiro": False,
                        }
                    )

                gravar_chunk_no_postgres(empresas_chunk)
                total_lote += len(empresas_chunk)
                print(f"  -> {total_lote} registros MG processados no lote {idx}...", flush=True)

            total_processado += total_lote
            print(f"Lote {idx} concluido. Subtotal={total_lote}", flush=True)
        except Exception as exc:
            lotes_com_erro += 1
            print(f"  -> ERRO lote {idx}: {type(exc).__name__}: {exc}", flush=True)

    if lotes_com_erro:
        raise RuntimeError(
            f"Sincronizacao incompleta: {lotes_com_erro}/10 lotes falharam. Nenhum disparo deve depender desta carga parcial."
        )

    print("\nAplicando heuristica de e-mails compartilhados...", flush=True)
    with psycopg.connect(settings.database_url) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                with emails_terceiros as (
                    select lower(btrim(email::text)) as email_normalizado
                      from mei_email.empresas
                     where email is not null
                     group by lower(btrim(email::text))
                    having count(*) > 3
                )
                update mei_email.empresas e
                   set provavel_terceiro = true
                 where lower(btrim(e.email::text)) in (
                    select email_normalizado from emails_terceiros
                 );
                """
            )
            count_terceiros = cur.rowcount
        conn.commit()

    print(f"  -> {count_terceiros} registros marcados/reconfirmados como provavel_terceiro.", flush=True)
    print(
        f"\n=== SINCRONIZACAO CONCLUIDA: {total_processado} REGISTROS MG PROCESSADOS ===",
        flush=True,
    )
    print(
        "Novos CNPJs sao inseridos; existentes recebem refresh seguro. "
        "marketing_autorizado, mei_verificado, enviado e opt_out nunca sao reativados pela fonte espelho.",
        flush=True,
    )


if __name__ == "__main__":
    fetch_and_ingest_mg_data()
