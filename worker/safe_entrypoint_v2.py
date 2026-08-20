"""Indexed pre-send eligibility adapter for the production worker.

The final live policy is intentionally independent from tax regime: authorized
active contacts may be sent, while operationally unsafe recipients remain
blocked. The checks here are the last gate immediately before dispatch.

Startup recovery is intentionally lightweight: stale ``enviando`` rows are
accounted conservatively as submitted, but the heavyweight legacy queue scan is
not allowed to block consumption of an already prepared queue.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from psycopg.rows import dict_row

from worker import safe_entrypoint as base


def _text(value: Any) -> str:
    return str(value or "").strip()


@dataclass(frozen=True)
class _RecoveryResult:
    changed: int = 0


def _lightweight_recovery(conn):
    """Protect anti-replay without running the heavyweight legacy queue scan."""
    with conn.cursor() as cur:
        cur.execute(
            """
            update mei_email.envios e
               set status='submitted',
                   enviado_em=coalesce(e.enviado_em, now()),
                   erro=case
                     when coalesce(e.erro,'')='' then
                       'recovery: resultado Graph incerto; contabilizado conservadoramente como submitted'
                     else e.erro ||
                       ' | recovery: resultado Graph incerto; contabilizado conservadoramente como submitted'
                   end
              from mei_email.lotes l
             where e.lote_id=l.id
               and e.status::text='enviando'
               and l.status::text='processando'
               and l.iniciado_em < now()-interval '15 minutes'
            """
        )
        changed = max(int(cur.rowcount or 0), 0)
    conn.commit()
    return _RecoveryResult(changed=changed)


def fast_eligibility(conn, envio_id):
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            select e.id, e.email, e.cnpj,
                   emp.marketing_autorizado,
                   emp.marketing_autorizado_origem,
                   emp.opt_out,
                   emp.situacao_cadastral,
                   mei_email.is_valid_email_address(e.email) as email_valido,
                   position('contabil' in lower(btrim(e.email::text))) > 0 as email_contabil,
                   (
                     select count(distinct c2.cnpj)
                       from mei_email.empresas c2
                      where c2.email = e.email
                   ) as cadastros_mesmo_email,
                   exists (
                     select 1
                       from mei_email.email_suppressions s
                      where s.active
                        and (
                          (s.scope='email' and s.value=lower(btrim(e.email::text))::public.citext)
                          or (s.scope='domain' and s.value=split_part(lower(btrim(e.email::text)), '@', 2)::public.citext)
                          or (s.scope='cnpj' and s.value=upper(btrim(e.cnpj::text))::public.citext)
                        )
                        and (
                          lower(coalesce(s.reason,'')) in ('opt_out','hard_bounce','filter_email_invalid','sent')
                          or lower(coalesce(s.reason,'')) like '%%bounce%%'
                          or lower(coalesce(s.reason,'')) like '%%complaint%%'
                          or lower(coalesce(s.reason,'')) like '%%spam%%'
                          or lower(coalesce(s.reason,'')) like '%%abuse%%'
                        )
                   ) as protected_suppression,
                   exists (
                     select 1
                       from mei_email.envios h
                      where h.id<>e.id
                        and lower(btrim(h.email::text))=lower(btrim(e.email::text))
                        and h.status::text in ('submitted','enviado','delivered','bounced','bounce_permanent')
                   ) as terminal_history
              from mei_email.envios e
              join mei_email.empresas emp on emp.cnpj=e.cnpj
             where e.id=%s
               and e.status::text='pendente'
            """,
            (envio_id,),
        )
        row = cur.fetchone()
        if row is None:
            return False, "envio deixou de estar pendente"

        marketing_origin = _text(row["marketing_autorizado_origem"])
        checks = (
            (bool(row["marketing_autorizado"]), "marketing sem autorizacao"),
            (bool(marketing_origin), "origem de autorizacao ausente"),
            (not bool(row["opt_out"]), "opt-out ativo"),
            (_text(row["situacao_cadastral"]) == "ATIVA", "empresa inativa"),
            (bool(row["email_valido"]), "email invalido"),
            (not bool(row["email_contabil"]), "email contem palavra contabil"),
            (int(row["cadastros_mesmo_email"] or 0) <= 2, "email vinculado a mais de 2 cadastros"),
            (not bool(row["protected_suppression"]), "bounce/reclamacao/opt-out/supressao protegida"),
            (not bool(row["terminal_history"]), "destinatario ja submetido/entregue"),
        )
        for ok, reason in checks:
            if not ok:
                return False, reason

        cur.execute("select to_regclass('mei_email.envios_externos_cota') is not null as has_external_ledger")
        ledger_row = cur.fetchone()
        if ledger_row is not None and bool(ledger_row["has_external_ledger"]):
            cur.execute(
                """
                select exists(
                  select 1 from mei_email.envios_externos_cota x
                   where lower(btrim(x.email::text))=lower(btrim(%s))
                ) as already_external
                """,
                (row["email"],),
            )
            external_row = cur.fetchone()
            if external_row is not None and bool(external_row["already_external"]):
                return False, "destinatario ja consta no ledger externo"
    return True, "ok"


base._eligibility = fast_eligibility
base.worker.recuperar_fila_legada_e_lotes_orfaos = _lightweight_recovery
# Skip whole-lot pruning: the durable pre-send checkpoint still calls
# fast_eligibility immediately before every Graph request.
base.worker.processar_lote = base._ORIGINAL_PROCESSAR_LOTE


def main() -> int:
    return base.main()


if __name__ == "__main__":
    raise SystemExit(main())
