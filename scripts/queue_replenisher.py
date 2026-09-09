#!/usr/bin/env python3
from __future__ import annotations

import json
import logging
import os
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import psycopg
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / '.env')

from app.config import settings
from app.email_quality import recipient_has_obvious_provider_typo
from app.queue_manager import (
    AUTOQUEUE_LOT_SIZE,
    AUTOQUEUE_SUBJECT,
    CAMPAIGN_ENQUEUE_ADVISORY_LOCK_ID,
    carregar_template_html,
    validar_config_fila,
)
STATE_PATH = ROOT / 'runtime' / 'queue_replenisher_state.json'
PAUSE_PATH = Path('/var/lib/mei-mg-email/sender_blocked.pause')
LEGACY_PAUSE_PATH = ROOT / 'runtime' / 'sender_blocked.pause'
REPLENISHER_PAUSE_PATH = ROOT / 'runtime' / 'queue_replenisher.pause'
LOCK_ID = CAMPAIGN_ENQUEUE_ADVISORY_LOCK_ID
BATCH = min(200, max(settings.queue_target_pending, 1))
PAGE = 1000
MAX_PAGES = 40
POLL = 5
ACTIVE_STATUSES = ('pendente','enviando','pending','processing','submitted','enviado','delivered','bounced','bounce_permanent')
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
log = logging.getLogger('mei_mg_email.queue_replenisher')


def load_state() -> dict:
    if not STATE_PATH.exists():
        return {'cursor': ''}
    try:
        data = json.loads(STATE_PATH.read_text())
        return {'cursor': str(data.get('cursor') or '')}
    except Exception:
        return {'cursor': ''}


def save_state(state: dict) -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = STATE_PATH.with_suffix('.tmp')
    tmp.write_text(json.dumps(state, sort_keys=True))
    tmp.replace(STATE_PATH)


def open_count(cur) -> int:
    cur.execute("select count(*) from mei_email.envios where status in ('pendente','enviando','pending','processing')")
    return int(cur.fetchone()[0] or 0)


def fetch_page(cur, cursor: str):
    cur.execute("""
        select e.cnpj, e.email, e.uf
          from mei_email.empresas e
         where e.cnpj > %s
           and e.situacao_cadastral = 'ATIVA'
           and coalesce(e.opt_out,false)=false
           and e.email is not null
           and btrim(e.email::text) <> ''
         order by e.cnpj
         limit %s
    """, (cursor, PAGE))
    return cur.fetchall()


def filter_candidates_batch(cur, rows, needed: int):
    if not rows or needed <= 0:
        return []

    page = []
    for row in rows:
        cnpj = str(row[0])
        email = str(row[1] or '').strip()
        uf = str(row[2] or '').strip()
        email_norm = email.strip().lower()
        if (
            not email_norm
            or 'contabil' in email_norm
            or recipient_has_obvious_provider_typo(email)
        ):
            continue
        page.append((cnpj, email, uf))
    if not page:
        return []

    cnpjs = [cnpj for cnpj, _, _ in page]
    emails = [email for _, email, _ in page]
    ufs = [uf for _, _, uf in page]
    cur.execute("""
        with page as materialized (
            select p.cnpj,
                   p.email,
                   p.uf,
                   lower(btrim(p.email)) as email_norm,
                   case when upper(coalesce(p.uf,''))='MG' then 0 else 1 end as uf_priority
              from unnest(%s::text[], %s::text[], %s::text[])
                   as p(cnpj,email,uf)
        ), ranked as (
            select p.*,
                   row_number() over (
                       partition by p.email_norm
                       order by p.uf_priority, p.cnpj
                   ) as rn
              from page p
             where btrim(p.email) <> ''
               and position('contabil' in p.email_norm) = 0
        ), eligible_page as materialized (
            select r.cnpj, r.email, r.uf, r.email_norm, r.uf_priority
              from ranked r
             where r.rn = 1
               and mei_email.is_valid_email_address(r.email::public.citext)
               and position('contabil' in r.email_norm) = 0
               and not mei_email.is_email_suppressed(r.email::public.citext)
               and not mei_email.is_cnpj_suppressed(r.cnpj)
        )
        select cnpj, email, email_norm, uf_priority
          from eligible_page
         order by uf_priority, cnpj
         limit %s
    """, (cnpjs, emails, ufs, needed))
    eligible = [
        {
            'cnpj': str(cnpj),
            'email': str(email).strip(),
            'email_norm': str(email_norm),
            'uf_priority': int(uf_priority or 0),
        }
        for cnpj, email, email_norm, uf_priority in cur.fetchall()
    ]
    if not eligible:
        return []

    eligible_cnpjs = [row['cnpj'] for row in eligible]
    eligible_email_norms = sorted({row['email_norm'] for row in eligible})
    statuses = list(ACTIVE_STATUSES)

    cur.execute("""
        with emails as (
            select unnest(%s::text[]) as email_norm
        ), shared_email_counts as materialized (
            select emails.email_norm, count(shared.cnpj) as shared_cnpjs
              from emails
              join lateral (
                  select e2.cnpj
                    from mei_email.empresas e2
                   where lower(btrim(e2.email::text)) = emails.email_norm
                   limit 3
              ) shared on true
             group by emails.email_norm
        )
        select email_norm
          from shared_email_counts
         where shared_cnpjs <= 2
    """, (eligible_email_norms,))
    allowed_shared_emails = {str(row[0]) for row in cur.fetchall()}
    if not allowed_shared_emails:
        return []

    cur.execute("""
        with prior_cnpjs as materialized (
            select distinct cnpj::text as cnpj
              from mei_email.envios
             where cnpj::text = any(%s::text[])
               and status = any(%s::mei_email.status_envio[])
        )
        select cnpj from prior_cnpjs
    """, (eligible_cnpjs, statuses))
    blocked_cnpjs = {str(row[0]) for row in cur.fetchall()}

    cur.execute("""
        with prior_emails as materialized (
            select distinct lower(btrim(email::text)) as email_norm
              from mei_email.envios
             where lower(btrim(email::text)) = any(%s::text[])
               and status = any(%s::mei_email.status_envio[])
        )
        select email_norm from prior_emails
    """, (eligible_email_norms, statuses))
    blocked_emails = {str(row[0]) for row in cur.fetchall()}

    selected = []
    for row in eligible:
        if row['email_norm'] not in allowed_shared_emails:
            continue
        if row['cnpj'] in blocked_cnpjs or row['email_norm'] in blocked_emails:
            continue
        selected.append((row['cnpj'], row['email']))
        if len(selected) >= needed:
            break
    return selected

