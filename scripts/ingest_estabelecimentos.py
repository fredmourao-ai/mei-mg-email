"""
Ingestao dos dados abertos oficiais de CNPJ/Simples -> mei_email.empresas.

Quando o arquivo SIMPLES e informado, OPCAO_PELO_MEI='S' e a fonte que pode
marcar mei_verificado=true. Sem esse arquivo, registros podem ser armazenados
para atualizacao cadastral, mas jamais sao tratados como MEI verificado.
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

LIMITE_CNPJS_POR_EMAIL_TERCEIRO = 3
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


def ler_simples(caminho: Path | None) -> dict[str, bool]:
    """cnpj_basico -> opcao_pelo_mei. A coluna e a fonte oficial de verificacao."""
    if caminho is None:
        return {}
    mei_por_basico: dict[str, bool] = {}
    with open(caminho, encoding="latin-1", newline="") as f:
        for linha in csv.reader(f, delimiter=";"):
            cnpj_basico, opcao_mei = linha[0], linha[4]
            basico = cnpj_basico.strip().strip('"').upper().zfill(8)
            mei_por_basico[basico] = opcao_mei.strip().strip('"').upper() == "S"
    return mei_por_basico


def ingerir_estabelecimentos(
    caminho: Path,
    razao_por_basico: dict[str, str],
    mei_por_basico: dict[str, bool],
    filtrar_mei: bool,
) -> list[dict]:
    empresas: list[dict] = []
    total_linhas = 0
    descartadas_uf = 0
    descartadas_situacao = 0
    descartadas_mei = 0
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
            if uf != "MG":
                descartadas_uf += 1
                continue

            situacao_codigo = campo[5]
            situacao = SITUACAO_CADASTRAL.get(situacao_codigo, situacao_codigo)
            if situacao != "ATIVA":
                descartadas_situacao += 1
                continue

            mei_confirmado = bool(mei_por_basico.get(cnpj_basico, False)) if filtrar_mei else False
            if filtrar_mei and not mei_confirmado:
                descartadas_mei += 1
                continue

            email = campo[27].lower()
            if not EMAIL_RE.match(email):
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
                    "tipo_regime": "MEI" if mei_confirmado else "NAO_VERIFICADO",
                    "mei_verificado": mei_confirmado,
                    "mei_verificado_origem": "receita_simples_opcao_mei" if mei_confirmado else None,
                }
            )

    print(f"[ingest] linhas lidas: {total_linhas}")
    print(f"[ingest] descartadas (UF != MG): {descartadas_uf}")
    print(f"[ingest] descartadas (situacao != ATIVA): {descartadas_situacao}")
    if filtrar_mei:
        print(f"[ingest] descartadas (nao optante MEI): {descartadas_mei}")
        print("[ingest] MEI verificado pela coluna OPCAO_PELO_MEI do arquivo SIMPLES.")
    else:
        print(
            "[ingest] AVISO: arquivo SIMPLES nao informado -- nenhum registro sera marcado como MEI verificado."
        )
    print(f"[ingest] descartadas (sem e-mail valido): {descartadas_email}")
    print(f"[ingest] elegiveis apos filtros basicos: {len(empresas)}")
    return empresas


def _parse_data(valor: str) -> str | None:
    if not valor or valor == "00000000":
        return None
    return f"{valor[0:4]}-{valor[4:6]}-{valor[6:8]}"


def marcar_provaveis_terceiros(empresas: list[dict]) -> None:
    contagem = Counter(e["email"] for e in empresas)
    marcados = 0
    for e in empresas:
        e["provavel_terceiro"] = contagem[e["email"]] > LIMITE_CNPJS_POR_EMAIL_TERCEIRO
        if e["provavel_terceiro"]:
            marcados += 1
    print(
        f"[ingest] e-mails repetidos em mais de {LIMITE_CNPJS_POR_EMAIL_TERCEIRO} CNPJs "
        f"(marcados provavel_terceiro): {marcados}"
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
                     uf, email, ddd_1, telefone_1, data_abertura, provavel_terceiro,
                     tipo_regime, mei_verificado, mei_verificado_em, mei_verificado_origem)
                values
                    (%(cnpj)s, %(razao_social)s, %(nome_fantasia)s,
                     %(situacao_cadastral)s, %(uf)s, %(email)s, %(ddd_1)s, %(telefone_1)s,
                     %(data_abertura)s, %(provavel_terceiro)s, %(tipo_regime)s,
                     %(mei_verificado)s,
                     case when %(mei_verificado)s then now() else null end,
                     %(mei_verificado_origem)s)
                on conflict (cnpj) do update set
                    razao_social = excluded.razao_social,
                    nome_fantasia = excluded.nome_fantasia,
                    situacao_cadastral = excluded.situacao_cadastral,
                    email = excluded.email,
                    ddd_1 = excluded.ddd_1,
                    telefone_1 = excluded.telefone_1,
                    data_abertura = excluded.data_abertura,
                    provavel_terceiro = excluded.provavel_terceiro,
                    tipo_regime = case
                        when excluded.mei_verificado then 'MEI'
                        else mei_email.empresas.tipo_regime
                    end,
                    mei_verificado = mei_email.empresas.mei_verificado or excluded.mei_verificado,
                    mei_verificado_em = case
                        when excluded.mei_verificado then coalesce(mei_email.empresas.mei_verificado_em, now())
                        else mei_email.empresas.mei_verificado_em
                    end,
                    mei_verificado_origem = case
                        when excluded.mei_verificado then excluded.mei_verificado_origem
                        else mei_email.empresas.mei_verificado_origem
                    end
                    -- opt_out, marketing_autorizado e historico de envio nunca sao sobrescritos
                """,
                empresas,
            )
        conn.commit()
    print(f"[ingest] gravado/atualizado no banco: {len(empresas)} empresas")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--estabelecimentos", type=Path)
    parser.add_argument("--empresas", type=Path)
    parser.add_argument("--simples", type=Path)
    parser.add_argument("--sample", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if args.sample:
        estabelecimentos = BASE_DIR / "data" / "sample" / "ESTABELECIMENTOS_fake.csv"
        empresas_arq = BASE_DIR / "data" / "sample" / "EMPRESAS_fake.csv"
        simples_arq = BASE_DIR / "data" / "sample" / "SIMPLES_fake.csv"
    else:
        if not args.estabelecimentos:
            parser.error("--estabelecimentos e obrigatorio (ou use --sample)")
        estabelecimentos = args.estabelecimentos
        empresas_arq = args.empresas
        simples_arq = args.simples

    razao_por_basico = ler_empresas(empresas_arq)
    mei_por_basico = ler_simples(simples_arq)
    empresas = ingerir_estabelecimentos(
        estabelecimentos,
        razao_por_basico,
        mei_por_basico,
        filtrar_mei=bool(simples_arq),
    )
    marcar_provaveis_terceiros(empresas)

    if args.dry_run:
        print("[ingest] --dry-run: nada foi gravado no banco.")
        for e in empresas[:5]:
            print("  ", e)
        return

    gravar_no_banco(empresas)


if __name__ == "__main__":
    main()
