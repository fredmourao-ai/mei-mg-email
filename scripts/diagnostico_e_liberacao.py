#!/usr/bin/env python3
from __future__ import annotations

import os
from pathlib import Path

import psycopg
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / '.env')


def main() -> int:
    with psycopg.connect(os.environ['DATABASE_URL'], connect_timeout=5) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                select
                  count(*) filter (where status::text in ('pendente','enviando','pending','processing')),
                  count(*) filter (where status::text in ('submitted','enviado','delivered') and enviado_em>=now()-interval '10 minutes'),
                  max(enviado_em) filter (where status::text in ('submitted','enviado','delivered'))
                from mei_email.envios
            """)
            open_count, sent10, last_sent = cur.fetchone()
    print(f'OPEN={int(open_count or 0)}')
    print(f'SENT10={int(sent10 or 0)}')
    print(f'LAST_SENT={last_sent}')
    print('POLICY=ATIVA,email_valido,sem_contabil,shared<=2,sem_replay,optout/suppression')
    print('MG=priority_only')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