def collect_candidates(cur, needed: int, state: dict):
    selected = []
    seen = set()
    cursor = state.get('cursor', '')
    pages = 0
    while len(selected) < needed and pages < MAX_PAGES:
        rows = fetch_page(cur, cursor)
        pages += 1
        if not rows:
            cursor = ''
            state['cursor'] = ''
            save_state(state)
            if pages > 1:
                break
            continue
        cursor = str(rows[-1][0])
        state['cursor'] = cursor
        save_state(state)
        batch = filter_candidates_batch(cur, rows, needed - len(selected))
        for cnpj, email in batch:
            norm = str(email or '').strip().lower()
            if norm in seen:
                continue
            selected.append((cnpj, email))
            seen.add(norm)
            if len(selected) >= needed:
                break
    log.info('CANDIDATE_SCAN pages=%d selected=%d cursor=%s', pages, len(selected), state.get('cursor'))
    return selected


def insert_batch(cur, candidates):
    if not candidates:
        return 0
    template = carregar_template_html()
    now = datetime.now(ZoneInfo('America/Sao_Paulo'))
    cur.execute("""
        insert into mei_email.campanhas
            (nome, assunto, corpo_template, tamanho_lote, status, total_empresas)
        values (%s,%s,%s,%s,'enfileirada',%s)
        returning id
    """, (f'First-send Refill {now:%Y-%m-%d %H:%M:%S}', AUTOQUEUE_SUBJECT, template, AUTOQUEUE_LOT_SIZE, len(candidates)))
    campaign_id = cur.fetchone()[0]
    for number, start in enumerate(range(0, len(candidates), AUTOQUEUE_LOT_SIZE)):
        chunk = candidates[start:start + AUTOQUEUE_LOT_SIZE]
        cur.execute("""
            insert into mei_email.lotes (campanha_id,numero,status,tamanho)
            values (%s,%s,'pendente',%s) returning id
        """, (campaign_id, number, len(chunk)))
        lot_id = cur.fetchone()[0]
        cur.executemany("""
            insert into mei_email.envios (campanha_id,lote_id,cnpj,email,status)
            values (%s,%s,%s,%s,'pendente')
        """, [(campaign_id, lot_id, cnpj, email) for cnpj, email in chunk])
    log.warning('REFILL campaign=%s added=%d', campaign_id, len(candidates))
    return len(candidates)


def replenish_once(conn) -> int:
    state = load_state()
    with conn.cursor() as cur:
        cur.execute('select pg_try_advisory_xact_lock(%s)', (LOCK_ID,))
        row = cur.fetchone()
        if row is None or not bool(row[0]):
            conn.rollback()
            return 0
        pending = open_count(cur)
        if pending > settings.queue_min_pending:
            conn.rollback()
            return 0
        needed = min(BATCH, max(settings.queue_target_pending - pending, 0))
        selected = collect_candidates(cur, needed, state)
        added = insert_batch(cur, selected)
        conn.commit()
        if added:
            log.warning(
                'QUEUE open_before=%d added=%d target=%d cursor=%s',
                pending,
                added,
                settings.queue_target_pending,
                state.get('cursor'),
            )
        elif pending == 0:
            log.error('REFILL_EMPTY no canonical candidates found in bounded scan')
        return added


def main() -> int:
    validar_config_fila()
    database_url = os.environ['DATABASE_URL']
    once = os.getenv('QUEUE_REPLENISHER_ONCE') == '1'
    while True:
        if PAUSE_PATH.exists() or LEGACY_PAUSE_PATH.exists() or REPLENISHER_PAUSE_PATH.exists():
            log.warning('replenisher paused because sender-block sentinel exists')
            if once:
                return 0
            time.sleep(POLL)
            continue
        added = 0
        try:
            with psycopg.connect(database_url, connect_timeout=5) as conn:
                with conn.cursor() as cur:
                    cur.execute("set statement_timeout='15s'")
                    cur.execute("set lock_timeout='2s'")
                added = replenish_once(conn)
        except Exception:
            log.exception('replenisher cycle failed')
        if once:
            return 0
        time.sleep(5 if added else POLL)


if __name__ == '__main__':
    raise SystemExit(main())
