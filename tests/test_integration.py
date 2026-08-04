from __future__ import annotations

import pytest
import psycopg
from psycopg.rows import dict_row

from app.config import settings
from app.routes.campanhas import criar_campanha
from app.schemas import CampanhaCreate
from worker.worker import processar_lote, pegar_proximo_lote
from app.email_provider import get_email_provider


@pytest.fixture
def clean_db():
    # Limpa as tabelas de campanha/lotes/envios/empresas para rodar os testes com isolamento
    with psycopg.connect(settings.database_url) as conn:
        with conn.cursor() as cur:
            cur.execute("truncate table mei_email.campanhas cascade")
            cur.execute("truncate table mei_email.empresas cascade")
        conn.commit()
    yield
    with psycopg.connect(settings.database_url) as conn:
        with conn.cursor() as cur:
            cur.execute("truncate table mei_email.campanhas cascade")
            cur.execute("truncate table mei_email.empresas cascade")
        conn.commit()


def test_prioridade_e_envio_unico(clean_db):
    # 1. Inserir empresas com diferentes datas de abertura e verificar ordenação
    empresas_teste = [
        # Mais nova
        {
            "cnpj": "11111111000101",
            "razao_social": "EMPRESA NOVA",
            "nome_fantasia": "NOVA",
            "situacao_cadastral": "ATIVA",
            "uf": "MG",
            "email": "nova@example.com",
            "ddd_1": "31",
            "telefone_1": "999990001",
            "data_abertura": "2026-01-01",
            "provavel_terceiro": False,
        },
        # Mais antiga
        {
            "cnpj": "22222222000102",
            "razao_social": "EMPRESA ANTIGA",
            "nome_fantasia": "ANTIGA",
            "situacao_cadastral": "ATIVA",
            "uf": "MG",
            "email": "antiga@example.com",
            "ddd_1": "31",
            "telefone_1": "999990002",
            "data_abertura": "2010-01-01",
            "provavel_terceiro": False,
        },
        # Intermediária
        {
            "cnpj": "33333333000103",
            "razao_social": "EMPRESA INTERMEDIARIA",
            "nome_fantasia": "INTERMEDIARIA",
            "situacao_cadastral": "ATIVA",
            "uf": "MG",
            "email": "intermediaria@example.com",
            "ddd_1": "31",
            "telefone_1": "999990003",
            "data_abertura": "2020-01-01",
            "provavel_terceiro": False,
        },
    ]

    with psycopg.connect(settings.database_url) as conn:
        with conn.cursor() as cur:
            cur.executemany(
                """
                insert into mei_email.empresas
                    (cnpj, razao_social, nome_fantasia, situacao_cadastral,
                     uf, email, ddd_1, telefone_1, data_abertura, provavel_terceiro)
                values
                    (%(cnpj)s, %(razao_social)s, %(nome_fantasia)s,
                     %(situacao_cadastral)s, %(uf)s, %(email)s, %(ddd_1)s, %(telefone_1)s,
                     %(data_abertura)s, %(provavel_terceiro)s)
                """,
                empresas_teste,
            )
        conn.commit()

    # 2. Criar campanha com tamanho_lote=1 para forçar um lote por empresa.
    # Isso permite validar se o lote de menor número contem a empresa mais recente.
    payload = CampanhaCreate(
        nome="Campanha Teste Prioridade",
        assunto="Teste assunto",
        corpo_template="Olá {{razao_social}}. Descadastro: {{unsubscribe_url}}",
        tamanho_lote=1,
    )
    campanha = criar_campanha(payload)

    assert campanha["total_empresas"] == 3

    # Validar a ordem dos envios associados a cada lote (lote 0 -> mais nova, lote 1 -> média, lote 2 -> antiga)
    with psycopg.connect(settings.database_url) as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                select l.numero, e.cnpj, emp.data_abertura
                  from mei_email.envios e
                  join mei_email.lotes l on l.id = e.lote_id
                  join mei_email.empresas emp on emp.cnpj = e.cnpj
                 where e.campanha_id = %s
                 order by l.numero asc
                """,
                (campanha["id"],),
            )
            envios = cur.fetchall()

    assert envios[0]["numero"] == 0
    assert envios[0]["cnpj"] == "11111111000101"  # 2026-01-01 (mais nova)

    assert envios[1]["numero"] == 1
    assert envios[1]["cnpj"] == "33333333000103"  # 2020-01-01 (intermediária)

    assert envios[2]["numero"] == 2
    assert envios[2]["cnpj"] == "22222222000102"  # 2010-01-01 (mais antiga)

    # 3. Processar todos os lotes e garantir que as empresas sejam marcadas como "enviado = True"
    provider = get_email_provider(settings.email_provider)
    for _ in range(3):
        with psycopg.connect(settings.database_url) as conn:
            lote = pegar_proximo_lote(conn)
            assert lote is not None
            processar_lote(conn, lote, provider)

    # Validar no banco se foram marcados como enviado no cadastro
    with psycopg.connect(settings.database_url) as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute("select cnpj, enviado, enviado_em from mei_email.empresas")
            empresas_db = {e["cnpj"]: e for e in cur.fetchall()}

    assert empresas_db["11111111000101"]["enviado"] is True
    assert empresas_db["11111111000101"]["enviado_em"] is not None
    assert empresas_db["22222222000102"]["enviado"] is True
    assert empresas_db["33333333000103"]["enviado"] is True

    # 4. Tentar criar outra campanha e validar que as empresas já enviadas NÃO são selecionadas novamente
    payload_2 = CampanhaCreate(
        nome="Campanha Teste Novo Envio",
        assunto="Teste assunto 2",
        corpo_template="Olá {{razao_social}}. Descadastro: {{unsubscribe_url}}",
        tamanho_lote=100,
    )
    
    # Deve dar erro 422 pois nenhuma empresa elegível resta
    with pytest.raises(Exception) as exc_info:
        criar_campanha(payload_2)
    assert "Nenhuma empresa elegivel encontrada" in str(exc_info.value)
