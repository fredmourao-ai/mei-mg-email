from __future__ import annotations

import base64
import hashlib
import os
import secrets
import sys
import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlparse

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))
load_dotenv(BASE_DIR / ".env")

from app.email_provider import MicrosoftGraphEmailProvider

HOST = "127.0.0.1"
PORT = 8400
REDIRECT_URI = f"http://localhost:{PORT}"


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def main() -> None:
    provider = MicrosoftGraphEmailProvider()
    state = secrets.token_urlsafe(24)
    verifier = secrets.token_urlsafe(64)
    challenge = _b64url(hashlib.sha256(verifier.encode("ascii")).digest())
    result: dict[str, str] = {}
    done = threading.Event()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format: str, *args) -> None:
            return

        def do_GET(self) -> None:
            parsed = urlparse(self.path)
            params = parse_qs(parsed.query)
            if params.get("state", [""])[0] != state:
                self.send_response(400)
                self.end_headers()
                self.wfile.write(b"Invalid OAuth state")
                return
            if params.get("error"):
                result["error"] = params.get("error_description", params["error"])[0]
            else:
                result["code"] = params.get("code", [""])[0]
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(
                "<html><body style='font-family:Arial;padding:32px'>"
                "<h2>Autorizacao concluida</h2>"
                "<p>Voce pode fechar esta janela. O ShopVivaliz continuara a validacao automaticamente.</p>"
                "</body></html>".encode("utf-8")
            )
            done.set()

    server = HTTPServer((HOST, PORT), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    authorize_url = (
        f"{provider._authority}/oauth2/v2.0/authorize?"
        + urlencode(
            {
                "client_id": provider.client_id,
                "response_type": "code",
                "redirect_uri": REDIRECT_URI,
                "response_mode": "query",
                "scope": provider._scope,
                "state": state,
                "code_challenge": challenge,
                "code_challenge_method": "S256",
                "prompt": "select_account",
                "login_hint": provider.address,
            }
        )
    )

    print("GRAPH_BROWSER_AUTH_STARTED", flush=True)
    print(f"sender={provider.address}", flush=True)
    webbrowser.open(authorize_url, new=1, autoraise=True)

    if not done.wait(timeout=600):
        server.shutdown()
        raise SystemExit("GRAPH_BROWSER_AUTH_TIMEOUT")
    server.shutdown()

    if result.get("error"):
        raise SystemExit("GRAPH_BROWSER_AUTH_ERROR: " + result["error"])
    code = result.get("code") or ""
    if not code:
        raise SystemExit("GRAPH_BROWSER_AUTH_ERROR: authorization code ausente")

    token = provider._post_form(
        f"{provider._authority}/oauth2/v2.0/token",
        {
            "client_id": provider.client_id,
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": REDIRECT_URI,
            "scope": provider._scope,
            "code_verifier": verifier,
        },
    )
    provider._store_token(token)
    print("GRAPH_BROWSER_AUTH_READY", flush=True)
    print("token_value=REDACTED", flush=True)


if __name__ == "__main__":
    main()
