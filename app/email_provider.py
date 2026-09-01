"""ShopVivaliz e-mail provider.

Production delivery is restricted to Microsoft Graph app-only using the X.509
certificate/key installed on the Oracle VM. HTTP 202 means only that Exchange
accepted the message for processing.
"""
from __future__ import annotations

import base64
import hashlib
import html
import json
import logging
import os
import re
import subprocess
import time
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass
from email.message import EmailMessage
from email.policy import SMTP
from email.utils import formataddr, parseaddr
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

from app.email_quality import recipient_has_obvious_provider_typo

logger = logging.getLogger("mei_mg_email.email_provider")
ALLOWED_SENDER = "naoresponda@dev.shopvivaliz.com.br"


@dataclass
class SendResult:
    success: bool
    message_id: str | None = None
    error: str | None = None
    retry_after_seconds: int | None = None
    status: str | None = None
    status_code: int | None = None


class EmailProvider(ABC):
    @abstractmethod
    def send(self, to: str, subject: str, body: str) -> SendResult:
        raise NotImplementedError


class DryRunEmailProvider(EmailProvider):
    def send(self, to: str, subject: str, body: str) -> SendResult:
        fake_id = f"dryrun-{int(time.time() * 1000)}"
        logger.info("DRY-RUN: para=%s assunto=%r chars=%d id=%s", to, subject, len(body), fake_id)
        return SendResult(True, message_id=fake_id, status="dryrun", status_code=0)


def _body_is_html(body: str) -> bool:
    value = body.strip().lower()
    return value.startswith("<!doctype html") or value.startswith("<html") or "<body" in value


def _extract_unsubscribe_url(body: str) -> str | None:
    if not _body_is_html(body):
        return None
    match = re.search(r'href=["\']([^"\']*(?:descad|unsubscribe)[^"\']*)["\']', body, re.I)
    if not match:
        return None
    value = html.unescape(match.group(1)).strip()
    if value.startswith("https://"):
        return value
    return None


def _one_click_unsubscribe_url(unsubscribe_url: str) -> str:
    return unsubscribe_url.replace("/descadastro?", "/descadastro/one-click?", 1)


_LOCAL_PART_RE = re.compile(r"^[A-Za-z0-9!#$%&'*+/=?^_`{|}~.-]+$")
_DOMAIN_LABEL_RE = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?$")


def _is_valid_recipient_address(address: str) -> bool:
    if not isinstance(address, str) or address != address.strip():
        return False
    if not 3 <= len(address) <= 254 or address.count("@") != 1:
        return False
    if recipient_has_obvious_provider_typo(address):
        return False
    local, domain = address.rsplit("@", 1)
    if not 1 <= len(local) <= 64 or not _LOCAL_PART_RE.fullmatch(local):
        return False
    if local.startswith(".") or local.endswith(".") or ".." in local:
        return False
    if not 3 <= len(domain) <= 253 or "." not in domain:
        return False
    labels = domain.split(".")
    return all(1 <= len(label) <= 63 and _DOMAIN_LABEL_RE.fullmatch(label) for label in labels)


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _is_sender_blocked(code: str, message: str) -> bool:
    text = f"{code} {message}".casefold()
    return any(marker in text for marker in ("5.1.8", "42004", "bad outbound sender", "restricted sender"))


