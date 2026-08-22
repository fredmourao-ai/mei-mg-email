from __future__ import annotations

import math

from fastapi import APIRouter, HTTPException
from psycopg.rows import dict_row

from app.config import settings
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
            # nao selecionem o mesmo e-mail nem comprometam a mesma cota diaria.
            cur.execute("select pg_advisory_xact_lock(%s)", (CAMPAIGN_ENQUEUE_ADVISORY_LOCK_ID,))

            cur.execute(
                """
                select
                  count(*) filter (
                    where status::text in ('submitted', 'enviado')
                      and enviado_em >= now() - interval '24 hours'
                  ) as consumidos_24h,
                  count(*) filter (where status::text in ('pendente', 'enviando')) as comprometidos
                from mei_email.envios
                """
            )
            capacidade = cur.fetchone()
            ja_comprometido = int(capacidade["consumidos_24h"] or 0) + int(capacidade["comprometidos"] or 0)
            limite_operacional = min(settings.meta_envios_por_dia, settings.max_envios_por_dia)
            restante = max(limite_operacional - ja_comprometido, 0)
            if restante <= 0:
                raise HTTPException(
                    status_code=422,
                    detail=(
                        f"Meta movel de 24h ja comprometida: {ja_comprometido}/{limite_operacional}."
                    ),
                )

            filtros = ["situacao_cadastral = 'ATIVA'", "email is not null", "btrim(email::text) <> ''", "mei_email.is_valid_email_address(email)", "position('contabil' in lower(btrim(email::text))) = 0"]
            params: list[object] = []
            where_clause = " and ".join(filtros)
            requested_limit = payload.limite_empresas if payload.limite_empresas is not None else restante
            effective_limit = min(requested_limit, restante)
            params.append(effective_limit)

            cur.execute(
                f"""
                with candidatas as (
                    select cnpj, email, data_abertura,
                           row_number() over (
                               partition by lower(btrim(email::text))
                               order by data_abertura desc nulls last, cnpj
                           ) as posicao_do_email
                      from mei_email.empresas
                     where {where_clause}
                )
                select cnpj, email
                  from candidatas c
                 where posicao_do_email = 1
                   and (
                       select count(distinct e2.cnpj)
                         from mei_email.empresas e2
                        where lower(btrim(e2.email::text)) = lower(btrim(c.email::text))
                   ) <= 2
                   and not exists (
                       select 1 from mei_email.envios x
                        where x.cnpj = c.cnpj
                          and x.status::text in ('pendente','enviando','pending','processing','submitted','enviado','delivered','bounced','bounce_permanent')
                   )
                   and not exists (
                       select 1 from mei_email.envios x
                        where lower(btrim(x.email::text)) = lower(btrim(c.email::text))
                          and x.status::text in ('pendente','enviando','pending','processing','submitted','enviado','delivered','bounced','bounce_permanent')
                   )
                 order by data_abertura desc nulls last, cnpj
                 limit %s
                """,
                params,
            )
            empresas = cur.fetchall()

            if not empresas:
                raise HTTPException(
                    status_code=422,
                    detail=(
                        "Nenhuma empresa elegivel encontrada (ativa, email valido/nao contabil, "
                        "ate 2 cadastros por email e nunca enfileirada/contatada)."
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
