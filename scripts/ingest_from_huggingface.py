import os
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path
import duckdb
import psycopg

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from app.config import settings

# URLs dos arquivos Parquet pré-processados da Receita Federal no HuggingFace CDN
PARQUET_FILES = [
    f"https://huggingface.co/datasets/fluowai/datacorp-cnpj-data/resolve/main/cnpj_prefix_{i:02d}_{(i+9):02d}.parquet"
    for i in range(0, 100, 10)
]

def format_date(dt_str: str | None) -> str | None:
    if not dt_str or len(str(dt_str)) != 8:
        return None
    try:
        s = str(dt_str)
        return f"{s[:4]}-{s[4:6]}-{s[6:8]}"
    except Exception:
        return None

def fetch_and_ingest_mg_data() -> None:
    print("=== INICIANTO EXTRAÇÃO ULTRA-RÁPIDA DE DADOS CNPJ (MG) VIA HUGGINGFACE CDN ===")
    conn_duck = duckdb.connect()
    
    todas_empresas = []
    
    for idx, parquet_url in enumerate(PARQUET_FILES, 1):
        print(f"\n[HuggingFace] Processando lote {idx}/10: {parquet_url}...")
        try:
            # Query filtrando diretamente em memória via HTTP/Parquet
            query = f"""
                SELECT 
                    cnpj_base || ordem || dv AS cnpj,
                    razao_social,
                    fantasia AS nome_fantasia,
                    sit_cadastral,
                    uf,
                    email,
                    ddd1 AS ddd_1,
                    tel1 AS telefone_1,
                    data_sit_cad AS data_abertura
                FROM '{parquet_url}'
                WHERE uf = 'MG'
                  AND sit_cadastral = '02'
                  AND email IS NOT NULL
                  AND trim(email) != ''
            """
            rows = conn_duck.execute(query).fetchall()
            print(f"  -> Encontradas {len(rows)} empresas ativas com e-mail em MG no arquivo {idx}.")
            
            for r in rows:
                cnpj = str(r[0]).zfill(14)
                email = str(r[5]).strip().lower()
                todas_empresas.append({
                    "cnpj": cnpj,
                    "razao_social": r[1] or None,
                    "nome_fantasia": r[2] or None,
                    "situacao_cadastral": "ATIVA",
                    "uf": "MG",
                    "email": email,
                    "ddd_1": str(r[6]).strip() if r[6] else None,
                    "telefone_1": str(r[7]).strip() if r[7] else None,
                    "data_abertura": format_date(r[8]),
                })
        except Exception as e:
            print(f"  -> Erro ao ler lote {idx}: {e}")
            
    print(f"\nTotal de registros extraídos para MG: {len(todas_empresas)}")
    
    if not todas_empresas:
        print("Nenhum registro encontrado. Abortando.")
        return

    # Regra de governança: e-mail em mais de 3 CNPJs é marcado como provavel_terceiro
    print("\nAplicando governança de e-mails repetidos (mais de 3 CNPJs)...")
    contagem_email = Counter(e["email"] for e in todas_empresas if e.get("email"))
    
    terceiros_count = 0
    for e in todas_empresas:
        is_terceiro = contagem_email.get(e["email"], 0) > 3
        e["provavel_terceiro"] = is_terceiro
        if is_terceiro:
            terceiros_count += 1
            
    print(f"  -> {terceiros_count} contatos marcados como provavel_terceiro (e-mail em > 3 empresas).")
    
    # Gravação no Banco de Dados PostgreSQL
    print(f"\nGravando {len(todas_empresas)} empresas no PostgreSQL (mei_email.empresas)...")
    with psycopg.connect(settings.database_url) as conn_pg:
        with conn_pg.cursor() as cur:
            cur.executemany(
                """
                insert into mei_email.empresas
                    (cnpj, razao_social, nome_fantasia, situacao_cadastral,
                     uf, email, ddd_1, telefone_1, data_abertura, provavel_terceiro)
                values
                    (%(cnpj)s, %(razao_social)s, %(nome_fantasia)s,
                     %(situacao_cadastral)s, %(uf)s, %(email)s, %(ddd_1)s, %(telefone_1)s,
                     %(data_abertura)s, %(provavel_terceiro)s)
                on conflict (cnpj) do update set
                    razao_social = excluded.razao_social,
                    nome_fantasia = excluded.nome_fantasia,
                    situacao_cadastral = excluded.situacao_cadastral,
                    email = excluded.email,
                    ddd_1 = excluded.ddd_1,
                    telefone_1 = excluded.telefone_1,
                    data_abertura = excluded.data_abertura,
                    provavel_terceiro = excluded.provavel_terceiro
                    -- enviado e opt_out NUNCA são sobrescritos
                """,
                todas_empresas,
            )
        conn_pg.commit()
        
    print("\n=== INGESTÃO CONCLUÍDA COM SUCESSO! ===")

if __name__ == "__main__":
    fetch_and_ingest_mg_data()