class MicrosoftGraphEmailProvider(EmailProvider):
    """Microsoft Graph application authentication using a local X.509 key."""

    def __init__(self) -> None:
        self.tenant_id = os.getenv("MICROSOFT_GRAPH_TENANT_ID", "").strip()
        self.client_id = os.getenv("MICROSOFT_GRAPH_CLIENT_ID", "").strip()
        self.address = os.getenv("MICROSOFT_GRAPH_USER", "").strip()
        self.auth_mode = os.getenv("MICROSOFT_GRAPH_AUTH_MODE", "app_only_cert").strip().lower()
        self.cert_path = Path(os.getenv("MICROSOFT_GRAPH_CERT_PATH", "/home/ubuntu/.shopvivaliz/m365/graph-auth.crt"))
        self.key_path = Path(os.getenv("MICROSOFT_GRAPH_KEY_PATH", "/home/ubuntu/.shopvivaliz/m365/graph-auth.key"))

        raw_from = os.getenv("MAIL_FROM", self.address).strip() or self.address
        parsed_name, parsed_address = parseaddr(raw_from)
        self.from_name = parsed_name.strip() or os.getenv("MAIL_FROM_NAME", "").strip() or "Contabilidade Melo"
        self.from_address = parsed_address.strip() or self.address

        missing = [name for name, value in (
            ("MICROSOFT_GRAPH_TENANT_ID", self.tenant_id),
            ("MICROSOFT_GRAPH_CLIENT_ID", self.client_id),
            ("MICROSOFT_GRAPH_USER", self.address),
        ) if not value]
        if missing:
            raise RuntimeError("Microsoft Graph app-only missing configuration: " + ", ".join(missing))
        if self.auth_mode != "app_only_cert":
            raise RuntimeError("Autenticacao Graph interativa/delegada esta desabilitada; use app_only_cert.")
        if self.address.casefold() != ALLOWED_SENDER.casefold() or self.from_address.casefold() != ALLOWED_SENDER.casefold():
            raise RuntimeError(f"Remetente Graph bloqueado por fail-closed. Permitido somente {ALLOWED_SENDER}.")
        if not self.cert_path.is_file() or not self.key_path.is_file():
            raise RuntimeError("Microsoft Graph app-only certificate/key not found on server")
        if os.getenv("MICROSOFT_GRAPH_CLIENT_SECRET", "").strip():
            raise RuntimeError("Client secret is forbidden; certificate app-only is required")

        self._token: str | None = None
        self._expires_at = 0
        logger.warning("MicrosoftGraphEmailProvider APP-ONLY active sender=%s cert=%s", self.address, self.cert_path)

    @property
    def _token_url(self) -> str:
        return f"https://login.microsoftonline.com/{self.tenant_id}/oauth2/v2.0/token"

    def _certificate_thumbprint_b64url(self) -> str:
        try:
            der = subprocess.check_output(["openssl", "x509", "-in", str(self.cert_path), "-outform", "DER"], timeout=15)
        except (OSError, subprocess.SubprocessError) as exc:
            raise RuntimeError(f"Falha ao ler certificado Graph: {exc}") from exc
        return _b64url(hashlib.sha1(der).digest())

    def _client_assertion(self) -> str:
        now = int(time.time())
        header = _b64url(json.dumps({"alg": "RS256", "typ": "JWT", "x5t": self._certificate_thumbprint_b64url()}, separators=(",", ":")).encode())
        payload = _b64url(json.dumps({
            "aud": self._token_url,
            "iss": self.client_id,
            "sub": self.client_id,
            "jti": str(uuid.uuid4()),
            "nbf": now - 60,
            "exp": now + 540,
        }, separators=(",", ":")).encode())
        unsigned = f"{header}.{payload}".encode("ascii")
        try:
            signature = subprocess.check_output(["openssl", "dgst", "-sha256", "-sign", str(self.key_path)], input=unsigned, timeout=15)
        except (OSError, subprocess.SubprocessError) as exc:
            raise RuntimeError(f"Falha ao assinar client assertion Graph: {exc}") from exc
        return unsigned.decode("ascii") + "." + _b64url(signature)

    def _get_access_token(self) -> str:
        if self._token and self._expires_at > int(time.time()) + 300:
            return self._token
        values = {
            "client_id": self.client_id,
            "scope": "https://graph.microsoft.com/.default",
            "grant_type": "client_credentials",
            "client_assertion_type": "urn:ietf:params:oauth:client-assertion-type:jwt-bearer",
            "client_assertion": self._client_assertion(),
        }
        req = Request(self._token_url, data=urlencode(values).encode(), headers={"Content-Type": "application/x-www-form-urlencoded"}, method="POST")
        try:
            with urlopen(req, timeout=30) as response:
                token = json.loads(response.read().decode())
        except HTTPError as error:
            detail = error.read().decode("utf-8", "replace")
            raise RuntimeError(f"Microsoft Graph app-only OAuth HTTP {error.code}: {detail[:400]}") from error
        except (URLError, OSError, ValueError) as error:
            raise RuntimeError(f"Microsoft Graph app-only OAuth falhou: {error}") from error
        access_token = str(token.get("access_token") or "")
        expires_in = int(token.get("expires_in") or 0)
        if not access_token or expires_in <= 0:
            raise RuntimeError("Microsoft Graph app-only OAuth nao retornou token valido")
        self._token = access_token
        self._expires_at = int(time.time()) + expires_in
        return access_token

    def authenticate(self) -> None:
        self._get_access_token()

    @staticmethod
    def _parse_retry_after(error: HTTPError) -> int | None:
        value = error.headers.get("Retry-After") if error.headers else None
        try:
            return max(int(value), 0) if value else None
        except (TypeError, ValueError):
            return None

    def _mime_payload(self, to: str, subject: str, body: str, unsubscribe_url: str) -> bytes:
        msg = EmailMessage(policy=SMTP.clone(max_line_length=998))
        msg["From"] = formataddr((self.from_name, self.address))
        msg["To"] = to
        msg["Reply-To"] = "fiscalmelo@hotmail.com"
        msg["Subject"] = subject
        msg["List-Unsubscribe"] = f"<{_one_click_unsubscribe_url(unsubscribe_url)}>"
        msg["List-Unsubscribe-Post"] = "List-Unsubscribe=One-Click"
        msg["X-ShopVivaliz-Transactional-Class"] = "marketing-authorized"
        if _body_is_html(body):
            msg.set_content("Esta mensagem possui uma versao HTML. Use o link de descadastro para nao receber novas comunicacoes.")
            msg.add_alternative(body, subtype="html")
        else:
            msg.set_content(body)
        return base64.b64encode(msg.as_bytes())

    def send(self, to: str, subject: str, body: str) -> SendResult:
        if not _is_valid_recipient_address(to):
            return SendResult(
                False,
                error="recipient_invalid_format",
                status="invalid_recipient",
                status_code=0,
            )
        unsubscribe_url = _extract_unsubscribe_url(body)
        endpoint = f"https://graph.microsoft.com/v1.0/users/{quote(self.address)}/sendMail"
        headers = {"Authorization": "Bearer " + self._get_access_token()}
        if unsubscribe_url:
            data = self._mime_payload(to, subject, body, unsubscribe_url)
            headers["Content-Type"] = "text/plain"
        else:
            sender_identity = {"emailAddress": {"address": self.address, "name": self.from_name}}
            payload = {
                "message": {
                    "subject": subject,
                    "body": {"contentType": "HTML" if _body_is_html(body) else "Text", "content": body},
                    "from": sender_identity,
                    "sender": sender_identity,
                    "toRecipients": [{"emailAddress": {"address": to}}],
                },
                "saveToSentItems": True,
            }
            data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            headers["Content-Type"] = "application/json; charset=utf-8"

        try:
            req = Request(endpoint, data=data, headers=headers, method="POST")
            with urlopen(req, timeout=30) as response:
                status_code = int(response.status)
                request_id = response.headers.get("request-id") or response.headers.get("client-request-id")
                if status_code not in (200, 202):
                    return SendResult(False, message_id=request_id, error=f"Microsoft Graph HTTP {status_code}", status="error", status_code=status_code)
            return SendResult(True, message_id=request_id, status="submitted", status_code=status_code)
        except HTTPError as error:
            retry_after = self._parse_retry_after(error)
            try:
                detail = json.loads(error.read().decode("utf-8"))
            except Exception:
                detail = {}
            graph_error = detail.get("error", {}) if isinstance(detail, dict) else {}
            code = str(graph_error.get("code") or f"http_{error.code}")
            message = str(graph_error.get("message") or "")
            mapped = "sender_blocked" if _is_sender_blocked(code, message) else "error"
            compact = message.replace("\n", " ").strip()[:500]
            error_text = f"Microsoft Graph: {code}; http_{error.code}" + (f"; {compact}" if compact else "")
            return SendResult(False, error=error_text, retry_after_seconds=retry_after, status=mapped, status_code=int(error.code))
        except (RuntimeError, URLError, OSError, subprocess.SubprocessError) as error:
            return SendResult(False, error=str(error), status="error")


def get_email_provider(name: str) -> EmailProvider:
    normalized = (name or "").strip().lower()
    if normalized == "dryrun":
        return DryRunEmailProvider()
    if normalized in {"microsoft_graph", "microsoft-oauth", "graph"}:
        return MicrosoftGraphEmailProvider()
    if normalized in {"gmail", "microsoft", "outlook", "office365", "brevo", "brevo_api", "smtp"}:
        raise RuntimeError(f"Email provider '{normalized}' is disabled. ShopVivaliz production is Microsoft Graph app-only only.")
    raise ValueError("Unknown e-mail provider. Use 'dryrun' or 'microsoft_graph'.")
