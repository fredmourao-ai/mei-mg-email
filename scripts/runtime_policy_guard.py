#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

import psycopg
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / '.env')

BANNED_DB_MARKERS = (
    'filter_uf',
    'filter_not_mei',
    'filter_marketing_not_authorized',
    'filter_mei_not_verified',
    'filter_third_party',
    'insert_filter_gate',
)
CANONICAL_ENVIO_MARKERS = (
    'situacao_cadastral',
    'opt_out',
    'is_valid_email_address',
    "position('contabil'",
    'is_email_suppressed',
    'is_cnpj_suppressed',
    'limit 3',
    'prior.status',
)


def _repo_guard() -> None:
    completed = subprocess.run(
        [sys.executable, str(ROOT / 'scripts' / 'repo_policy_guard.py')],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError('repo policy guard failed: ' + (completed.stdout + completed.stderr)[-4000:])


def _active_migration_max() -> int:
    versions = []
    for path in (ROOT / 'db' / 'migrations').glob('V[0-9]*__*.sql'):
        match = re.match(r'V(\d+)__', path.name)
        if match:
            versions.append(int(match.group(1)))
    return max(versions, default=0)


def _function_sources(cur) -> dict[str, str]:
    cur.execute("""
        select p.proname, lower(p.prosrc)
          from pg_proc p
          join pg_namespace n on n.oid=p.pronamespace
         where n.nspname='mei_email'
           and p.proname in (
             'operational_filter_rejection_reason',
             'trg_purge_rejected_company_update',
             'trg_archive_envio_and_purge_pii',
             'enforce_envio_live_eligibility'
           )
    """)
    return {str(name): str(src or '') for name, src in cur.fetchall()}


def _check_database(conn: psycopg.Connection) -> dict:
    with conn.cursor() as cur:
        sources = _function_sources(cur)
        legacy = sources.get('operational_filter_rejection_reason', '')
        for marker in BANNED_DB_MARKERS:
            if marker in legacy:
                raise RuntimeError(f'database old eligibility marker active: {marker}')

        purge = sources.get('trg_purge_rejected_company_update', '')
        if 'delete from mei_email.envios' in purge or 'delete from mei_email.empresas' in purge:
            raise RuntimeError('database destructive company-update purge function is active')
        if 'trg_archive_envio_and_purge_pii' in sources:
            raise RuntimeError('obsolete destructive archive/purge function still exists')

        live = sources.get('enforce_envio_live_eligibility', '')
        missing = [marker for marker in CANONICAL_ENVIO_MARKERS if marker not in live]
        if missing:
            raise RuntimeError('canonical live eligibility markers missing: ' + ','.join(missing))

        cur.execute("""
            select tgname
              from pg_trigger t
              join pg_class c on c.oid=t.tgrelid
              join pg_namespace n on n.oid=c.relnamespace
             where n.nspname='mei_email' and c.relname='empresas'
               and not t.tgisinternal and t.tgenabled <> 'D'
               and tgname in (
                 'zz_empresas_purge_rejected_after_update',
                 'zz_empresas_block_suppressed_or_rejected_insert'
               )
        """)
        bad_triggers = [row[0] for row in cur.fetchall()]
        if bad_triggers:
            raise RuntimeError('obsolete empresa triggers active: ' + ','.join(bad_triggers))

        cur.execute("""
            select max(case when version ~ '^[0-9]+$' then version::integer end)
              from mei_email.flyway_schema_history
             where success=true
        """)
        installed_max = int(cur.fetchone()[0] or 0)
        active_max = _active_migration_max()
        if active_max > installed_max:
            raise RuntimeError(
                f'pending active Flyway migrations blocked: installed={installed_max} active_max={active_max}'
            )

    return {
        'db_contract': 'ok',
        'flyway_installed_max': installed_max,
        'flyway_active_max': active_max,
    }


def main() -> int:
    _repo_guard()
    database_url = os.environ.get('DATABASE_URL')
    if not database_url:
        raise RuntimeError('DATABASE_URL missing')
    with psycopg.connect(database_url, connect_timeout=5) as conn:
        result = _check_database(conn)
    result['repo_contract'] = 'ok'
    print(json.dumps(result, sort_keys=True))
    print('RUNTIME_POLICY_GUARD_OK')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
