"""
Testes da logica de parsing/filtro do script de ingestao, usando os
arquivos fake em data/sample/. Nao precisa de banco: testa as funcoes
puras de importacao sob a politica canonica atual.
"""
from pathlib import Path

from scripts.ingest_estabelecimentos import (
    ingerir_estabelecimentos,
    ler_empresas,
    remover_emails_compartilhados,
)

SAMPLE_DIR = Path(__file__).resolve().parent.parent / "data" / "sample"


def _carregar():
    razao = ler_empresas(SAMPLE_DIR / "EMPRESAS_fake.csv")
    empresas = ingerir_estabelecimentos(
        SAMPLE_DIR / "ESTABELECIMENTOS_fake.csv",
        razao,
    )
    remover_emails_compartilhados(empresas)
    return {e["cnpj"]: e for e in empresas}


def test_nao_filtra_fora_de_mg():
    empresas = _carregar()
    assert "10000013000117" in empresas


def test_filtra_situacao_nao_ativa():
    empresas = _carregar()
    assert "10000014000118" not in empresas


def test_filtra_sem_email():
    empresas = _carregar()
    assert "10000015000119" not in empresas


def test_classificacao_simples_mei_nao_participa_da_elegibilidade():
    empresas = _carregar()
    assert "10000005000109" in empresas


def test_grupo_de_3_cnpjs_e_descartado_na_importacao():
    empresas = _carregar()
    for cnpj in ("10000006000110", "10000007000111", "10000008000112"):
        assert cnpj not in empresas


def test_grupo_de_4_cnpjs_e_descartado_na_importacao():
    empresas = _carregar()
    for cnpj in (
        "10000009000113",
        "10000010000114",
        "10000011000115",
        "10000012000116",
    ):
        assert cnpj not in empresas


def test_razao_social_vem_do_arquivo_empresas():
    empresas = _carregar()
    assert empresas["10000001000105"]["razao_social"] == "PADARIA FAKE 1 LTDA"
