#!/usr/bin/env python3
"""Send one internal Brevo probe and require a real delivered event."""
from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import psycopg
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env", override=True)

from app.config import settings
from app.email_provider import BREVO_ALLOWED_SENDER, BrevoEmailProvider
from scripts.brevo_event_reconciler import classify_event
from worker.worker import montar_corpo

RECIPIENT = os.getenv("TEST_RECIPIENT", "atendimento@shopvivaliz.com.br").strip()
TEMPLATE_PATH = BASE_DIR / "templates" / "mei-contabilidade-melo.html"
BREVO_TEST_TIMEOUT_SECONDS = min(max(int(os.getenv("BREVO_TEST_TIMEOUT_SECONDS", "180")), 30), 600)
BREVO_TEST_POLL_SECONDS = min(max(int(os.getenv("BREVO_TEST_POLL_SECONDS", "5")), 2), 30)
EVENT_ENDPOINT = "https://api.brevo.com/v3/smtp/statistics/events"


def _rolling_brevo_total(conn: psycopg.Connection) -> int:
    with conn.cursor() as cur:
        cur.execute(
            """
            select
              (select count(*) from mei_email.envios
                where provider_message_id like 'brevo:%'
                  and submitted_at >= now() - interval '24 hours')
              +
              (select count(*) from mei_email.envios_externos_cota
                where (provider_message_id like 'brevo:%' or source like 'brevo%')
                  and sent_at >= now() - interval '24 hours')
            """
        )
        return int(cur.fetchone()[0] or 0)


def _record_probe(conn, *, subject: str, storage_id: str) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            insert into mei_email.envios_externos_cota
                (email, subject, sent_at, source, provider_message_id, metadata)
            values (%s, %s, now(), 'brevo_controlled_test', %s, %s::jsonb)
            on conflict (provider_message_id) do nothing
            """,
            (RECIPIENT, subject, storage_id, json.dumps({"purpose": "brevo_delivery_proof"})),
        )
    conn.commit()


def _fetch_events(raw_message_id: str) -> list[dict]:
    params = urlencode({
        "messageId": raw_message_id,
        "days": "1",
        "limit": "100",
        "offset": "0",
        "sort": "desc",
    })
    req = Request(
        f"{EVENT_ENDPOINT}?{params}",
        headers={
            "api-key": os.environ["BREVO_API_KEY"],
            "accept": "application/json",
        },
        method="GET",
    )
    try:
        with urlopen(req, timeout=30) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")[:500]
        raise RuntimeError(f"Brevo event lookup HTTP {exc.code}: {detail}") from exc
    except (URLError, OSError, ValueError) as exc:
        raise RuntimeError(f"Brevo event lookup failed: {exc}") from exc
    return list(payload.get("events") or [])


def _render_test_body() -> str:
    template = TEMPLATE_PATH.read_text(encoding="utf-8")
    body = montar_corpo(
        template,
        {
            "cnpj": "00000000000000",
            "email": RECIPIENT,
            "razao_social": "Equipe ShopVivaLiz",
            "nome_fantasia": "ShopVivaLiz",
        },
    )
    lower = body.casefold()
    if "logo-contabilidade-melo-transparente.png" not in lower:
        raise RuntimeError("Template de teste sem a logo oficial")
    if "R$ 200,00/mês" not in body:
        raise RuntimeError("Template de teste nao corresponde ao Plano MEI aprovado")
    if "Falar com a Contabilidade Melo" not in body:
        raise RuntimeError("Template de teste sem CTA atual")
    if "{{unsubscribe_url}}" in body:
        raise RuntimeError("Template saiu com placeholder sem renderizar")
    return body


def main() -> int:
    if settings.email_provider.strip().lower() != "brevo":
        raise RuntimeError("Controlled test requires EMAIL_PROVIDER=brevo")
    if settings.max_envios_por_dia > 300 or settings.meta_envios_por_dia > 300:
        raise RuntimeError("Brevo Free quota misconfigured above 300")
    if not RECIPIENT.endswith(("@shopvivaliz.com.br", "@dev.shopvivaliz.com.br")):
        raise RuntimeError("Controlled test recipient must be internal ShopVivaLiz")

    provider = BrevoEmailProvider()
    if provider.from_address.casefold() != BREVO_ALLOWED_SENDER.casefold():
        raise RuntimeError("Brevo sender differs from allowed sender")
    body = _render_test_body()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%SZ")
    subject = f"VALIDACAO CONTROLADA BREVO - Contabilidade Melo - {stamp}"

    with psycopg.connect(settings.database_url, connect_timeout=10) as conn:
        total_before = _rolling_brevo_total(conn)
        if total_before >= settings.max_envios_por_dia:
            raise RuntimeError(
                f"Brevo rolling cap reached before test: {total_before}/{settings.max_envios_por_dia}"
            )
        result = provider.send(RECIPIENT, subject, body)
        if not result.success or result.status != "submitted" or not result.message_id:
            raise RuntimeError(
                f"Brevo controlled submit failed: status={result.status} error={result.error}"
            )
        storage_id = result.message_id
        if not storage_id.startswith("brevo:"):
            raise RuntimeError("Brevo controlled submit missing provider-attributed message id")
        _record_probe(conn, subject=subject, storage_id=storage_id)

    raw_message_id = storage_id.removeprefix("brevo:")
    deadline = time.monotonic() + BREVO_TEST_TIMEOUT_SECONDS
    last_events: list[str] = []
    while time.monotonic() < deadline:
        events = _fetch_events(raw_message_id)
        last_events = [str(event.get("event") or "") for event in events]
        for event in events:
            outcome = classify_event(event)
            if outcome.status == "delivered":
                print("BREVO_TEST_DELIVERED=true")
                print(f"recipient={RECIPIENT}")
                print(f"sender={provider.from_name} <{provider.from_address}>")
                print(f"subject={subject}")
                print(f"provider_message_id={storage_id}")
                print(f"sent_24h_before_probe={total_before}")
                return 0
            if outcome.suppress:
                raise RuntimeError(
                    f"Brevo controlled delivery failed permanently: event={event.get('event')} reason={event.get('reason')}"
                )
        time.sleep(BREVO_TEST_POLL_SECONDS)

    raise RuntimeError(
        f"Brevo controlled delivery timed out after {BREVO_TEST_TIMEOUT_SECONDS}s; events={last_events}"
    )


if __name__ == "__main__":
    raise SystemExit(main())
