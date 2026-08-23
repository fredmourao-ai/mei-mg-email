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

from app.queue_manager import AUTOQUEUE_LOT_SIZE, AUTOQUEUE_SUBJECT, carregar_template_html

ROOT = Path('/home/ubuntu/mei-mg-email')
STATE_PATH = ROOT / 'runtime' / 'queue_replenisher_state.json'
PAUSE_PATH = Path('/var/lib/mei-mg-email/sender_blocked.pause')
LEGACY_PAUSE_PATH = ROOT / 'runtime' / 'sender_blocked.pause'
REPLENISHER_PAUSE_PATH = ROOT / 'runtime' / 'queue_replenisher.pause'
LOCK_ID = 99502027
TARGET = 15000
MINIMUM = 14800
BATCH = 200
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
    cnpjs = [str(row[0]) for row in rows]
    emails = [str(row[1] or '').strip() for row in rows]
    ufs = [str(row[2] or '').strip() for row in rows]
    statuses = list(ACTIVE_STATUSES)
    cur.execute("""
        with page as (
            select *
              from unnest(%s::text[], %s::text[], %s::text[])
                   as p(cnpj,email,uf)
        ), ranked as (
            select p.*,
                   row_number() over (
                       partition by lower(btrim(p.email))
                       order by case when upper(coalesce(p.uf,''))='MG' then 0 else 1 end,
                                p.cnpj
                   ) as rn
              from page p
             where btrim(p.email) <> ''
               and position('contabil' in lower(btrim(p.email))) = 0
        )
        select r.cnpj, r.email
          from ranked r
          join mei_email.empresas e on e.cnpj = r.cnpj
         where r.rn = 1
           and e.situacao_cadastral = 'ATIVA'
           and coalesce(e.opt_out,false)=false
           and e.email is not null
           and lower(btrim(e.email::text)) = lower(btrim(r.email))
           and mei_email.is_valid_email_address(e.email)
           and position('contabil' in lower(btrim(e.email::text))) = 0
           and not mei_email.is_email_suppressed(e.email)
           and not mei_email.is_cnpj_suppressed(e.cnpj::text)
           and (
               select count(*) from (
                   select 1
                     from mei_email.empresas e2
                    where lower(btrim(e2.email::text)) = lower(btrim(e.email::text))
                    limit 3
               ) shared
           ) <= 2
           and not exists (
               select 1 from mei_email.envios x
                where x.cnpj = e.cnpj
                  and x.status = any(%s::mei_email.status_envio[])
           )
           and not exists (
               select 1 from mei_email.envios x
                where lower(btrim(x.email::text)) = lower(btrim(e.email::text))
                  and x.status = any(%s::mei_email.status_envio[])
           )
         order by case when upper(coalesce(r.uf,''))='MG' then 0 else 1 end,
                  r.cnpj
         limit %s
    """, (cnpjs, emails, ufs, statuses, statuses, needed))
    return [(str(cnpj), str(email).strip()) for cnpj, email in cur.fetchall()]

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
        if pending > MINIMUM:
            conn.rollback()
            return 0
        needed = min(BATCH, max(TARGET - pending, 0))
        selected = collect_candidates(cur, needed, state)
        added = insert_batch(cur, selected)
        conn.commit()
        if added:
            log.warning('QUEUE open_before=%d added=%d target=%d cursor=%s', pending, added, TARGET, state.get('cursor'))
        elif pending == 0:
            log.error('REFILL_EMPTY no canonical candidates found in bounded scan')
        return added


def main() -> int:
    load_dotenv(ROOT / '.env')
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
