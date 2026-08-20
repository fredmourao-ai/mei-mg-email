"""Nonstop worker entrypoint with migration-independent pre-send safety.

The database migrations remain the durable policy layer, while the active
pre-send policy is supplied by safe_entrypoint_v2. Stale ``enviando`` rows are
never blindly reopened, preventing duplicate Graph submissions.
"""
from __future__ import annotations

import logging
from typing import Any

import psycopg
from psycopg.rows import dict_row

from worker import worker_queue_first as worker

logger = logging.getLogger("mei_mg_email.safe_entrypoint")

LEGACY_MARKETING_ORIGINS = {
    "confirmacao_operador_2026-08-12",
    "confirmacao_operador_2026-08-13",
    "politica_importacao_operador_2026-08-13",
    "operator_authorization_true_2026-08-20",
}
LEGACY_MEI_ORIGINS = {
    "override_operador_2026-08-13",
    "politica_importacao_operador_2026-08-13",
}

LEGACY_COPY_PUBLIC = "Você recebeu este e-mail porque seu contato consta em base pública de CNPJ."
LEGACY_COPY_ASCII = "Você recebeu este e-mail porque seu contato consta em base publica de CNPJ."
SAFE_COPY = "Você recebe esta mensagem porque há uma autorização comercial registrada para este contato."

_ORIGINAL_MARK = worker._marcar_envio_em_transito
_ORIGINAL_RECOVERY = worker.recuperar_fila_legada_e_lotes_orfaos
_ORIGINAL_PROCESSAR_LOTE = worker.processar_lote
_ORIGINAL_RENDER = worker.base_worker.montar_corpo


def _nonempty(value: Any) -> str:
    return str(value or "").strip()


def _safe_render(template: str, empresa: dict) -> str:
    rendered = _ORIGINAL_RENDER(template, empresa)
    rendered = rendered.replace(LEGACY_COPY_PUBLIC, SAFE_COPY)
    rendered = rendered.replace(LEGACY_COPY_ASCII, SAFE_COPY)
    if "base pública de CNPJ" in rendered or "base publica de CNPJ" in rendered:
        raise RuntimeError("legacy public-CNPJ copy survived render normalization")
    return rendered


def _eligibility(conn: psycopg.Connection, envio_id) -> tuple[bool, str]:
    """Fallback fail-closed eligibility; v2 replaces this with live policy."""
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            select e.id, e.email, e.cnpj,
                   emp.marketing_autorizado,
                   emp.marketing_autorizado_origem,
                   emp.opt_out,
                   emp.situacao_cadastral,
                   mei_email.is_valid_email_address(e.email) as email_valido,
                   exists (
                     select 1 from mei_email.envios h
                      where h.id<>e.id
                        and lower(btrim(h.email::text))=lower(btrim(e.email::text))
                        and h.status::text in ('submitted','enviado','delivered','bounced','bounce_permanent')
                   ) as terminal_history
              from mei_email.envios e
              join mei_email.empresas emp on emp.cnpj=e.cnpj
             where e.id=%s and e.status::text='pendente'
            """,
            (envio_id,),
        )
        row = cur.fetchone()
        if row is None:
            return False, "envio deixou de estar pendente"
        origin = _nonempty(row["marketing_autorizado_origem"])
        checks = (
            (bool(row["marketing_autorizado"]), "marketing sem autorizacao"),
            (bool(origin), "origem de autorizacao ausente"),
            (origin not in LEGACY_MARKETING_ORIGINS, "origem de autorizacao legada"),
            (not bool(row["opt_out"]), "opt-out ativo"),
            (_nonempty(row["situacao_cadastral"]) == "ATIVA", "empresa inativa"),
            (bool(row["email_valido"]), "email invalido"),
            (not bool(row["terminal_history"]), "destinatario ja submetido/entregue"),
        )
        for ok, reason in checks:
            if not ok:
                return False, reason
    return True, "ok"


def _drop_never_dispatched(conn: psycopg.Connection, envio_id, reason: str) -> None:
    with conn.cursor() as cur:
        cur.execute(
            "delete from mei_email.envios where id=%s and status::text='pendente'",
            (envio_id,),
        )
    conn.commit()
    logger.warning("PRESEND_REJECT envio=%s reason=%s", envio_id, reason)


def _safe_mark(conn: psycopg.Connection, envio_id) -> None:
    ok, reason = _eligibility(conn, envio_id)
    if not ok:
        _drop_never_dispatched(conn, envio_id, reason)
        raise RuntimeError(f"pre-send eligibility rejected {envio_id}: {reason}")
    _ORIGINAL_MARK(conn, envio_id)


def _safe_recovery(conn: psycopg.Connection):
    with conn.cursor() as cur:
        cur.execute(
            """
            update mei_email.envios e
               set status='submitted',
                   enviado_em=coalesce(e.enviado_em, now()),
                   erro=case
                     when coalesce(e.erro,'')='' then 'recovery: resultado Graph incerto; contabilizado conservadoramente como submitted'
                     else e.erro || ' | recovery: resultado Graph incerto; contabilizado conservadoramente como submitted'
                   end
              from mei_email.lotes l
             where e.lote_id=l.id
               and e.status::text='enviando'
               and l.status::text='processando'
               and l.iniciado_em < now()-interval '15 minutes'
            """
        )
        uncertain = max(int(cur.rowcount or 0), 0)
    conn.commit()
    if uncertain:
        logger.critical("UNCERTAIN_DISPATCH_ACCOUNTED submitted=%d", uncertain)
    return _ORIGINAL_RECOVERY(conn)


def _prune_lot(conn: psycopg.Connection, lote_id) -> int:
    with conn.cursor() as cur:
        cur.execute(
            "select id from mei_email.envios where lote_id=%s and status::text='pendente' order by criado_em",
            (lote_id,),
        )
        ids = [row[0] for row in cur.fetchall()]
    removed = 0
    for envio_id in ids:
        ok, reason = _eligibility(conn, envio_id)
        if not ok:
            _drop_never_dispatched(conn, envio_id, reason)
            removed += 1
    return removed


def _safe_processar_lote(conn: psycopg.Connection, lote: dict, provider) -> None:
    removed = _prune_lot(conn, lote["id"])
    if removed:
        logger.warning("PRESEND_LOT_PRUNE lote=%s removed=%d", lote["id"], removed)
    _ORIGINAL_PROCESSAR_LOTE(conn, lote, provider)


worker.base_worker.montar_corpo = _safe_render
worker._marcar_envio_em_transito = _safe_mark
worker.recuperar_fila_legada_e_lotes_orfaos = _safe_recovery
worker.processar_lote = _safe_processar_lote


def main() -> int:
    worker.run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
