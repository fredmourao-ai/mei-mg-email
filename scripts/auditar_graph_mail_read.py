#!/usr/bin/env python3
"""Valida Mail.Read app-only na caixa usada pelo NDR guard, sem expor token."""
from __future__ import annotations

import json
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

from dotenv import load_dotenv

load_dotenv()

from app.email_provider import MicrosoftGraphEmailProvider


def main() -> int:
    provider = MicrosoftGraphEmailProvider()
    token = provider._get_access_token()
    params = urlencode({"$top": "1", "$select": "id,subject,receivedDateTime"})
    url = f"https://graph.microsoft.com/v1.0/users/{quote(provider.address)}/mailFolders/inbox/messages?{params}"
    req = Request(url, headers={"Authorization": f"Bearer {token}", "Accept": "application/json"})
    try:
        with urlopen(req, timeout=30) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")[:500]
        print(f"GRAPH_MAIL_READ_FAILED http={exc.code} detail={detail}")
        return 2
    except (URLError, OSError, ValueError) as exc:
        print(f"GRAPH_MAIL_READ_FAILED error={type(exc).__name__}")
        return 3

    messages = payload.get("value") or []
    print("GRAPH_MAIL_READ_OK")
    print(f"sender={provider.address}")
    print(f"sample_count={len(messages)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
