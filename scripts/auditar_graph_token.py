#!/usr/bin/env python3
"""Validate unattended Microsoft Graph app-only authentication.

No token value is printed. Successful token issuance plus Mail.Send application
role validation proves the configured X.509 application credential is usable.
"""
from __future__ import annotations

import base64
import json
import sys
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))
load_dotenv(BASE_DIR / ".env")

from app.email_provider import MicrosoftGraphEmailProvider


def _decode_segment(value: str) -> dict:
    padded = value + "=" * (-len(value) % 4)
    return json.loads(base64.urlsafe_b64decode(padded.encode("ascii")).decode("utf-8"))


def main() -> int:
    try:
        provider = MicrosoftGraphEmailProvider()
        token = provider._get_access_token()
        parts = token.split(".")
        if len(parts) != 3:
            raise RuntimeError("access token Graph nao possui formato JWT esperado")
        claims = _decode_segment(parts[1])

        aud = str(claims.get("aud") or "")
        roles = {str(role) for role in (claims.get("roles") or [])}
        token_app = str(claims.get("appid") or claims.get("azp") or "").casefold()
        expected_app = provider.client_id.casefold()
        tenant = str(claims.get("tid") or "").casefold()

        if aud not in {"https://graph.microsoft.com", "00000003-0000-0000-c000-000000000000"}:
            raise RuntimeError(f"audience Graph inesperada: {aud or 'vazia'}")
        if "Mail.Send" not in roles:
            raise RuntimeError(f"application role Mail.Send ausente; roles={sorted(roles)}")
        if token_app != expected_app:
            raise RuntimeError(f"appid/azp diverge do client configurado: {token_app or 'vazio'}")
        if tenant and tenant != provider.tenant_id.casefold():
            raise RuntimeError(f"tenant do token diverge do configurado: {tenant}")

        print("GRAPH_APP_ONLY_TOKEN_READY")
        print(f"sender={provider.address}")
        print("auth_mode=app_only_cert")
        print("role_Mail.Send=true")
        print("certificate_credential=validated_by_token_issuance")
        print("token_value=REDACTED")
        return 0
    except Exception as exc:
        print("GRAPH_APP_ONLY_TOKEN_NOT_READY")
        print(f"error={type(exc).__name__}:{exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
