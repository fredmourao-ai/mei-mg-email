import os
import sys
from datetime import datetime
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

def format_date(dt_str: str | None) -> str | None:
    if not dt_str:
        return None
    s = str(dt_str).strip()
    if len(s) != 8 or not s.isdigit():
        return None
    try:
        return f"{s[:4]}-{s[4:6]}-{s[6:8]}"
    except Exception:
        return None

def clean_str(val: str | None, max_len: int | None = None) -> str | None:
    if not val:
        return None
    s = str(val).strip()
    if not s:
        return None
    if max_len:
        s = s[:max_len]
    return s

def gravar_chunk_no_postgres(empresas: list[dict]) -> None:
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
                    razao_social = excluded.razao_social,
                    nome_fantasia = excluded.nome_fantasia,
                    situacao_cadastral = excluded.situacao_cadastral,
                    email = excluded.email,
                    ddd_1 = excluded.ddd_1,
                    telefone_1 = excluded.telefone_1,
                    data_abertura = excluded.data_abertura,
                    tipo_regime = excluded.tipo_regime
                    -- enviado e opt_out NUNCA são sobrescritos por reimportação
                """,
                empresas,
            )
        conn.commit()

def fetch_and_ingest_mg_data() -> None:
    print("=== INICIANDO EXTRAÇÃO DE ALTA PERFORMANCE CNPJ (MG) VIA HUGGINGFACE ===", flush=True)
    conn_duck = duckdb.connect()
    
    total_geral = 0
    
    for idx, parquet_url in enumerate(PARQUET_FILES, 1):
        print(f"\n[HuggingFace] Lendo lote {idx}/10: {parquet_url}...", flush=True)
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
                WHERE uf = 'MG'
                  AND sit_cadastral = '02'
                  AND email IS NOT NULL
                  AND trim(email) != ''
            """
            cursor = conn_duck.execute(query)
            
            total_lote = 0
            while True:
                rows = cursor.fetchmany(10000)
                if not rows:
                    break
                
                empresas_chunk = []
                for r in rows:
                    cnpj = str(r[0]).zfill(14)
                    email = str(r[5]).strip().lower()
                    nat_jur = str(r[9]).strip() if r[9] else ""
                    porte = str(r[10]).strip() if r[10] else ""
                    
                    # Classificação: MEI (Empresário Individual / Porte ME 01), SIMPLES (ME/EPP 03/05 ou LTDA/EIRELI), OUTROS
                    if nat_jur == '2135' or porte == '01':
                        tipo_regime = 'MEI'
                    elif porte in ('03', '05') or nat_jur in ('2062', '2305'):
                        tipo_regime = 'SIMPLES'
                    else:
                        tipo_regime = 'OUTROS'
                    
                    empresas_chunk.append({
                        "cnpj": cnpj,
                        "razao_social": clean_str(r[1]),
                        "nome_fantasia": clean_str(r[2]),
                        "situacao_cadastral": "ATIVA",
                        "uf": "MG",
                        "email": email,
                        "ddd_1": clean_str(r[6], 3),
                        "telefone_1": clean_str(r[7], 15),
                        "data_abertura": format_date(r[8]),
                        "tipo_regime": tipo_regime,
                        "provavel_terceiro": False,
                    })
                
                gravar_chunk_no_postgres(empresas_chunk)
                total_lote += len(empresas_chunk)
                print(f"  -> {total_lote} empresas gravadas do lote {idx}...", flush=True)
                
            total_geral += total_lote
            print(f"Lote {idx} concluído! Subtotal: {total_lote} empresas em MG.", flush=True)
            
        except Exception as e:
            print(f"  -> Erro ao processar lote {idx}: {e}", flush=True)

    # Atualiza a marcação de provável terceiro (e-mail em > 3 empresas) direto no Postgres via SQL
    print("\nAplicando pós-processamento de e-mails duplicados em mais de 3 empresas no Postgres...", flush=True)
    with psycopg.connect(settings.database_url) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                with emails_terceiros as (
                    select email
                      from mei_email.empresas
                     where email is not null
                     group by email
                    having count(*) > 3
                )
                update mei_email.empresas
                   set provavel_terceiro = true
                 where email in (select email from emails_terceiros);
                """
            )
            count_terceiros = cur.rowcount
        conn.commit()
    print(f"  -> {count_terceiros} empresas marcadas como provavel_terceiro = true no banco.", flush=True)
    print(f"\n=== INGESTÃO CONCLUÍDA! TOTAL GRAVADO NO BANCO: {total_geral} EMPRESAS EM MG ===", flush=True)

if __name__ == "__main__":
    fetch_and_ingest_mg_data()
