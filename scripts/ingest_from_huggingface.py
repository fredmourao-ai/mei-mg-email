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

POLITICA_ORIGEM = "politica_importacao_operador_2026-08-13_huggingface_upsert"


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


def classificar_regime_espelho(
    nat_juridica: str,
    porte: str,
) -> tuple[str, bool]:
    """Return regime and whether the operator-approved MEI rule matched.

    Completely ambiguous mirror rows remain candidates and are not verified.
    Known non-MEI shapes remain SIMPLES/OUTROS. The audited operator override
    applies only when the explicit operational MEI rule matches.
    """
    is_mei_operacional = nat_juridica == "2135" or porte == "01"
    if is_mei_operacional:
        return "MEI", True
    if porte in {"03", "05"} or nat_juridica in {"2062", "2305"}:
        return "SIMPLES", False
    if not nat_juridica and not porte:
        tipo_regime = "MEI_CANDIDATO"
        return tipo_regime, False
    return "OUTROS", False


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
                     uf, email, ddd_1, telefone_1, data_abertura, tipo_regime,
                     provavel_terceiro, marketing_autorizado,
                     marketing_autorizado_em, marketing_autorizado_origem,
                     mei_verificado, mei_verificado_em, mei_verificado_origem)
                values
                    (%(cnpj)s, %(razao_social)s, %(nome_fantasia)s,
                     %(situacao_cadastral)s, %(uf)s, %(email)s, %(ddd_1)s,
                     %(telefone_1)s, %(data_abertura)s, %(tipo_regime)s,
                     %(provavel_terceiro)s, %(marketing_autorizado)s,
                     case when %(marketing_autorizado)s then now() else null end,
                     %(marketing_autorizado_origem)s,
                     %(mei_verificado)s,
                     case when %(mei_verificado)s then now() else null end,
                     %(mei_verificado_origem)s)
                on conflict (cnpj) do update set
                    situacao_cadastral = excluded.situacao_cadastral,
                    tipo_regime = case
                        when excluded.tipo_regime = 'MEI' then 'MEI'
                        when mei_email.empresas.mei_verificado
                            then mei_email.empresas.tipo_regime
                        else excluded.tipo_regime
                    end,
                    marketing_autorizado = case
                        when excluded.tipo_regime = 'MEI' then true
                        else mei_email.empresas.marketing_autorizado
                    end,
                    marketing_autorizado_em = case
                        when excluded.tipo_regime = 'MEI'
                        then coalesce(
                            mei_email.empresas.marketing_autorizado_em,
                            now()
                        )
                        else mei_email.empresas.marketing_autorizado_em
                    end,
                    marketing_autorizado_origem = case
                        when excluded.tipo_regime = 'MEI'
                        then coalesce(
                            nullif(
                                btrim(
                                    mei_email.empresas.marketing_autorizado_origem
                                ),
                                ''
                            ),
                            excluded.marketing_autorizado_origem
                        )
                        else mei_email.empresas.marketing_autorizado_origem
                    end,
                    mei_verificado =
                        mei_email.empresas.mei_verificado
                        or excluded.mei_verificado,
                    mei_verificado_em = case
                        when excluded.mei_verificado
                        then coalesce(
                            mei_email.empresas.mei_verificado_em,
                            now()
                        )
                        else mei_email.empresas.mei_verificado_em
                    end,
                    mei_verificado_origem = case
                        when excluded.mei_verificado
                        then coalesce(
                            nullif(
                                btrim(
                                    mei_email.empresas.mei_verificado_origem
                                ),
                                ''
                            ),
                            excluded.mei_verificado_origem
                        )
                        else mei_email.empresas.mei_verificado_origem
                    end
                    -- opt_out, enviado e supressoes nunca sao sobrescritos.
                """,
                empresas,
            )
        conn.commit()


def fetch_and_ingest_mg_data() -> None:
    print(
        "=== SINCRONIZACAO CNPJ MG VIA FONTE ESPELHO CONFIGURADA ===",
        flush=True,
    )
    print(
        "NOTE=MEI por regra operacional explicita recebe override auditavel; "
        "linhas ambiguas permanecem MEI_CANDIDATO sem verificacao.",
        flush=True,
    )
    conn_duck = duckdb.connect()
    total_processado = 0
    total_mei = 0
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
                    data_sit_cad as data_abertura,
                    nat_juridica,
                    porte
                from '{parquet_url}'
                where email is not null
                  and trim(email) != ''
                  and upper(trim(uf)) = 'MG'
            """
            cursor = conn_duck.execute(query)

            total_lote = 0
            mei_lote = 0
            while True:
                rows = cursor.fetchmany(10000)
                if not rows:
                    break

                empresas_chunk = []
                for row in rows:
                    cnpj = str(row[0]).strip().upper().zfill(14)
                    email = str(row[5]).strip().lower()
                    nat_jur = str(row[9]).strip() if row[9] else ""
                    porte = str(row[10]).strip() if row[10] else ""
                    tipo_regime, is_mei_operacional = (
                        classificar_regime_espelho(nat_jur, porte)
                    )
                    if is_mei_operacional:
                        mei_lote += 1

                    empresas_chunk.append(
                        {
                            "cnpj": cnpj,
                            "razao_social": clean_str(row[1]),
                            "nome_fantasia": clean_str(row[2]),
                            "situacao_cadastral": situacao_cadastral(row[3]),
                            "uf": "MG",
                            "email": email,
                            "ddd_1": clean_str(row[6], 3),
                            "telefone_1": clean_str(row[7], 15),
                            "data_abertura": format_date(row[8]),
                            "tipo_regime": tipo_regime,
                            "provavel_terceiro": False,
                            "marketing_autorizado": is_mei_operacional,
                            "marketing_autorizado_origem": (
                                POLITICA_ORIGEM
                                if is_mei_operacional
                                else None
                            ),
                            "mei_verificado": is_mei_operacional,
                            "mei_verificado_origem": (
                                POLITICA_ORIGEM
                                if is_mei_operacional
                                else None
                            ),
                        }
                    )

                gravar_chunk_no_postgres(empresas_chunk)
                total_lote += len(empresas_chunk)
                print(
                    f"  -> {total_lote} registros MG processados "
                    f"no lote {idx}...",
                    flush=True,
                )

            total_processado += total_lote
            total_mei += mei_lote
            print(
                f"Lote {idx} concluido. Subtotal={total_lote} "
                f"mei_operacional={mei_lote}",
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
                 )
                """
            )
            count_terceiros = cur.rowcount
        conn.commit()

    print(
        f"  -> {count_terceiros} registros marcados/reconfirmados "
        "como provavel_terceiro.",
        flush=True,
    )
    print(
        f"\n=== SINCRONIZACAO CONCLUIDA: {total_processado} REGISTROS "
        f"MG PROCESSADOS; MEI={total_mei} ===",
        flush=True,
    )
    print(
        "MEI por regra operacional entra com override auditavel; "
        "opt_out e enviado permanecem soberanos.",
        flush=True,
    )


if __name__ == "__main__":
    fetch_and_ingest_mg_data()
