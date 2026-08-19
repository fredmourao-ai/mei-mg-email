#!/usr/bin/env python3
"""Recover a stale sender-block sentinel only after live, fail-closed proof.

This script never unblocks Exchange. It only removes the local pause after all of
these are true: the sentinel is old enough for propagation, Exchange reports the
sender is not restricted, Graph app-only authentication works, a single internal
controlled send is accepted, no blocking NDR appears during the observation
window, Exchange still reports the sender unrestricted, and the probe is written
to the external quota ledger.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

import psycopg
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parents[1]
load_dotenv(BASE_DIR / ".env", override=True)

from app.config import settings
from app.email_provider import ALLOWED_SENDER, MicrosoftGraphEmailProvider
import ndr_guard

SENTINEL_PATH = Path(
    os.getenv(
        "SENDER_BLOCK_SENTINEL_PATH",
        "/var/lib/mei-mg-email/sender_blocked.pause",
    )
)
LEGACY_SENTINEL_PATH = BASE_DIR / "runtime" / "sender_blocked.pause"
STATE_PATH = Path(
    os.getenv(
        "SENDER_BLOCK_RECOVERY_STATE_PATH",
        "/var/lib/mei-mg-email/sender_block_recovery_state.json",
    )
)
TEST_RECIPIENT = os.getenv(
    "SENDER_BLOCK_RECOVERY_TEST_RECIPIENT",
    "atendimento@shopvivaliz.com.br",
).strip()
MIN_AGE_MINUTES = min(
    max(int(os.getenv("SENDER_BLOCK_RECOVERY_MIN_AGE_MINUTES", "15")), 5),
    120,
)
NDR_WAIT_SECONDS = min(
    max(int(os.getenv("SENDER_BLOCK_RECOVERY_NDR_WAIT_SECONDS", "120")), 60),
    300,
)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _is_internal_recipient(address: str) -> bool:
    value = address.casefold().strip()
    return value.endswith("@shopvivaliz.com.br") or value.endswith(
        "@dev.shopvivaliz.com.br"
    )


def _sentinel_age_minutes(path: Path) -> float:
    raw = path.read_text(encoding="utf-8", errors="replace")
    for line in raw.splitlines():
        if line.startswith("blocked_at_utc="):
            value = line.split("=", 1)[1].strip().replace("Z", "+00:00")
            try:
                blocked_at = datetime.fromisoformat(value)
                if blocked_at.tzinfo is None:
                    blocked_at = blocked_at.replace(tzinfo=timezone.utc)
                return max((_now() - blocked_at.astimezone(timezone.utc)).total_seconds() / 60, 0)
            except ValueError:
                break
    return max((_now().timestamp() - path.stat().st_mtime) / 60, 0)


def _exchange_not_blocked() -> str:
    command = [
        "pwsh",
        "-NoProfile",
        "-File",
        str(BASE_DIR / "scripts" / "desbloquear_exchange_app_cert.ps1"),
    ]
    completed = subprocess.run(
        command,
        cwd=BASE_DIR,
        capture_output=True,
        text=True,
        timeout=240,
        check=False,
    )
    output = (completed.stdout or "") + "\n" + (completed.stderr or "")
    if completed.returncode != 0:
        raise RuntimeError(
            f"exchange restriction check failed rc={completed.returncode}: {output[-1600:]}"
        )
    if "EXCHANGE_SENDER_NOT_BLOCKED" not in output:
        raise RuntimeError("exchange did not prove sender unrestricted")
    return output


def _rolling_total_24h(conn: psycopg.Connection) -> int:
    with conn.cursor() as cur:
        cur.execute(
            """
            select
              (select count(*) from mei_email.envios
                where status in ('submitted','enviado')
                  and enviado_em >= now() - interval '24 hours')
              +
              (select count(*) from mei_email.envios_externos_cota
                where sent_at >= now() - interval '24 hours')
            """
        )
        return int(cur.fetchone()[0] or 0)


def _record_probe(
    conn: psycopg.Connection,
    *,
    recipient: str,
    subject: str,
    provider_message_id: str | None,
) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            insert into mei_email.envios_externos_cota
                (email, subject, sent_at, source, provider_message_id, metadata)
            values (%s, %s, now(), 'sender_block_recovery_probe', %s, %s::jsonb)
            on conflict (provider_message_id) do nothing
            """,
            (
                recipient,
                subject,
                provider_message_id,
                json.dumps({"purpose": "controlled_sender_recovery"}),
            ),
        )
    conn.commit()


