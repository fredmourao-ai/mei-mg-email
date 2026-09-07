#!/usr/bin/env python3
"""Reconcile Brevo transactional delivery events into durable local evidence."""
from __future__ import annotations

import hashlib
import json
import logging
import os
import time
from dataclasses import dataclass
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import psycopg
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env", override=True)

from app.config import settings
from app.email_provider import brevo_storage_message_id

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("mei_mg_email.brevo_reconciler")

ENDPOINT = "https://api.brevo.com/v3/smtp/statistics/events"
STATE_PATH = Path(os.getenv("BREVO_EVENT_STATE_PATH", "/var/lib/mei-mg-email/brevo_event_state.json"))
POLL_SECONDS = max(int(os.getenv("BREVO_EVENT_POLL_SECONDS", "60")), 15)
EVENT_LIMIT = min(max(int(os.getenv("BREVO_EVENT_LIMIT", "500")), 25), 5000)
MAX_PAGES = min(max(int(os.getenv("BREVO_EVENT_MAX_PAGES", "10")), 1), 10)
LOOKBACK_DAYS = min(max(int(os.getenv("BREVO_EVENT_LOOKBACK_DAYS", "2")), 1), 30)
REQUEST_TIMEOUT_SECONDS = min(max(int(os.getenv("BREVO_EVENT_TIMEOUT_SECONDS", "30")), 5), 60)
MAX_SEEN_KEYS = min(max(int(os.getenv("BREVO_EVENT_MAX_SEEN_KEYS", "5000")), 500), 20000)
PERMANENT_EVENTS = {"hardbounce", "invalid", "blocked", "spam"}


@dataclass(frozen=True)
class EventOutcome:
    status: str | None
    suppress: bool


def classify_event(event: dict) -> EventOutcome:
    name = str(event.get("event") or "").strip().casefold()
    if name == "delivered":
        return EventOutcome("delivered", False)
    if name in PERMANENT_EVENTS:
        return EventOutcome("bounce_permanent", True)
    return EventOutcome(None, False)


def storage_message_id(event: dict) -> str:
    return brevo_storage_message_id(str(event.get("messageId") or ""))


def event_key(event: dict) -> str:
    payload = {
        "messageId": str(event.get("messageId") or ""),
        "event": str(event.get("event") or ""),
        "date": str(event.get("date") or ""),
        "email": str(event.get("email") or "").casefold(),
    }
    raw = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def dedupe_events(events: list[dict], seen: set[str]) -> tuple[list[dict], set[str]]:
    updated = set(seen)
    unique: list[dict] = []
    for event in events:
        key = event_key(event)
        if key in updated:
            continue
        updated.add(key)
        unique.append(event)
    return unique, updated


