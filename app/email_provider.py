"""Email provider abstraction.

Real delivery is Microsoft Graph only. SMTP is intentionally unsupported.
Production authentication is app-only with an X.509 certificate; no
browser/device-code login is required for production sends.
"""
from __future__ import annotations

import json
import logging
import os
import subprocess
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from email.utils import parseaddr
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

logger = logging.getLogger("mei_mg_email.email_provider")


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
        logger.info(
            "DRY-RUN: enviaria e-mail para=%s assunto=%r corpo(%d chars) id=%s",
            to,
            subject,
            len(body),
            fake_id,
        )
        return SendResult(success=True, message_id=fake_id, status="dryrun", status_code=0)


def _body_is_html(body: str) -> bool:
    body_lower = body.strip().lower()
    return body_lower.startswith("<!doctype html") or body_lower.startswith("<html") or "<body" in body_lower


def _is_sender_blocked(code: str, message: str) -> bool:
    text = f"{code} {message}".casefold()
    return "5.1.8" in text and ("42004" in text or "sender" in text or "outbound" in text)


class MicrosoftGraphEmailProvider(EmailProvider):
    """Microsoft Graph provider using unattended certificate app-only OAuth2."""

    def __init__(self) -> None:
        self.tenant_id = os.getenv("MICROSOFT_GRAPH_TENANT_ID", "").strip()
        self.client_id = os.getenv("MICROSOFT_GRAPH_CLIENT_ID", "").strip()
        self.address = os.getenv("MICROSOFT_GRAPH_USER", "").strip()
        self.auth_mode = os.getenv("MICROSOFT_GRAPH_AUTH_MODE", "app_only_cert").strip().lower()
        self.certificate_thumbprint = os.getenv("MICROSOFT_GRAPH_CERT_THUMBPRINT", "").replace(" ", "").strip().upper()

        raw_from = os.getenv("MAIL_FROM", self.address).strip() or self.address
        parsed_name, parsed_address = parseaddr(raw_from)
        self.from_name = parsed_name.strip() or os.getenv("MAIL_FROM_NAME", "").strip() or "Contabilidade Melo"
        self.from_address = parsed_address.strip() or self.address

        base_dir = Path(__file__).resolve().parent.parent
        configured_broker = os.getenv("MICROSOFT_GRAPH_TOKEN_BROKER", "").strip()
        self.token_broker = Path(configured_broker) if configured_broker else base_dir / "scripts" / "get_graph_app_token.ps1"

        if not self.tenant_id or not self.client_id or not self.address:
            raise RuntimeError(
                "EMAIL_PROVIDER=microsoft_graph exige MICROSOFT_GRAPH_TENANT_ID, "
                "MICROSOFT_GRAPH_CLIENT_ID e MICROSOFT_GRAPH_USER."
            )
        if self.auth_mode != "app_only_cert":
            raise RuntimeError(
                "Autenticacao Graph interativa/delegada esta desabilitada para producao. "
                "Use MICROSOFT_GRAPH_AUTH_MODE=app_only_cert."
            )
        if not self.certificate_thumbprint:
            raise RuntimeError("MICROSOFT_GRAPH_CERT_THUMBPRINT nao configurado.")
        if not self.token_broker.is_file():
            raise RuntimeError(f"token broker Graph ausente: {self.token_broker}")
        if self.from_address.casefold() != self.address.casefold():
            raise RuntimeError(
                "MAIL_FROM precisa usar o mesmo endereco de MICROSOFT_GRAPH_USER; "
                "spoof de endereco e bloqueado."
            )

        self._token: str | None = None
        self._token_expires_at = 0
        logger.warning(
            "MicrosoftGraphEmailProvider app-only ativo com remetente=%s <%s> cert=%s...",
            self.from_name,
            self.from_address,
            self.certificate_thumbprint[:8],
        )

    def _get_access_token(self) -> str:
        if self._token and self._token_expires_at > int(time.time()) + 120:
            return self._token

        powershell = os.getenv("POWERSHELL_EXE", "powershell.exe").strip() or "powershell.exe"
        command = [
            powershell,
            "-NoProfile",
            "-NonInteractive",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(self.token_broker),
            "-TenantId",
            self.tenant_id,
            "-ClientId",
            self.client_id,
            "-Thumbprint",
            self.certificate_thumbprint,
        ]
        try:
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=45,
                check=False,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            raise RuntimeError(f"falha ao executar token broker Graph: {exc}") from exc

        if result.returncode != 0:
            detail = (result.stderr or result.stdout or "erro desconhecido").strip()
            if len(detail) > 800:
                detail = detail[-800:]
            raise RuntimeError(f"token broker Graph falhou: {detail}")

        lines = [line.strip() for line in result.stdout.splitlines() if line.strip()]
        if not lines:
            raise RuntimeError("token broker Graph nao retornou JSON")
        try:
            payload = json.loads(lines[-1])
        except json.JSONDecodeError as exc:
            raise RuntimeError("token broker Graph retornou resposta invalida") from exc

        token = str(payload.get("access_token") or "")
        expires_in = int(payload.get("expires_in") or 0)
        if not token or expires_in <= 0:
            raise RuntimeError("token broker Graph nao retornou access_token valido")
        self._token = token
        self._token_expires_at = int(time.time()) + expires_in
        return token

    def authenticate(self) -> None:
        self._get_access_token()

    @staticmethod
    def _parse_retry_after(error: HTTPError) -> int | None:
        value = error.headers.get("Retry-After") if error.headers else None
        if not value:
            return None
        try:
            seconds = int(value)
        except (TypeError, ValueError):
            return None
        return max(seconds, 0)

    def send(self, to: str, subject: str, body: str) -> SendResult:
        content_type = "HTML" if _body_is_html(body) else "Text"
        sender_identity = {
            "emailAddress": {
                "address": self.address,
                "name": self.from_name,
            }
        }
        payload = {
            "message": {
                "subject": subject,
                "body": {"contentType": content_type, "content": body},
                "from": sender_identity,
                "sender": sender_identity,
                "toRecipients": [{"emailAddress": {"address": to}}],
            },
            "saveToSentItems": True,
        }
        try:
            access_token = self._get_access_token()
            req = Request(
                f"https://graph.microsoft.com/v1.0/users/{self.address}/sendMail",
                data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Content-Type": "application/json; charset=utf-8",
                },
                method="POST",
            )
            with urlopen(req, timeout=30) as response:
                status_code = int(response.status)
                request_id = response.headers.get("request-id") or response.headers.get("client-request-id")
                if status_code not in {200, 202}:
                    return SendResult(
                        success=False,
                        message_id=request_id,
                        error=f"Microsoft Graph HTTP {status_code}",
                        status="error",
                        status_code=status_code,
                    )
                # sendMail 202 means accepted/submitted to Exchange processing only.
                # It is not positive proof of recipient delivery.
                return SendResult(
                    success=True,
                    message_id=request_id,
                    status="submitted",
                    status_code=status_code,
                )
        except HTTPError as error:
            retry_after = self._parse_retry_after(error)
            try:
                detail = json.loads(error.read().decode("utf-8"))
            except (ValueError, UnicodeDecodeError):
                detail = {}
            graph = detail.get("error", {}) if isinstance(detail, dict) else {}
            graph_error = str(graph.get("code") or f"http_{error.code}")
            graph_message = str(graph.get("message") or "")
            mapped_status = "sender_blocked" if _is_sender_blocked(graph_error, graph_message) else "error"
            compact_message = graph_message.replace("\n", " ").strip()
            if len(compact_message) > 500:
                compact_message = compact_message[:500]
            error_text = f"Microsoft Graph: {graph_error}; http_{error.code}"
            if compact_message:
                error_text += f"; {compact_message}"
            return SendResult(
                success=False,
                error=error_text,
                retry_after_seconds=retry_after,
                status=mapped_status,
                status_code=int(error.code),
            )
        except (RuntimeError, URLError, OSError) as error:
            return SendResult(success=False, error=str(error), status="error")


def get_email_provider(name: str) -> EmailProvider:
    normalized = (name or "").strip().lower()
    if normalized == "dryrun":
        return DryRunEmailProvider()
    if normalized in {"microsoft_graph", "microsoft-oauth", "graph"}:
        return MicrosoftGraphEmailProvider()
    if normalized in {"gmail", "smtp", "microsoft", "outlook", "office365"}:
        raise ValueError("SMTP esta desabilitado neste projeto. Use EMAIL_PROVIDER=microsoft_graph.")
    raise ValueError(f"Provedor de e-mail '{name}' nao reconhecido. Use somente 'dryrun' ou 'microsoft_graph'.")
