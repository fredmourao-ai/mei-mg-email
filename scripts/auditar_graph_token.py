#!/usr/bin/env python3
"""Valida o cache OAuth do Microsoft Graph sem iniciar login interativo.

Executar no mesmo host e usuario do worker. O script nunca imprime tokens e
falha fechado se o cache nao puder ser reutilizado/renovado silenciosamente.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))
load_dotenv(BASE_DIR / ".env")

from app.email_provider import MicrosoftGraphEmailProvider


def cached_access_token(provider: MicrosoftGraphEmailProvider) -> str:
    cache = provider._load_cache()
    if cache.get("access_token") and int(cache.get("expires_at", 0)) > int(time.time()) + 120:
        return str(cache["access_token"])

    refresh_token = str(cache.get("refresh_token") or "")
    if not refresh_token:
        raise RuntimeError("cache Graph sem access token valido e sem refresh token")

    response = provider._post_form(
        f"{provider._authority}/oauth2/v2.0/token",
        {
            "grant_type": "refresh_token",
            "client_id": provider.client_id,
            "scope": provider._scope,
            "refresh_token": refresh_token,
        },
    )
    return provider._store_token(response, previous=cache)


def main() -> int:
    try:
        provider = MicrosoftGraphEmailProvider()
        token = cached_access_token(provider)
        req = Request(
            "https://graph.microsoft.com/v1.0/me?$select=id,mail,userPrincipalName",
            headers={"Authorization": f"Bearer {token}"},
            method="GET",
        )
        with urlopen(req, timeout=30) as response:
            payload = json.loads(response.read().decode("utf-8"))

        principal = str(payload.get("userPrincipalName") or "").casefold()
        mail = str(payload.get("mail") or "").casefold()
        expected = provider.address.casefold()
        if expected not in {principal, mail}:
            raise RuntimeError(
                f"usuario do token diverge do remetente configurado: principal={principal or 'vazio'} mail={mail or 'vazio'}"
            )

        print("GRAPH_TOKEN_READY")
        print(f"sender={provider.address}")
        print("scope_expected=User.Read Mail.Send offline_access")
        print("token_value=REDACTED")
        return 0
    except (RuntimeError, HTTPError, URLError, OSError, ValueError) as exc:
        print("GRAPH_TOKEN_NOT_READY")
        print(f"error={type(exc).__name__}:{exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
