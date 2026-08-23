#!/usr/bin/env python3
"""Circuit breaker assíncrono para NDRs do remetente e hard bounces.

O Microsoft Graph sendMail pode responder HTTP 202 e o Exchange gerar um NDR
segundos depois. Este processo observa a caixa do remetente via Graph Mail.Read.

Dois comportamentos são deliberadamente separados:
* bloqueio sistêmico do remetente (AS(42004), 5.1.8 etc.) abre o sentinel e
  interrompe globalmente os envios;
* falha permanente de um destinatário individual registra hard-bounce na
  suppression list e deixa os demais destinatários autorizados seguirem.

Para evitar suprimir o endereço errado, um hard-bounce só é persistido quando
existe exatamente um endereço no NDR que também consta no histórico terminal
de um envio anterior. O message id do NDR é preservado como source_ref.

Este processo nunca envia e-mail e nunca remove a pausa automaticamente.
"""
from __future__ import annotations

import json
import logging
import os
import re
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

import psycopg
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env", override=True)

from app.config import settings
from app.email_provider import MicrosoftGraphEmailProvider

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("mei_mg_email.ndr_guard")

POLL_SECONDS = max(int(os.getenv("NDR_GUARD_POLL_SECONDS", "60")), 15)
LOOKBACK_MINUTES = max(int(os.getenv("NDR_GUARD_LOOKBACK_MINUTES", "20")), 5)
MAX_MESSAGES = min(max(int(os.getenv("NDR_GUARD_MAX_MESSAGES", "50")), 5), 100)
STATE_PATH = Path(os.getenv("NDR_GUARD_STATE_PATH", "/var/lib/mei-mg-email/ndr_guard_state.json"))
SENTINEL_PATH = Path(os.getenv("SENDER_BLOCK_SENTINEL_PATH", "/var/lib/mei-mg-email/sender_blocked.pause"))

BLOCK_MARKERS = (
    "as(42004)",
    "5.1.8",
    "5.1.90",
    "as:46601",
    "24 hour limit for message recipients",
    "daily limit for message recipients",
    "bad outbound sender",
    "restricted sender",
    "address was not recognized as a valid sender",
)

# Keep this intentionally narrow. Generic 5.7.x policy/reputation rejections and
# routing loops are not automatically converted into permanent recipient
# suppressions because they can be transient or domain-wide operational issues.
PERMANENT_RECIPIENT_MARKERS = (
    "550 5.1.1",
    "5.1.10",
    "recipient address rejected: user unknown",
    "recipient not found",
    "mailbox not found",
    "address not found",
    "user unknown",
    "no such user",
    "recipient does not exist",
    "email account that you tried to reach does not exist",
    "domain does not exist",
    "domain not found",
    "host or domain name not found",
)

EMAIL_RE = re.compile(r"(?i)(?<![A-Z0-9._%+-])([A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,})(?![A-Z0-9._%+-])")


def contains_sender_blocked_marker(text: str | None) -> bool:
    normalized = (text or "").casefold()
    return any(marker in normalized for marker in BLOCK_MARKERS)


def is_permanent_recipient_ndr(text: str | None) -> bool:
    normalized = (text or "").casefold()
    if contains_sender_blocked_marker(normalized):
        return False
    return any(marker in normalized for marker in PERMANENT_RECIPIENT_MARKERS)


def extract_email_addresses(text: str | None) -> list[str]:
    """Extract normalized addresses from an NDR body without guessing targets."""
    values = {
        match.group(1).strip().casefold()
        for match in EMAIL_RE.finditer(text or "")
    }
    return sorted(
        value
        for value in values
        if not value.endswith("@invalid.local")
        and not value.startswith("microsoftexchange")
    )


def looks_like_ndr(subject: str | None, preview: str | None = None) -> bool:
    text = f"{subject or ''} {preview or ''}".casefold()
    return any(
        marker in text
        for marker in (
            "undeliverable",
            "não é possível entregar",
            "nao e possivel entregar",
            "delivery has failed",
            "delivery status notification",
            "address not found",
            "suspected of sending spam",
        )
    )


