from __future__ import annotations

import math

from fastapi import APIRouter, HTTPException
from psycopg.rows import dict_row

from app.db import get_pool
from app.schemas import CampanhaCreate, CampanhaOut

router = APIRouter(prefix="/campanhas", tags=["campanhas"])


@router.post("", response_model=CampanhaOut, status_code=201)
def criar_campanha(payload: CampanhaCreate):
    if "{{unsubscribe_url}}" not in payload.corpo_template:
        raise HTTPException(
            status_code=422,
            detail=(
                "corpo_template precisa incluir {{unsubscribe_url}} -- "
                "toda campanha tem que ter link de descadastro (LGPD / "
                "anti-spam), mesmo enquanto o envio real ainda nao existe."
            ),
        )

    pool = get_pool()
    with pool.connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            # A view ja aplica: uf=MG, situacao=ATIVA, opt_out=false,
            # provavel_terceiro=false, email is not null.
            cur.execute(
                f"select cnpj, email from mei_email.vw_empresas_elegiveis "
                f"order by data_abertura desc, cnpj"
            )
            empresas = cur.fetchall()

            if not empresas:
                raise HTTPException(
                    status_code=422,
                    detail=(
                        "Nenhuma empresa elegivel encontrada "
                        "(ja excluindo opt-out, provavel_terceiro "
                        "e fora de MG/ATIVA). Rode o script de ingestao "
                        "primeiro."
                    ),
                )

            cur.execute(
                """
                insert into mei_email.campanhas
                    (nome, assunto, corpo_template, tamanho_lote, status, total_empresas)
                values (%s, %s, %s, %s, 'enfileirada', %s)
                returning id, nome, status, total_empresas, total_enviados,
                          total_falhas, criado_em, iniciado_em, concluido_em
                """,
                (
                    payload.nome,
                    payload.assunto,
                    payload.corpo_template,
                    payload.tamanho_lote,
                    len(empresas),
                ),
            )
            campanha = cur.fetchone()

            tamanho_lote = payload.tamanho_lote
            total_lotes = math.ceil(len(empresas) / tamanho_lote)

            for numero in range(total_lotes):
                fatia = empresas[
                    numero * tamanho_lote : (numero + 1) * tamanho_lote
                ]
                cur.execute(
                    """
                    insert into mei_email.lotes
                        (campanha_id, numero, status, tamanho)
                    values (%s, %s, 'pendente', %s)
                    returning id
                    """,
                    (campanha["id"], numero, len(fatia)),
                )
                lote_id = cur.fetchone()["id"]

                cur.executemany(
                    """
                    insert into mei_email.envios
                        (campanha_id, lote_id, cnpj, email, status)
                    values (%s, %s, %s, %s, 'pendente')
                    """,
                    [
                        (campanha["id"], lote_id, e["cnpj"], e["email"])
                        for e in fatia
                    ],
                )

        conn.commit()

    return campanha


@router.get("/{campanha_id}", response_model=CampanhaOut)
def obter_campanha(campanha_id: str):
    pool = get_pool()
    with pool.connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                select id, nome, status, total_empresas, total_enviados,
                       total_falhas, criado_em, iniciado_em, concluido_em
                  from mei_email.campanhas
                 where id = %s
                """,
                (campanha_id,),
            )
            campanha = cur.fetchone()

    if not campanha:
        raise HTTPException(status_code=404, detail="Campanha nao encontrada")
    return campanha


@router.get("/{campanha_id}/lotes")
def listar_lotes(campanha_id: str):
    pool = get_pool()
    with pool.connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                select id, numero, status, tamanho, tentativas,
                       iniciado_em, concluido_em, erro
                  from mei_email.lotes
                 where campanha_id = %s
                 order by numero
                """,
                (campanha_id,),
            )
            return cur.fetchall()
