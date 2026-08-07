from __future__ import annotations

import math

from fastapi import APIRouter, HTTPException
from psycopg.rows import dict_row

from app.db import get_pool
from app.schemas import CampanhaCreate, CampanhaOut

router = APIRouter(prefix="/campanhas", tags=["campanhas"])
CAMPAIGN_ENQUEUE_ADVISORY_LOCK_ID = 99502026


@router.post("", response_model=CampanhaOut, status_code=201)
def criar_campanha(payload: CampanhaCreate):
    if "{{unsubscribe_url}}" not in payload.corpo_template:
        raise HTTPException(
            status_code=422,
            detail=(
                "corpo_template precisa incluir {{unsubscribe_url}} -- "
                "toda campanha tem que ter link de descadastro."
            ),
        )

    pool = get_pool()
    with pool.connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            # Serializa a montagem de filas para que duas campanhas simultaneas
            # nao selecionem o mesmo e-mail antes de uma delas gravar em envios.
            cur.execute("select pg_advisory_xact_lock(%s)", (CAMPAIGN_ENQUEUE_ADVISORY_LOCK_ID,))

            filtros = ["1 = 1"]
            params: list[object] = []
            if payload.filtro_tipo_regime:
                filtros.append("tipo_regime = %s")
                params.append(payload.filtro_tipo_regime)
            if payload.filtro_uf:
                filtros.append("uf = %s")
                params.append(payload.filtro_uf.upper())

            where_clause = " and ".join(filtros)
            limit_clause = ""
            if payload.limite_empresas is not None:
                limit_clause = " limit %s"
                params.append(payload.limite_empresas)

            cur.execute(
                f"""
                with candidatas as (
                    select cnpj, email, data_abertura,
                           row_number() over (
                               partition by lower(btrim(email::text))
                               order by data_abertura desc nulls last, cnpj
                           ) as posicao_do_email
                      from mei_email.vw_empresas_elegiveis
                     where {where_clause}
                )
                select cnpj, email
                  from candidatas
                 where posicao_do_email = 1
                 order by data_abertura desc nulls last, cnpj
                 {limit_clause}
                """,
                params,
            )
            empresas = cur.fetchall()

            if not empresas:
                raise HTTPException(
                    status_code=422,
                    detail=(
                        "Nenhuma empresa elegivel encontrada com esses filtros "
                        "(ativa, autorizada, sem opt-out/terceiro e nunca enfileirada/contatada)."
                    ),
                )

            cur.execute(
                """
                insert into mei_email.campanhas
                    (nome, assunto, corpo_template, filtro_tipo_regime, filtro_uf, tamanho_lote, status, total_empresas)
                values (%s, %s, %s, %s, %s, %s, 'enfileirada', %s)
                returning id, nome, status, total_empresas, total_enviados,
                          total_falhas, criado_em, iniciado_em, concluido_em
                """,
                (
                    payload.nome,
                    payload.assunto,
                    payload.corpo_template,
                    payload.filtro_tipo_regime,
                    payload.filtro_uf.upper() if payload.filtro_uf else None,
                    payload.tamanho_lote,
                    len(empresas),
                ),
            )
            campanha = cur.fetchone()

            tamanho_lote = payload.tamanho_lote
            total_lotes = math.ceil(len(empresas) / tamanho_lote)

            for numero in range(total_lotes):
                fatia = empresas[numero * tamanho_lote : (numero + 1) * tamanho_lote]
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
                    [(campanha["id"], lote_id, e["cnpj"], e["email"]) for e in fatia],
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
