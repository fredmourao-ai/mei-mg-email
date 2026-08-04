from __future__ import annotations

from fastapi import APIRouter
from psycopg.rows import dict_row

from app.db import get_pool
from app.schemas import DescadastroIn

router = APIRouter(tags=["descadastro"])


@router.post("/descadastro", status_code=201)
def registrar_descadastro(payload: DescadastroIn):
    """Registra o pedido de descadastro. Um trigger no banco
    (V003__opt_out_trigger_e_views.sql) propaga isso pra
    empresas.opt_out = true automaticamente -- essa rota so precisa
    inserir o registro, nao precisa saber a regra de propagacao."""
    pool = get_pool()
    with pool.connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                insert into mei_email.descadastros
                    (cnpj, email, campanha_id, origem)
                values (%s, %s, %s, %s)
                returning id, criado_em
                """,
                (payload.cnpj, payload.email, payload.campanha_id, payload.origem),
            )
            registro = cur.fetchone()
        conn.commit()

    return {
        "mensagem": "Descadastro registrado. Voce nao recebera mais e-mails deste remetente.",
        "id": registro["id"],
        "criado_em": registro["criado_em"],
    }
