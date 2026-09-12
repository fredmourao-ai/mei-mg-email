"""Single pre-send guard for the first-send queue."""
from __future__ import annotations

import logging
import psycopg
from psycopg.rows import dict_row
from app.queue_recovery import quarentenar_dispatches_incertos
from worker import worker_queue_first as worker

logger = logging.getLogger("mei_mg_email.safe_entrypoint")
_ORIGINAL_MARK = worker._marcar_envio_em_transito
_ORIGINAL_PROCESSAR_LOTE = worker.processar_lote


def _eligibility(conn: psycopg.Connection, envio_id) -> tuple[bool, str]:
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute("""
            select e.id, e.email, e.cnpj,
                   emp.opt_out,
                   emp.situacao_cadastral,
                   mei_email.is_valid_email_address(e.email) as email_valido,
                   mei_email.is_email_suppressed(e.email) as email_suppressed,
                   mei_email.is_cnpj_suppressed(e.cnpj::text) as cnpj_suppressed,
                   position('contabil' in lower(btrim(e.email::text))) > 0 as email_contabil,
                   (select count(distinct c2.cnpj)
                      from mei_email.empresas c2
                     where lower(btrim(c2.email::text))=lower(btrim(e.email::text))) as cadastros_mesmo_email,
                   exists (
                     select 1 from mei_email.envios h
                      where h.id<>e.id
                        and lower(btrim(h.email::text))=lower(btrim(e.email::text))
                        and h.status::text in ('submitted','enviado','delivered','bounced','bounce_permanent')
                   ) as terminal_history
              from mei_email.envios e
              join mei_email.empresas emp on emp.cnpj=e.cnpj
             where e.id=%s and e.status::text='pendente'
        """, (envio_id,))
        row=cur.fetchone()
        if row is None:
            return False, "envio deixou de estar pendente"
        checks=(
            (not bool(row['opt_out']), 'opt-out ativo'),
            (str(row['situacao_cadastral'] or '').upper()=='ATIVA', 'empresa inativa'),
            (bool(row['email_valido']), 'email invalido'),
            (not bool(row['email_suppressed']), 'email suprimido'),
            (not bool(row['cnpj_suppressed']), 'cnpj suprimido'),
            (not bool(row['email_contabil']), 'email contem palavra contabil'),
            (int(row['cadastros_mesmo_email'] or 0)<=2, 'email vinculado a mais de 2 cadastros'),
            (not bool(row['terminal_history']), 'destinatario ja submetido/entregue'),
        )
        for ok, reason in checks:
            if not ok:
                return False, reason
        cur.execute("select to_regclass('mei_email.envios_externos_cota') is not null as has_external")
        has_external = cur.fetchone()
        if has_external and bool(has_external['has_external']):
            cur.execute("""
                select exists(
                    select 1 from mei_email.envios_externos_cota x
                     where lower(btrim(x.email::text))=lower(btrim(%s))
                ) as already_external
            """, (row['email'],))
            external = cur.fetchone()
            if external and bool(external['already_external']):
                return False, 'destinatario ja consta no ledger externo'
    return True, 'ok'


def _block_never_dispatched(conn, envio_id, reason):
    with conn.cursor() as cur:
        cur.execute("""
            update mei_email.envios
               set status='bloqueado',
                   erro='PRESEND_REJECT: ' || %s
             where id=%s and status::text='pendente'
        """, (reason, envio_id))
    conn.commit()
    logger.warning('PRESEND_REJECT envio=%s reason=%s', envio_id, reason)


def _safe_mark(conn, envio_id):
    ok, reason=_eligibility(conn, envio_id)
    if not ok:
        _block_never_dispatched(conn, envio_id, reason)
        raise RuntimeError(f'pre-send eligibility rejected {envio_id}: {reason}')
    _ORIGINAL_MARK(conn, envio_id)


def _prune_lot(conn, lote_id):
    with conn.cursor() as cur:
        cur.execute("select id from mei_email.envios where lote_id=%s and status::text='pendente' order by criado_em", (lote_id,))
        ids=[row[0] for row in cur.fetchall()]
    removed=0
    for envio_id in ids:
        ok, reason=_eligibility(conn, envio_id)
        if not ok:
            _block_never_dispatched(conn, envio_id, reason)
            removed+=1
    return removed


def _safe_processar_lote(conn, lote, provider):
    removed=_prune_lot(conn, lote['id'])
    if removed:
        logger.warning('PRESEND_LOT_PRUNE lote=%s removed=%d', lote['id'], removed)
    _ORIGINAL_PROCESSAR_LOTE(conn, lote, provider)

from types import SimpleNamespace

def _light_recovery(conn):
    quarantined = quarentenar_dispatches_incertos(conn)
    return SimpleNamespace(
        changed=quarantined,
        quarantined_uncertain_dispatches=quarantined,
    )

worker._marcar_envio_em_transito=_safe_mark
worker.processar_lote=_safe_processar_lote
worker.recuperar_fila_legada_e_lotes_orfaos=_light_recovery


def main() -> int:
    worker.run()
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
