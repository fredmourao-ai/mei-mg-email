"""
Ingestao dos dados abertos de CNPJ da Receita Federal (dados.gov.br) ->
tabela mei_email.empresas, filtrado para MEIs ativos de MG.

Os arquivos oficiais sao .csv (na pratica ; separado, sem header, encoding
latin-1/ISO-8859-1), um por tipo de dado, layout fixo por posicao de coluna
(documentado no "Layout dos Dados Abertos do CNPJ" do proprio dados.gov.br).
Usa-se pelo menos 3 arquivos, unidos pelo CNPJ_BASICO (8 primeiros digitos):

  - ESTABELECIMENTOS*.csv  (obrigatorio) -- endereco, UF, situacao,
                             telefone, e-mail. Um estabelecimento por linha.
  - EMPRESAS*.csv          (opcional)    -- razao social, porte.
  - SIMPLES*.csv           (opcional)    -- flag OPCAO_PELO_MEI (S/N).
                             Sem esse arquivo, o filtro de MEI e pulado (so
                             filtra UF=MG + situacao ATIVA) e um aviso e
                             impresso -- os dados que chegarem incluem
                             empresas de outros portes, nao so MEI.

O arquivo real ainda nao foi fornecido. Os arquivos em data/sample/*.csv sao
FAKE, pequenos, no mesmo layout posicional, so pra validar a esteira
(ingestao -> banco -> API -> worker dry-run) antes do dado de verdade
chegar. Rode com --sample pra usar eles.

Uso:
  python scripts/ingest_estabelecimentos.py --sample
  python scripts/ingest_estabelecimentos.py \
      --estabelecimentos data/receita/ESTABELECIMENTOS0.csv \
      --empresas data/receita/EMPRESAS0.csv \
      --simples data/receita/SIMPLES.csv
"""
from __future__ import annotations

import argparse
import csv
import re
import sys
from collections import Counter
from pathlib import Path

# psycopg e app.config so sao importados dentro de gravar_no_banco(), de
# proposito: assim as funcoes de parse/filtro (usadas nos testes em
# tests/test_ingest.py) continuam importaveis mesmo sem driver de banco
# instalado nem .env configurado -- so precisa deles quem for gravar de
# verdade.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

SITUACAO_CADASTRAL = {
    "01": "NULA",
    "02": "ATIVA",
    "03": "SUSPENSA",
    "04": "INAPTA",
    "08": "BAIXADA",
}

# Limite da heuristica "provavel terceiro" (contador/escritorio
# compartilhando um unico e-mail entre varios CNPJs de clientes). Ver
# decisao no README / pedido original: "mais de 3 CNPJs diferentes".
LIMITE_CNPJS_POR_EMAIL_TERCEIRO = 3

BASE_DIR = Path(__file__).resolve().parent.parent


def ler_empresas(caminho: Path | None) -> dict[str, str]:
    """cnpj_basico -> razao_social. Vazio se o arquivo nao foi passado."""
    if caminho is None:
        return {}
    razao_por_basico: dict[str, str] = {}
    with open(caminho, encoding="latin-1", newline="") as f:
        for linha in csv.reader(f, delimiter=";"):
            cnpj_basico, razao_social = linha[0], linha[1]
            razao_por_basico[cnpj_basico] = razao_social.strip().strip('"')
    return razao_por_basico


