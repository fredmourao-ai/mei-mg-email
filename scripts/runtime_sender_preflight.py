#!/usr/bin/env python3
"""Fail-closed startup preflight for the Brevo first-send worker."""
from __future__ import annotations

import json
import os
from email.utils import parseaddr
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

import psycopg
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env", override=True)

from app.config import settings

ALLOWED_SENDER = "atendimento@shopvivaliz.com.br"
REQUIRED_EMPRESA_COLUMNS = (
    "email",
    "opt_out",
    "situacao_cadastral",
)
ALLOWED_UNSUBSCRIBE_HOSTS = {"dev.shopvivaliz.com.br", "shopvivaliz.com.br"}


def _validate_public_unsubscribe() -> dict[str, object]:
    raw_url = os.getenv("BASE_URL_DESCADASTRO", "").strip()
    parsed = urlsplit(raw_url)
    if parsed.scheme != "https" or parsed.hostname not in ALLOWED_UNSUBSCRIBE_HOSTS:
        raise RuntimeError("BASE_URL_DESCADASTRO must be public HTTPS on ShopVivaliz")
    req = Request(raw_url, headers={"User-Agent": "mei-mg-email-preflight/1.0"}, method="GET")
    try:
        with urlopen(req, timeout=8) as response:
            status = int(response.status)
            final = urlsplit(response.geturl())
            content_type = str(response.headers.get("Content-Type") or "")
            response.read(512)
    except HTTPError as exc:
        raise RuntimeError(f"unsubscribe endpoint HTTP {exc.code}") from exc
    except (URLError, OSError) as exc:
        raise RuntimeError(f"unsubscribe endpoint unavailable: {exc}") from exc
    if status != 200 or final.scheme != "https" or final.hostname not in ALLOWED_UNSUBSCRIBE_HOSTS:
        raise RuntimeError("unsubscribe endpoint did not remain healthy public HTTPS")
    if "text/html" not in content_type.casefold():
        raise RuntimeError("unsubscribe endpoint must return HTML")
    return {"unsubscribe_url": raw_url, "unsubscribe_http_status": status}


def _validate_runtime_config() -> dict[str, object]:
    provider = os.getenv("EMAIL_PROVIDER", "").strip().lower()
    if provider != "brevo":
        raise RuntimeError(f"EMAIL_PROVIDER must be brevo, got {provider!r}")
    api_key = os.getenv("BREVO_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("BREVO_API_KEY missing")
    raw_from = os.getenv("MAIL_FROM", "").strip()
    _, sender = parseaddr(raw_from)
    if sender.casefold() != ALLOWED_SENDER.casefold():
        raise RuntimeError(f"MAIL_FROM must be {ALLOWED_SENDER}")

    raw_max = int(os.getenv("MAX_ENVIOS_POR_DIA", "0"))
    raw_meta = int(os.getenv("META_ENVIOS_POR_DIA", "0"))
    if raw_max <= 0 or raw_max > 300:
        raise RuntimeError("MAX_ENVIOS_POR_DIA must be between 1 and 300 for Brevo Free")
    if raw_meta <= 0 or raw_meta > 300:
        raise RuntimeError("META_ENVIOS_POR_DIA must be between 1 and 300 for Brevo Free")
    if raw_meta > raw_max:
        raise RuntimeError("META_ENVIOS_POR_DIA cannot exceed MAX_ENVIOS_POR_DIA")
    if settings.max_envios_por_dia > 300 or settings.meta_envios_por_dia > 300:
        raise RuntimeError("effective Brevo quota exceeds 300")

    return {
        "email_provider": provider,
        "sender": sender,
        "brevo_api_key_present": True,
        "max_24h": settings.max_envios_por_dia,
        "meta_24h": settings.meta_envios_por_dia,
    }


def main() -> int:
    out: dict[str, object] = {"runtime_sender_preflight": "ok"}
    out.update(_validate_runtime_config())
    out.update(_validate_public_unsubscribe())
    database_url = os.environ["DATABASE_URL"]
    with psycopg.connect(database_url, connect_timeout=5) as conn:
        with conn.cursor() as cur:
            cur.execute("set statement_timeout='5s'")
            cur.execute("set lock_timeout='1s'")
            cur.execute(
                """
                select column_name
                  from information_schema.columns
                 where table_schema='mei_email'
                   and table_name='empresas'
                   and column_name = any(%s::text[])
                """,
                (list(REQUIRED_EMPRESA_COLUMNS),),
            )
            present = {str(row[0]) for row in cur.fetchall()}
            missing = sorted(set(REQUIRED_EMPRESA_COLUMNS) - present)
            if missing:
                raise RuntimeError("required empresa columns unavailable: " + ",".join(missing))

            cur.execute(
                """
                select
                  to_regclass('mei_email.envios') is not null,
                  to_regclass('mei_email.campanhas') is not null,
                  to_regclass('mei_email.envios_externos_cota') is not null,
                  to_regprocedure('mei_email.is_valid_email_address(citext)') is not null,
                  to_regprocedure('mei_email.register_operational_suppression(text,citext,text,text,text,timestamptz)') is not null
                """
            )
            envios_ok, campanhas_ok, external_ok, validator_ok, suppression_ok = cur.fetchone()
            out.update(
                {
                    "envios": bool(envios_ok),
                    "campanhas": bool(campanhas_ok),
                    "external_quota_ledger": bool(external_ok),
                    "email_validator": bool(validator_ok),
                    "suppression_function": bool(suppression_ok),
                }
            )

    required = (
        "envios",
        "campanhas",
        "external_quota_ledger",
        "email_validator",
        "suppression_function",
    )
    if not all(bool(out[key]) for key in required):
        raise RuntimeError("required Brevo send schema primitive unavailable")
    print(json.dumps(out, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