def _persist(payload: dict) -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = STATE_PATH.with_suffix(".tmp")
    tmp.write_text(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str) + "\n",
        encoding="utf-8",
    )
    tmp.replace(STATE_PATH)


def main() -> int:
    present = [path for path in (SENTINEL_PATH, LEGACY_SENTINEL_PATH) if path.is_file()]
    if not present:
        print("SENDER_BLOCK_SENTINEL_ABSENT=true")
        return 0

    oldest_age = min(_sentinel_age_minutes(path) for path in present)
    if oldest_age < MIN_AGE_MINUTES:
        raise RuntimeError(
            f"sender-block sentinel too recent for safe recovery: age={oldest_age:.1f}m"
        )
    if not _is_internal_recipient(TEST_RECIPIENT):
        raise RuntimeError("controlled recovery recipient must be an internal ShopVivaliz address")

    exchange_before = _exchange_not_blocked()
    provider = MicrosoftGraphEmailProvider()
    provider.authenticate()
    if provider.address.casefold() != ALLOWED_SENDER.casefold():
        raise RuntimeError("Graph sender differs from the fail-closed allowed sender")

    if ndr_guard.check_once(provider):
        raise RuntimeError("current sender-block NDR detected before controlled probe")

    with psycopg.connect(settings.database_url, connect_timeout=10) as conn:
        total_before = _rolling_total_24h(conn)
        if total_before >= settings.max_envios_por_dia:
            raise RuntimeError(
                f"hard cap already reached: sent_24h={total_before} cap={settings.max_envios_por_dia}"
            )
        stamp = _now().strftime("%Y%m%d-%H%M%SZ")
        subject = f"VALIDACAO CONTROLADA SENDER RECOVERY {stamp}"
        body = (
            "Validacao interna e controlada do remetente ShopVivaliz. "
            "Esta mensagem existe apenas para confirmar a recuperacao segura do circuito de envio."
        )
        result = provider.send(TEST_RECIPIENT, subject, body)
        if not result.success or result.status != "submitted":
            raise RuntimeError(
                f"controlled Graph probe failed: status={result.status} error={result.error}"
            )
        _record_probe(
            conn,
            recipient=TEST_RECIPIENT,
            subject=subject,
            provider_message_id=result.message_id,
        )

    time.sleep(NDR_WAIT_SECONDS)
    if ndr_guard.check_once(provider):
        raise RuntimeError("sender-block NDR detected after controlled probe")
    exchange_after = _exchange_not_blocked()

    hashes: dict[str, str] = {}
    for path in present:
        content = path.read_bytes()
        hashes[str(path)] = hashlib.sha256(content).hexdigest()
        path.unlink()

    payload = {
        "recovered_at_utc": _now().isoformat(),
        "sender": provider.address,
        "test_recipient": TEST_RECIPIENT,
        "probe_subject": subject,
        "probe_status": result.status,
        "probe_status_code": result.status_code,
        "probe_request_id": result.message_id,
        "sent_24h_before_probe": total_before,
        "sentinel_age_minutes": round(oldest_age, 2),
        "removed_sentinel_sha256": hashes,
        "exchange_verified_before": "EXCHANGE_SENDER_NOT_BLOCKED" in exchange_before,
        "exchange_verified_after": "EXCHANGE_SENDER_NOT_BLOCKED" in exchange_after,
        "result": "stale_sender_block_sentinel_cleared_after_live_verification",
    }
    _persist(payload)
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str))
    print("SENDER_BLOCK_RECOVERY_VERIFIED=true")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
