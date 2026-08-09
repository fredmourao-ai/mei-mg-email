#!/usr/bin/env python3
"""Reconstroi uma fila confirmada pelo operador sem reenviar itens submetidos.

Usa apenas os registros historicos pendentes ou explicitamente falhos. A base
atual ainda e consultada para respeitar status ATIVA, consentimento, opt-out e
supressao. Cada endereco normalizado entra uma unica vez, pelo CNPJ mais novo.
"""
from __future__ import annotations

import argparse
import gzip
import json
import math
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import psycopg
from psycopg.rows import dict_row

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from app.config import settings

BACKUP_PATH = Path(
    "/home/ubuntu/backups/mei-campaign-cleanup-20260809T010359Z/"
    "campaigns-lotes-envios-before-delete.json.gz"
)
TARGET = 9950
SUBJECT = "MEI: Ganhe Certificado Digital + 10 Notas Fiscais por mes"
TEMPLATE_PATH = BASE_DIR / "templates" / "mei-contabilidade-melo.html"


def carregar_candidatos() -> list[tuple[str, str]]:
    with gzip.open(BACKUP_PATH, "rt", encoding="utf-8") as handle:
        envios = json.load(handle)["tables"]["envios"]
    # submitted is intentionally excluded: Graph acceptance is not an NDR.
    return sorted(
        {
            (str(row["cnpj"]).strip(), str(row["email"]).strip().lower())
            for row in envios
            if row.get("status") in {"pendente", "falhou"}
            and row.get("cnpj")
            and row.get("email")
        }
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="valida os candidatos sem criar campanha, lotes ou envios",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    template = TEMPLATE_PATH.read_text(encoding="utf-8")
    if "{{unsubscribe_url}}" not in template:
        raise RuntimeError("template sem link de descadastro")
    candidates = carregar_candidatos()
    if not candidates:
        raise RuntimeError("backup sem candidatos pendentes/falhos")

    with psycopg.connect(settings.database_url) as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute("select pg_advisory_xact_lock(%s)", (99502026,))
            cur.execute("select count(*) from mei_email.campanhas")
            if cur.fetchone()["count"]:
                raise RuntimeError("ja existe campanha; recuperacao exige fila vazia")
            cur.execute(
                "create temporary table recovery_candidates (cnpj char(14), email citext) on commit drop"
            )
            with cur.copy("copy recovery_candidates (cnpj, email) from stdin") as copy:
                for row in candidates:
                    copy.write_row(row)
            cur.execute(
                """
                with validos as (
                    select e.cnpj, e.email, e.data_abertura,
                           row_number() over (
                               partition by lower(btrim(e.email::text))
                               order by e.data_abertura desc nulls last, e.cnpj
                           ) as posicao
                      from recovery_candidates r
                      join mei_email.empresas e
                        on e.cnpj = r.cnpj
                       and lower(btrim(e.email::text)) = lower(btrim(r.email::text))
                     where e.uf = 'MG'
                       and e.situacao_cadastral = 'ATIVA'
                       and e.marketing_autorizado = true
                       and e.opt_out = false
                       and not mei_email.is_email_suppressed(e.email)
                )
                select cnpj, email
                  from validos
                 where posicao = 1
                 order by data_abertura desc nulls last, cnpj
                 limit %s
                """,
                (TARGET,),
            )
            recipients = cur.fetchall()
            if not recipients:
                raise RuntimeError("nenhum candidato historico permanece elegivel")
            if args.dry_run:
                print(f"RECOVERY_DRY_RUN_CANDIDATES={len(candidates)}")
                print(f"RECOVERY_DRY_RUN_RECIPIENTS={len(recipients)}")
                print("RECOVERY_DRY_RUN_STATUS=validated_no_writes")
                return 0
            now = datetime.now(ZoneInfo("America/Sao_Paulo"))
            cur.execute(
                """
                insert into mei_email.campanhas
                    (nome, assunto, corpo_template, filtro_tipo_regime, filtro_uf, tamanho_lote, status, total_empresas)
                values (%s, %s, %s, 'MEI', 'MG', 100, 'enfileirada', %s)
                returning id
                """,
                (f"MEI MG Recuperacao Confirmada {now:%Y-%m-%d}", SUBJECT, template, len(recipients)),
            )
            campaign_id = cur.fetchone()["id"]
            for number in range(math.ceil(len(recipients) / 100)):
                batch = recipients[number * 100 : (number + 1) * 100]
                cur.execute(
                    "insert into mei_email.lotes (campanha_id, numero, status, tamanho) values (%s, %s, 'pendente', %s) returning id",
                    (campaign_id, number, len(batch)),
                )
                lot_id = cur.fetchone()["id"]
                cur.executemany(
                    "insert into mei_email.envios (campanha_id, lote_id, cnpj, email, status) values (%s, %s, %s, %s, 'pending')",
                    [(campaign_id, lot_id, row["cnpj"], row["email"]) for row in batch],
                )
        conn.commit()
    print(f"RECOVERY_CAMPAIGN={campaign_id}")
    print(f"RECOVERY_RECIPIENTS={len(recipients)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
