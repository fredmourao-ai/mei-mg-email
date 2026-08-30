"""
Testes da logica de parsing/filtro do script de ingestao, usando os
arquivos fake em data/sample/. Nao precisa de banco -- testa so as funcoes
puras (ler_empresas, ler_simples, ingerir_estabelecimentos,
remover_emails_compartilhados).

Rodar: pytest tests/test_ingest.py -v
"""
from pathlib import Path

from scripts.ingest_estabelecimentos import (
    ingerir_estabelecimentos,
    ler_empresas,
    ler_simples,
    remover_emails_compartilhados,
)

SAMPLE_DIR = Path(__file__).resolve().parent.parent / "data" / "sample"


def _carregar(filtrar_mei: bool):
    razao = ler_empresas(SAMPLE_DIR / "EMPRESAS_fake.csv")
    mei = ler_simples(SAMPLE_DIR / "SIMPLES_fake.csv") if filtrar_mei else {}
    empresas = ingerir_estabelecimentos(
        SAMPLE_DIR / "ESTABELECIMENTOS_fake.csv",
        razao,
        mei,
        filtrar_mei=filtrar_mei,
    )
    remover_emails_compartilhados(empresas)
    return {e["cnpj"]: e for e in empresas}


def test_nao_filtra_fora_de_mg():
    empresas = _carregar(filtrar_mei=False)
    assert "10000013000117" in empresas


def test_filtra_situacao_nao_ativa():
    empresas = _carregar(filtrar_mei=False)
    assert "10000014000118" not in empresas


def test_filtra_sem_email():
    empresas = _carregar(filtrar_mei=False)
    assert "10000015000119" not in empresas


def test_arquivo_simples_nao_filtra_elegibilidade():
    com_filtro = _carregar(filtrar_mei=True)
    sem_filtro = _carregar(filtrar_mei=False)
    assert "10000005000109" in com_filtro
    assert "10000005000109" in sem_filtro


def test_grupo_de_3_cnpjs_e_descartado_na_importacao():
    empresas = _carregar(filtrar_mei=False)
    for cnpj in ("10000006000110", "10000007000111", "10000008000112"):
        assert cnpj not in empresas


def test_grupo_de_4_cnpjs_e_descartado_na_importacao():
    empresas = _carregar(filtrar_mei=False)
    for cnpj in (
        "10000009000113",
        "10000010000114",
        "10000011000115",
        "10000012000116",
    ):
        assert cnpj not in empresas


def test_razao_social_vem_do_arquivo_empresas():
    empresas = _carregar(filtrar_mei=False)
    assert empresas["10000001000105"]["razao_social"] == "PADARIA FAKE 1 LTDA"
