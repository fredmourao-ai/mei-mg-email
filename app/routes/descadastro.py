from __future__ import annotations

from html import escape

from fastapi import APIRouter, Form
from fastapi.responses import HTMLResponse
from psycopg.rows import dict_row

from app.db import get_pool
from app.schemas import DescadastroIn

router = APIRouter(tags=["descadastro"])


def _registrar_descadastro(payload: DescadastroIn) -> dict:
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


@router.post("/descadastro", status_code=201)
def registrar_descadastro(payload: DescadastroIn):
    """Endpoint JSON para integrações da API."""
    return _registrar_descadastro(payload)


@router.get("/descadastro", response_class=HTMLResponse)
def confirmar_descadastro(
    email: str = "",
    cnpj: str | None = None,
    campanha_id: str | None = None,
):
    """Exibe uma confirmação antes de registrar o opt-out vindo do e-mail."""
    campos = {
        "email": email,
        "cnpj": cnpj or "",
        "campanha_id": campanha_id or "",
    }
    hidden = "".join(
        f'<input type="hidden" name="{nome}" value="{escape(valor, quote=True)}">'
        for nome, valor in campos.items()
    )
    return HTMLResponse(
        "<!doctype html><html lang=\"pt-BR\"><meta charset=\"utf-8\">"
        "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">"
        "<title>Descadastro - Contabilidade Melo</title>"
        "<body style=\"font-family:Arial,sans-serif;background:#f3f6fb;padding:32px;color:#1f2937\">"
        "<main style=\"max-width:560px;margin:auto;background:#fff;padding:28px;border-radius:16px\">"
        "<h1>Confirmar descadastro</h1>"
        "<p>Ao confirmar, este endereço não receberá novos e-mails da Contabilidade Melo.</p>"
        f"<p><strong>{escape(email)}</strong></p>"
        f"<form method=\"post\" action=\"/descadastro/confirmar\">{hidden}"
        "<button type=\"submit\" style=\"padding:12px 18px;background:#0b1f3a;color:#fff;border:0;border-radius:8px\">"
        "Confirmar descadastro</button></form></main></body></html>"
    )


@router.post("/descadastro/confirmar", response_class=HTMLResponse)
def confirmar_descadastro_post(
    email: str = Form(...),
    cnpj: str | None = Form(None),
    campanha_id: str | None = Form(None),
):
    _registrar_descadastro(
        DescadastroIn(cnpj=cnpj, email=email, campanha_id=campanha_id, origem="link_email")
    )
    return HTMLResponse(
        "<!doctype html><html lang=\"pt-BR\"><meta charset=\"utf-8\">"
        "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">"
        "<title>Descadastro confirmado</title>"
        "<body style=\"font-family:Arial,sans-serif;background:#f3f6fb;padding:32px;color:#1f2937\">"
        "<main style=\"max-width:560px;margin:auto;background:#fff;padding:28px;border-radius:16px\">"
        "<h1>Descadastro confirmado</h1>"
        "<p>Você não receberá novos e-mails da Contabilidade Melo.</p>"
        "</main></body></html>"
    )