def ler_simples(caminho: Path | None) -> dict[str, bool]:
    """cnpj_basico -> opcao_pelo_mei (bool). Vazio se o arquivo nao foi passado."""
    if caminho is None:
        return {}
    mei_por_basico: dict[str, bool] = {}
    with open(caminho, encoding="latin-1", newline="") as f:
        for linha in csv.reader(f, delimiter=";"):
            cnpj_basico, opcao_mei = linha[0], linha[4]
            mei_por_basico[cnpj_basico] = opcao_mei.strip().strip('"').upper() == "S"
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

            cnpj_basico = campo[0].zfill(8)
            cnpj_ordem = campo[1].zfill(4)
            cnpj_dv = campo[2].zfill(2)
            cnpj = f"{cnpj_basico}{cnpj_ordem}{cnpj_dv}"

            uf = campo[19]
            if uf != "MG":
                descartadas_uf += 1
                continue

            situacao_codigo = campo[5]
            situacao = SITUACAO_CADASTRAL.get(situacao_codigo, situacao_codigo)
            if situacao != "ATIVA":
                descartadas_situacao += 1
                continue

            if filtrar_mei and not mei_por_basico.get(cnpj_basico, False):
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
                    "cnae": campo[11] or None,
                    "municipio": campo[20] or None,
                    "uf": uf,
                    "cep": campo[18] or None,
                    "email": email,
                    "ddd_1": campo[21] or None,
                    "telefone_1": campo[22] or None,
                    "data_abertura": _parse_data(campo[10]),
                }
            )

    print(f"[ingest] linhas lidas: {total_linhas}")
    print(f"[ingest] descartadas (UF != MG): {descartadas_uf}")
    print(f"[ingest] descartadas (situacao != ATIVA): {descartadas_situacao}")
    if filtrar_mei:
        print(f"[ingest] descartadas (nao optante MEI): {descartadas_mei}")
    else:
        print(
            "[ingest] AVISO: arquivo SIMPLES nao informado -- filtro de MEI "
            "NAO aplicado. Os dados incluem qualquer porte de empresa ativa "
            "em MG com e-mail, nao so MEI."
        )
    print(f"[ingest] descartadas (sem e-mail valido): {descartadas_email}")
    print(f"[ingest] elegiveis apos filtros basicos: {len(empresas)}")
    return empresas


def _parse_data(valor: str) -> str | None:
    # Layout da Receita: AAAAMMDD, "00000000" quando vazio.
    if not valor or valor == "00000000":
        return None
    return f"{valor[0:4]}-{valor[4:6]}-{valor[6:8]}"


def marcar_provaveis_terceiros(empresas: list[dict]) -> None:
    """Regra de limpeza: e-mail que aparece em mais de N CNPJs diferentes
    e provavelmente de um contador/escritorio, nao do MEI direto. Marca
    (nao remove) -- fica auditavel e a view vw_empresas_elegiveis que
    exclui do disparo."""
    contagem = Counter(e["email"] for e in empresas)
    marcados = 0
    for e in empresas:
        if contagem[e["email"]] > LIMITE_CNPJS_POR_EMAIL_TERCEIRO:
            e["provavel_terceiro"] = True
            marcados += 1
        else:
            e["provavel_terceiro"] = False
    print(
        f"[ingest] e-mails repetidos em mais de "
        f"{LIMITE_CNPJS_POR_EMAIL_TERCEIRO} CNPJs (marcados provavel_terceiro): "
        f"{marcados}"
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
                     cnae, municipio, uf, cep, email, ddd_1, telefone_1,
                     data_abertura, provavel_terceiro)
                values
                    (%(cnpj)s, %(razao_social)s, %(nome_fantasia)s,
                     %(situacao_cadastral)s, %(cnae)s, %(municipio)s,
                     %(uf)s, %(cep)s, %(email)s, %(ddd_1)s, %(telefone_1)s,
                     %(data_abertura)s, %(provavel_terceiro)s)
                on conflict (cnpj) do update set
                    razao_social = excluded.razao_social,
                    nome_fantasia = excluded.nome_fantasia,
                    situacao_cadastral = excluded.situacao_cadastral,
                    cnae = excluded.cnae,
                    municipio = excluded.municipio,
                    cep = excluded.cep,
                    email = excluded.email,
                    ddd_1 = excluded.ddd_1,
                    telefone_1 = excluded.telefone_1,
                    data_abertura = excluded.data_abertura,
                    provavel_terceiro = excluded.provavel_terceiro
                    -- opt_out NUNCA e sobrescrito por reimportacao
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
    parser.add_argument(
        "--sample",
        action="store_true",
        help="Usa os arquivos fake em data/sample/ em vez de dados reais.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Roda tudo (parse + filtros + regra de terceiro) mas nao grava no banco.",
    )
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
