"""Indexed eligibility adapter for :mod:`worker.safe_entrypoint`.

The suppression table is large in production.  Never wrap its normalized
``value`` column in lower/btrim: doing so defeats the (active, scope, value)
index.  This module replaces only the eligibility probe; all replay and stale
``enviando`` protections remain in safe_entrypoint.
"""
from __future__ import annotations

from typing import Any

from psycopg.rows import dict_row

from worker import safe_entrypoint as base


def _text(value: Any) -> str:
    return str(value or "").strip()


def _disallowed_marketing_origin(value: Any) -> bool:
    origin = _text(value)
    lowered = origin.lower()
    return origin in base.LEGACY_MARKETING_ORIGINS or "operator_authorization_true" in lowered


def fast_eligibility(conn, envio_id):
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            select e.id, e.email, e.cnpj,
                   emp.marketing_autorizado,
                   emp.marketing_autorizado_origem,
                   emp.mei_verificado,
                   emp.mei_verificado_origem,
                   emp.opt_out,
                   emp.situacao_cadastral,
                   emp.uf,
                   emp.tipo_regime,
                   emp.provavel_terceiro,
                   mei_email.is_valid_email_address(e.email) as email_valido,
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
        mei_origin = _text(row["mei_verificado_origem"])
        checks = (
            (bool(row["marketing_autorizado"]), "marketing sem autorizacao"),
            (bool(marketing_origin), "origem de autorizacao ausente"),
            (not _disallowed_marketing_origin(marketing_origin), "origem de autorizacao legada/inferida por operador"),
            (bool(row["mei_verificado"]), "MEI nao verificado"),
            (bool(mei_origin), "origem de verificacao MEI ausente"),
            (mei_origin not in base.LEGACY_MEI_ORIGINS, "origem de verificacao MEI legada"),
            (not bool(row["opt_out"]), "opt-out ativo"),
            (_text(row["situacao_cadastral"]) == "ATIVA", "empresa inativa"),
            (_text(row["uf"]).upper() == "MG", "empresa fora de MG"),
            (_text(row["tipo_regime"]).upper() == "MEI", "regime nao MEI"),
            (not bool(row["provavel_terceiro"]), "contato provavel terceiro"),
            (bool(row["email_valido"]), "email invalido"),
            (not bool(row["suppressed"]), "destinatario suprimido"),
            (not bool(row["terminal_history"]), "destinatario ja submetido/entregue"),
        )
        for ok, reason in checks:
            if not ok:
                return False, reason

        cur.execute("select to_regclass('mei_email.envios_externos_cota') is not null")
        if bool(cur.fetchone()[0]):
            cur.execute(
                """
                select exists(
                  select 1 from mei_email.envios_externos_cota x
                   where lower(btrim(x.email::text))=lower(btrim(%s))
                )
                """,
                (row["email"],),
            )
            if bool(cur.fetchone()[0]):
                return False, "destinatario ja consta no ledger externo"
    return True, "ok"


base._eligibility = fast_eligibility


def main() -> int:
    return base.main()


if __name__ == "__main__":
    raise SystemExit(main())
