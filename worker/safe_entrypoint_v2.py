"""Indexed pre-send eligibility adapter for the production worker.

Authorized MG recipients are checked immediately before every Graph request.
Marketing authorization is independent from MEI classification: verified MEIs
can be prioritized by the queue, while authorized non-MEIs are allowed as
fallback. Opt-out, suppression, invalid email, ``contabil`` addresses,
3+ source registrations and terminal replay remain hard blocks.

Startup recovery is intentionally lightweight: stale ``enviando`` rows are
accounted conservatively as submitted, but heavyweight whole-lot scans are not
allowed to delay consumption of an already prepared queue.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from psycopg.rows import dict_row

from worker import safe_entrypoint as base

USER_EXPLICIT_AUTHORIZATION = "user_explicit_authorization_2026-08-20"
USER_CAMPAIGN_AUTHORIZATION = "user_campaign_authorization_2026-08-20"


def _text(value: Any) -> str:
    return str(value or "").strip()


def _disallowed_marketing_origin(value: Any) -> bool:
    origin = _text(value)
    if origin in {USER_EXPLICIT_AUTHORIZATION, USER_CAMPAIGN_AUTHORIZATION}:
        return False
    lowered = origin.lower()
    return origin in base.LEGACY_MARKETING_ORIGINS or "operator_authorization_true" in lowered


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
                   emp.uf,
                   emp.provavel_terceiro,
                   mei_email.is_valid_email_address(e.email) as email_valido,
                   position('contabil' in lower(btrim(e.email::text))) > 0 as email_contabil,
                   (
                     select count(distinct c2.cnpj)
                       from mei_email.empresas c2
                      where lower(btrim(c2.email::text)) = lower(btrim(e.email::text))
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
                   ) as suppressed,
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
            (not _disallowed_marketing_origin(marketing_origin), "origem de autorizacao legada/inferida por operador"),
            (not bool(row["opt_out"]), "opt-out ativo"),
            (_text(row["situacao_cadastral"]).upper() == "ATIVA", "empresa inativa"),
            (_text(row["uf"]).upper() == "MG", "empresa fora de MG"),
            (not bool(row["provavel_terceiro"]), "contato provavel terceiro"),
            (bool(row["email_valido"]), "email invalido"),
            (not bool(row["email_contabil"]), "email contem palavra contabil"),
            (int(row["cadastros_mesmo_email"] or 0) <= 2, "email vinculado a mais de 2 cadastros"),
            (not bool(row["suppressed"]), "destinatario suprimido"),
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
# No whole-lot pre-scan: every row is still checked by _safe_mark immediately
# before the durable ``enviando`` checkpoint and Graph side effect.
base.worker.processar_lote = base._ORIGINAL_PROCESSAR_LOTE


def main() -> int:
    return base.main()


if __name__ == "__main__":
    raise SystemExit(main())