def _load_state() -> dict:
    try:
        return json.loads(STATE_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return {"seen_event_keys": []}


def _save_state(state: dict) -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = STATE_PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
    tmp.replace(STATE_PATH)


def _api_key() -> str:
    value = os.getenv("BREVO_API_KEY", "").strip()
    if not value:
        raise RuntimeError("BREVO_API_KEY missing")
    return value


def _fetch_page(offset: int) -> list[dict]:
    params = urlencode({
        "limit": str(EVENT_LIMIT),
        "offset": str(offset),
        "days": str(LOOKBACK_DAYS),
        "sort": "desc",
    })
    req = Request(
        f"{ENDPOINT}?{params}",
        headers={"api-key": _api_key(), "accept": "application/json"},
        method="GET",
    )
    try:
        with urlopen(req, timeout=REQUEST_TIMEOUT_SECONDS) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")[:500]
        raise RuntimeError(f"Brevo events HTTP {exc.code}: {detail}") from exc
    except (URLError, OSError, ValueError) as exc:
        raise RuntimeError(f"Brevo events request failed: {exc}") from exc
    return list(payload.get("events") or [])


def fetch_events() -> list[dict]:
    events: list[dict] = []
    for page in range(MAX_PAGES):
        batch = _fetch_page(page * EVENT_LIMIT)
        events.extend(batch)
        if len(batch) < EVENT_LIMIT:
            break
    return events


def _event_time(event: dict) -> str | None:
    value = str(event.get("date") or "").strip()
    return value or None


def _row_values(row) -> tuple[object, str]:
    if isinstance(row, dict):
        return row.get("id"), str(row.get("email") or "")
    return row[0], str(row[1] or "")


def apply_event(conn: psycopg.Connection, event: dict) -> bool:
    outcome = classify_event(event)
    if outcome.status is None:
        return False
    try:
        stored_id = storage_message_id(event)
    except ValueError:
        return False
    event_at = _event_time(event)
    reason = str(event.get("reason") or event.get("event") or "Brevo delivery event")[:1000]
    with conn.cursor() as cur:
        cur.execute(
            """
            select id, email::text
              from mei_email.envios
             where provider_message_id = %s
               and submitted_at is not null
             limit 1
             for update
            """,
            (stored_id,),
        )
        row = cur.fetchone()
        if row is None:
            conn.rollback()
            return False
        envio_id, stored_email = _row_values(row)
        event_email = str(event.get("email") or "").strip().casefold()
        recipient = event_email or stored_email
        if outcome.status == "delivered":
            cur.execute(
                """
                update mei_email.envios
                   set status = 'delivered'::mei_email.status_envio,
                       delivered_at = coalesce(delivered_at, coalesce(%s::timestamptz, now())),
                       reconciled_at = now(),
                       last_error = null
                 where id = %s
                   and status::text not in ('bounce_permanent','bounced')
                """,
                (event_at, envio_id),
            )
        else:
            cur.execute(
                """
                update mei_email.envios
                   set status = 'bounce_permanent'::mei_email.status_envio,
                       bounced_at = coalesce(bounced_at, coalesce(%s::timestamptz, now())),
                       ndr_code = %s,
                       ndr_reason = %s,
                       last_error = %s,
                       reconciled_at = now()
                 where id = %s
                """,
                (event_at, str(event.get("event") or "")[:100], reason, reason, envio_id),
            )
        if outcome.suppress and recipient:
            cur.execute(
                """
                select mei_email.register_operational_suppression(
                    null,
                    %s::public.citext,
                    'hard_bounce',
                    'brevo_event_reconciler',
                    %s,
                    coalesce(%s::timestamptz, now())
                )
                """,
                (recipient, event_key(event), event_at),
            )
    conn.commit()
    return True


def process_once() -> dict:
    state = _load_state()
    seen = {str(value) for value in state.get("seen_event_keys") or []}
    fetched = fetch_events()
    unique, _ = dedupe_events(fetched, seen)
    confirmed_seen = set(seen)
    matched = 0
    terminal = 0
    with psycopg.connect(settings.database_url, connect_timeout=10) as conn:
        for event in reversed(unique):
            key = event_key(event)
            if classify_event(event).status is None:
                confirmed_seen.add(key)
                continue
            terminal += 1
            if apply_event(conn, event):
                matched += 1
                confirmed_seen.add(key)
    state["seen_event_keys"] = sorted(confirmed_seen)[-MAX_SEEN_KEYS:]
    state["last_poll_epoch"] = int(time.time())
    state["last_fetched"] = len(fetched)
    state["last_unique"] = len(unique)
    state["last_terminal"] = terminal
    state["last_matched"] = matched
    _save_state(state)
    return state


def main() -> int:
    provider = settings.email_provider.strip().lower()
    if provider not in {"brevo", "brevo_api"}:
        raise RuntimeError(f"Brevo reconciler requires EMAIL_PROVIDER=brevo, got {provider!r}")
    if settings.max_envios_por_dia > 300:
        raise RuntimeError("Brevo Free hard cap exceeds 300")
    _api_key()
    logger.info(
        "Brevo reconciler started poll=%ss days=%s limit=%s max_pages=%s state=%s",
        POLL_SECONDS,
        LOOKBACK_DAYS,
        EVENT_LIMIT,
        MAX_PAGES,
        STATE_PATH,
    )
    while True:
        started = time.monotonic()
        try:
            state = process_once()
            logger.info(
                "BREVO_RECONCILE fetched=%s unique=%s terminal=%s matched=%s",
                state.get("last_fetched"),
                state.get("last_unique"),
                state.get("last_terminal"),
                state.get("last_matched"),
            )
        except Exception:
            logger.exception("BREVO_RECONCILE_FAILED")
        elapsed = time.monotonic() - started
        time.sleep(max(POLL_SECONDS - elapsed, 1.0))


if __name__ == "__main__":
    raise SystemExit(main())
