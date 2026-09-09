"""Ingestao dos dados abertos oficiais de CNPJ -> mei_email.empresas.

A importacao aplica somente a politica operacional atual: empresa ATIVA, e-mail
valido, e-mail sem a palavra contabil e e-mail compartilhado por no maximo 2
CNPJs no arquivo importado.
"""
from __future__ import annotations

import argparse
import csv
import re
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

SITUACAO_CADASTRAL = {
    "01": "NULA",
    "02": "ATIVA",
    "03": "SUSPENSA",
    "04": "INAPTA",
    "08": "BAIXADA",
}

LIMITE_CNPJS_POR_EMAIL_COMPARTILHADO = 2
BASE_DIR = Path(__file__).resolve().parent.parent


def ler_empresas(caminho: Path | None) -> dict[str, str]:
    if caminho is None:
        return {}
    razao_por_basico: dict[str, str] = {}
    with open(caminho, encoding="latin-1", newline="") as f:
        for linha in csv.reader(f, delimiter=";"):
            cnpj_basico, razao_social = linha[0], linha[1]
            razao_por_basico[cnpj_basico.strip().strip('"').upper().zfill(8)] = razao_social.strip().strip('"')
    return razao_por_basico


def ingerir_estabelecimentos(
    caminho: Path,
    razao_por_basico: dict[str, str],
) -> list[dict]:
    empresas: list[dict] = []
    total_linhas = 0
    descartadas_situacao = 0
    descartadas_email = 0

    with open(caminho, encoding="latin-1", newline="") as f:
        for linha in csv.reader(f, delimiter=";"):
            total_linhas += 1
            campo = [c.strip().strip('"') for c in linha]

            cnpj_basico = campo[0].upper().zfill(8)
            cnpj_ordem = campo[1].upper().zfill(4)
            cnpj_dv = campo[2].upper().zfill(2)
            cnpj = f"{cnpj_basico}{cnpj_ordem}{cnpj_dv}"

            uf = campo[19].upper()

            situacao_codigo = campo[5]
            situacao = SITUACAO_CADASTRAL.get(situacao_codigo, situacao_codigo)
            if situacao != "ATIVA":
                descartadas_situacao += 1
                continue

            email = campo[27].strip().lower()
            if not EMAIL_RE.match(email) or "contabil" in email:
                descartadas_email += 1
                continue

            empresas.append(
                {
                    "cnpj": cnpj,
                    "razao_social": razao_por_basico.get(cnpj_basico),
                    "nome_fantasia": campo[4] or None,
                    "situacao_cadastral": situacao,
                    "uf": uf,
                    "email": email,
                    "ddd_1": campo[21] or None,
                    "telefone_1": campo[22] or None,
                    "data_abertura": _parse_data(campo[10]),
                }
            )

    print(f"[ingest] linhas lidas: {total_linhas}")
    print(f"[ingest] descartadas (situacao != ATIVA): {descartadas_situacao}")
    print(f"[ingest] descartadas (sem e-mail valido): {descartadas_email}")
    print(f"[ingest] elegiveis apos filtros basicos: {len(empresas)}")
    return empresas


def _parse_data(valor: str) -> str | None:
    if not valor or valor == "00000000":
        return None
    return f"{valor[0:4]}-{valor[4:6]}-{valor[6:8]}"


def remover_emails_compartilhados(empresas: list[dict]) -> None:
    contagem = Counter(e["email"] for e in empresas)
    antes = len(empresas)
    empresas[:] = [
        e
        for e in empresas
        if contagem[e["email"]] <= LIMITE_CNPJS_POR_EMAIL_COMPARTILHADO
    ]
    descartados = antes - len(empresas)
    print(
        f"[ingest] e-mails repetidos em mais de {LIMITE_CNPJS_POR_EMAIL_COMPARTILHADO} CNPJs "
        f"(descartados): {descartados}"
    )


def gravar_no_banco(empresas: list[dict]) -> None:
    import psycopg
    from app.config import settings

    with psycopg.connect(settings.database_url) as conn:
        with conn.cursor() as cur:
            cur.executemany(
                """
                insert into mei_email.empresas
                    (cnpj, razao_social, nome_fantasia, situacao_cadastral,
                     uf, email, ddd_1, telefone_1, data_abertura)
                values
                    (%(cnpj)s, %(razao_social)s, %(nome_fantasia)s,
                     %(situacao_cadastral)s, %(uf)s, %(email)s, %(ddd_1)s, %(telefone_1)s,
                     %(data_abertura)s)
                on conflict (cnpj) do update set
                    razao_social = excluded.razao_social,
                    nome_fantasia = excluded.nome_fantasia,
                    situacao_cadastral = excluded.situacao_cadastral,
                    uf = excluded.uf,
                    email = excluded.email,
                    ddd_1 = excluded.ddd_1,
                    telefone_1 = excluded.telefone_1,
                    data_abertura = excluded.data_abertura
                    -- opt_out e historico de envio nunca sao sobrescritos
                """,
                empresas,
            )
        conn.commit()
    print(f"[ingest] gravado/atualizado no banco: {len(empresas)} empresas")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--estabelecimentos", type=Path)
    parser.add_argument("--empresas", type=Path)
    parser.add_argument("--sample", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if args.sample:
        estabelecimentos = BASE_DIR / "data" / "sample" / "ESTABELECIMENTOS_fake.csv"
        empresas_arq = BASE_DIR / "data" / "sample" / "EMPRESAS_fake.csv"
    else:
        if not args.estabelecimentos:
            parser.error("--estabelecimentos e obrigatorio (ou use --sample)")
        estabelecimentos = args.estabelecimentos
        empresas_arq = args.empresas

    razao_por_basico = ler_empresas(empresas_arq)
    empresas = ingerir_estabelecimentos(
        estabelecimentos,
        razao_por_basico,
    )
    remover_emails_compartilhados(empresas)

    if args.dry_run:
        print("[ingest] --dry-run: nada foi gravado no banco.")
        for e in empresas[:5]:
            print("  ", e)
        return

    gravar_no_banco(empresas)


if __name__ == "__main__":
    main()
