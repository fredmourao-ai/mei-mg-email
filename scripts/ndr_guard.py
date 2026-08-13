#!/usr/bin/env python3
"""Circuit breaker assíncrono para NDRs de bloqueio do remetente.

O Microsoft Graph sendMail pode responder HTTP 202 e o Exchange gerar um NDR
segundos depois. Este processo observa a caixa do remetente via Graph Mail.Read
e abre o mesmo sentinel usado pelo worker quando encontra AS(42004), 5.1.8 ou
mensagem equivalente de bad/restricted outbound sender.

Este processo nunca envia e-mail e nunca remove a pausa automaticamente.
"""
from __future__ import annotations

import json
import logging
import os
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env", override=True)

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
    "bad outbound sender",
    "restricted sender",
    "address was not recognized as a valid sender",
)


def contains_sender_blocked_marker(text: str | None) -> bool:
    normalized = (text or "").casefold()
    return any(marker in normalized for marker in BLOCK_MARKERS)


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
    url = f"https://graph.microsoft.com/v1.0/users/{quote(provider.address)}/mailFolders/inbox/messages?{params}"
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

    for message in messages:
        message_id = str(message.get("id") or "")
        if not message_id or message_id in seen_set:
            continue
        newly_seen.append(message_id)
        subject = str(message.get("subject") or "")
        preview = str(message.get("bodyPreview") or "")
        if not looks_like_ndr(subject, preview):
            continue

        text = f"{subject}\n{preview}"
        if not contains_sender_blocked_marker(text):
            text = _full_message_text(provider, message_id)
        if not contains_sender_blocked_marker(text):
            continue

        received_at = str(message.get("receivedDateTime") or "")
        _open_pause(
            message_id=message_id,
            received_at=received_at,
            detail="AS(42004)/5.1.8 sender restriction detected in asynchronous NDR",
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
        _save_state(state)
        return True

    if newly_seen:
        state["seen_ids"] = (newly_seen + seen)[:500]
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
