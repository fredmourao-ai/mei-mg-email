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
            cur.execute("truncate table mei_email.email_suppressions cascade")
        conn.commit()
    yield
    with psycopg.connect(settings.database_url) as conn:
        with conn.cursor() as cur:
            cur.execute("truncate table mei_email.campanhas cascade")
            cur.execute("truncate table mei_email.empresas cascade")
            cur.execute("truncate table mei_email.email_suppressions cascade")
        conn.commit()


def test_prioridade_e_envio_unico(clean_db):
    # Fixtures de teste sao explicitamente autorizadas para validar o fluxo de campanha.
    empresas_teste = [
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
                         uf, email, ddd_1, telefone_1, data_abertura, provavel_terceiro,
                         marketing_autorizado, marketing_autorizado_em, marketing_autorizado_origem,
                         mei_verificado, mei_verificado_em, mei_verificado_origem)
                values
                    (%(cnpj)s, %(razao_social)s, %(nome_fantasia)s,
                     %(situacao_cadastral)s, %(uf)s, %(email)s, %(ddd_1)s, %(telefone_1)s,
                         %(data_abertura)s, %(provavel_terceiro)s,
                         true, now(), 'fixture_teste',
                         true, now(), 'fixture_teste')
                """,
                empresas_teste,
            )
        conn.commit()

    payload = CampanhaCreate(
        nome="Campanha Teste Prioridade",
        assunto="Teste assunto",
        corpo_template="Olá {{razao_social}}. Descadastro: {{unsubscribe_url}}",
        tamanho_lote=1,
    )
    campanha = criar_campanha(payload)

    assert campanha["total_empresas"] == 3

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
    assert envios[0]["cnpj"] == "11111111000101"
    assert envios[1]["numero"] == 1
    assert envios[1]["cnpj"] == "33333333000103"
    assert envios[2]["numero"] == 2
    assert envios[2]["cnpj"] == "22222222000102"

    provider = get_email_provider("dryrun")
    for _ in range(3):
        with psycopg.connect(settings.database_url) as conn:
            lote = pegar_proximo_lote(conn)
            assert lote is not None
            processar_lote(conn, lote, provider)

    with psycopg.connect(settings.database_url) as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute("select cnpj, enviado, enviado_em from mei_email.empresas")
            empresas_db = {e["cnpj"]: e for e in cur.fetchall()}

    assert empresas_db["11111111000101"]["enviado"] is False
    assert empresas_db["11111111000101"]["enviado_em"] is None
    assert empresas_db["22222222000102"]["enviado"] is False
    assert empresas_db["33333333000103"]["enviado"] is False

    with psycopg.connect(settings.database_url) as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                select status, submitted_at, graph_request_id, last_error, enviado_em
                  from mei_email.envios
                 where campanha_id = %s
                 order by criado_em asc
                """,
                (campanha["id"],),
            )
            envios_db = cur.fetchall()

    assert all(row["status"] == "submitted" for row in envios_db)
    assert all(row["submitted_at"] is not None for row in envios_db)
    assert all(row["graph_request_id"] is not None for row in envios_db)
    assert all(row["last_error"] is None for row in envios_db)
    assert all(row["enviado_em"] is not None for row in envios_db)

    payload_2 = CampanhaCreate(
        nome="Campanha Teste Novo Envio",
        assunto="Teste assunto 2",
        corpo_template="Olá {{razao_social}}. Descadastro: {{unsubscribe_url}}",
        tamanho_lote=100,
    )
    with pytest.raises(Exception) as exc_info:
        criar_campanha(payload_2)
    assert "Nenhuma empresa elegivel encontrada" in str(exc_info.value)


def test_email_duplicado_recebe_apenas_um_envio(clean_db):
    with psycopg.connect(settings.database_url) as conn:
        with conn.cursor() as cur:
            cur.executemany(
                """
                insert into mei_email.empresas
                    (cnpj, razao_social, nome_fantasia, situacao_cadastral,
                         uf, email, data_abertura, provavel_terceiro,
                         marketing_autorizado, marketing_autorizado_em, marketing_autorizado_origem,
                         mei_verificado, mei_verificado_em, mei_verificado_origem)
                values
                    (%(cnpj)s, %(razao_social)s, %(nome_fantasia)s,
                         'ATIVA', 'MG', 'contato-compartilhado@example.com',
                         %(data_abertura)s, false, true, now(), 'fixture_teste',
                         true, now(), 'fixture_teste')
                """,
                [
                    {
                        "cnpj": "44444444000104",
                        "razao_social": "EMPRESA ANTIGA",
                        "nome_fantasia": "ANTIGA",
                        "data_abertura": "2020-01-01",
                    },
                    {
                        "cnpj": "55555555000105",
                        "razao_social": "EMPRESA NOVA",
                        "nome_fantasia": "NOVA",
                        "data_abertura": "2026-01-01",
                    },
                ],
            )
        conn.commit()

    campanha = criar_campanha(
        CampanhaCreate(
            nome="Campanha sem duplicidade de e-mail",
            assunto="Teste",
            corpo_template="Olá. Descadastro: {{unsubscribe_url}}",
            tamanho_lote=1,
            filtro_uf="MG",
        )
    )

    assert campanha["total_empresas"] == 1
    with psycopg.connect(settings.database_url) as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                "select cnpj from mei_email.envios where campanha_id = %s",
                (campanha["id"],),
            )
            assert cur.fetchone()["cnpj"] == "55555555000105"

    with psycopg.connect(settings.database_url) as conn:
        lote = pegar_proximo_lote(conn)
        processar_lote(conn, lote, get_email_provider("dryrun"))

    with psycopg.connect(settings.database_url) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                select count(*)
                  from mei_email.empresas
                 where email = 'contato-compartilhado@example.com'
                   and enviado = true
                """
            )
            assert cur.fetchone()[0] == 0