def _load_state() -> dict:
    try:
        return json.loads(STATE_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return {"seen_ids": []}


def _save_state(state: dict) -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = STATE_PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    tmp.replace(STATE_PATH)


def _graph_json(token: str, url: str) -> dict:
    req = Request(
        url,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
            "Prefer": 'outlook.body-content-type="text"',
        },
    )
    try:
        with urlopen(req, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")[:800]
        raise RuntimeError(f"NDR_GUARD_GRAPH_HTTP_{exc.code}: {detail}") from exc
    except (URLError, OSError, ValueError) as exc:
        raise RuntimeError(f"NDR_GUARD_GRAPH_ERROR: {exc}") from exc


def _recent_messages(provider: MicrosoftGraphEmailProvider) -> list[dict]:
    token = provider._get_access_token()
    since = (datetime.now(timezone.utc) - timedelta(minutes=LOOKBACK_MINUTES)).isoformat().replace("+00:00", "Z")
    params = urlencode(
        {
            "$top": str(MAX_MESSAGES),
            "$filter": f"receivedDateTime ge {since}",
            "$orderby": "receivedDateTime desc",
            "$select": "id,subject,receivedDateTime,bodyPreview",
        }
    )
    # NDRs can be moved out of Inbox immediately by mailbox rules (for example
    # into a dedicated Microsoft/NDR folder). Query the mailbox-wide messages
    # collection so hard bounces and sender restrictions remain observable
    # regardless of which folder currently contains the report.
    url = f"https://graph.microsoft.com/v1.0/users/{quote(provider.address)}/messages?{params}"
    payload = _graph_json(token, url)
    return list(payload.get("value") or [])


def _full_message_text(provider: MicrosoftGraphEmailProvider, message_id: str) -> str:
    token = provider._get_access_token()
    params = urlencode({"$select": "id,subject,receivedDateTime,body,bodyPreview"})
    url = f"https://graph.microsoft.com/v1.0/users/{quote(provider.address)}/messages/{quote(message_id)}?{params}"
    payload = _graph_json(token, url)
    body = payload.get("body") or {}
    return "\n".join(
        str(value or "")
        for value in (
            payload.get("subject"),
            payload.get("bodyPreview"),
            body.get("content") if isinstance(body, dict) else body,
        )
    )


def _previously_sent_recipient_matches(
    addresses: list[str], *, sender_address: str
) -> list[str]:
    """Return exact NDR addresses that have a terminal prior-send record."""
    normalized = sorted(
        {
            value.casefold()
            for value in addresses
            if value.casefold() != sender_address.casefold()
        }
    )
    if not normalized:
        return []
    with psycopg.connect(settings.database_url, connect_timeout=10) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                select distinct lower(btrim(email::text))
                  from mei_email.envios
                 where status::text in ('submitted','enviado','delivered','bounced')
                   and lower(btrim(email::text)) = any(%s::text[])
                """,
                (normalized,),
            )
            return sorted({str(row[0]).casefold() for row in cur.fetchall()})


def _record_permanent_recipient_suppression(
    *,
    provider: MicrosoftGraphEmailProvider,
    message_id: str,
    received_at: str | None,
    text: str,
) -> bool:
    """Turn an unambiguous hard NDR into a durable technical suppression."""
    if not is_permanent_recipient_ndr(text):
        return False

    candidates = extract_email_addresses(text)
    matches = _previously_sent_recipient_matches(
        candidates,
        sender_address=provider.address,
    )
    if len(matches) != 1:
        logger.warning(
            "NDR_HARD_BOUNCE_NOT_SUPPRESSED ambiguous_match_count=%d message_id=%s",
            len(matches),
            message_id,
        )
        return False

    recipient = matches[0]
    with psycopg.connect(settings.database_url, connect_timeout=10) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                select mei_email.register_operational_suppression(
                    null,
                    %s::public.citext,
                    'hard_bounce',
                    'async_ndr_graph_guard',
                    %s,
                    coalesce(%s::timestamptz, now())
                )
                """,
                (recipient, message_id, received_at or None),
            )
        conn.commit()

    logger.warning(
        "NDR_HARD_BOUNCE_SUPPRESSED message_id=%s source=async_ndr_graph_guard",
        message_id,
    )
    return True


def _open_pause(*, message_id: str, received_at: str | None, detail: str) -> None:
    SENTINEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = (
        f"blocked_at_utc={datetime.now(timezone.utc).isoformat()}\n"
        "sender=naoresponda@dev.shopvivaliz.com.br\n"
        "source=async_ndr_graph_guard\n"
        f"ndr_message_id={message_id}\n"
        f"ndr_received_at={received_at or ''}\n"
        f"error={detail[:1000].replace(chr(10), ' ')}\n"
        "resume_allowed=false\n"
    )
    SENTINEL_PATH.write_text(payload, encoding="utf-8")


def check_once(provider: MicrosoftGraphEmailProvider) -> bool:
    state = _load_state()
    seen = list(state.get("seen_ids") or [])
    seen_set = set(str(value) for value in seen)
    messages = _recent_messages(provider)
    newly_seen: list[str] = []
    hard_bounces_suppressed = int(state.get("hard_bounces_suppressed") or 0)

    for message in messages:
        message_id = str(message.get("id") or "")
        if not message_id or message_id in seen_set:
            continue
        newly_seen.append(message_id)
        subject = str(message.get("subject") or "")
        preview = str(message.get("bodyPreview") or "")
        if not looks_like_ndr(subject, preview):
            continue

        # Fetch the full NDR exactly once. Sender-block classification takes
        # precedence over recipient-level suppression.
        text = _full_message_text(provider, message_id)
        if contains_sender_blocked_marker(text):
            received_at = str(message.get("receivedDateTime") or "")
            _open_pause(
                message_id=message_id,
                received_at=received_at,
                detail="Exchange sender or recipient-rate restriction detected in asynchronous NDR",
            )
            logger.critical(
                "NDR_GUARD_SENDER_BLOCKED sender=%s received_at=%s sentinel=%s",
                provider.address,
                received_at,
                SENTINEL_PATH,
            )
            state["last_blocked_ndr_id"] = message_id
            state["last_blocked_ndr_received_at"] = received_at
            state["seen_ids"] = (newly_seen + seen)[:500]
            state["hard_bounces_suppressed"] = hard_bounces_suppressed
            _save_state(state)
            return True

        if _record_permanent_recipient_suppression(
            provider=provider,
            message_id=message_id,
            received_at=str(message.get("receivedDateTime") or "") or None,
            text=text,
        ):
            hard_bounces_suppressed += 1
            state["last_hard_bounce_ndr_id"] = message_id

    if newly_seen:
        state["seen_ids"] = (newly_seen + seen)[:500]
        state["hard_bounces_suppressed"] = hard_bounces_suppressed
        _save_state(state)
    return False


def main() -> int:
    provider = MicrosoftGraphEmailProvider()
    logger.info(
        "NDR guard iniciado sender=%s poll=%ss lookback=%smin sentinel=%s",
        provider.address,
        POLL_SECONDS,
        LOOKBACK_MINUTES,
        SENTINEL_PATH,
    )
    while True:
        try:
            check_once(provider)
        except Exception:
            logger.exception("NDR_GUARD_CHECK_FAILED")
        time.sleep(POLL_SECONDS)


if __name__ == "__main__":
    raise SystemExit(main())
