"""
Abstracao de provedor de e-mail.

O padrao continua sendo DryRunEmailProvider para evitar disparos reais por
engano. Para envio real, configure EMAIL_PROVIDER=microsoft_graph ou
EMAIL_PROVIDER=microsoft e defina as credenciais correspondentes no .env.

Personalizacao (mail-merge): o corpo do e-mail e montado por
worker.worker.montar_corpo() antes de chegar em EmailProvider.send().
"""
from __future__ import annotations

import json
import logging
import os
import smtplib
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

logger = logging.getLogger("mei_mg_email.email_provider")


@dataclass
class SendResult:
    success: bool
    message_id: str | None = None
    error: str | None = None
    retry_after_seconds: int | None = None


class EmailProvider(ABC):
    @abstractmethod
    def send(self, to: str, subject: str, body: str) -> SendResult:
        """Envia um e-mail e retorna o resultado."""
        raise NotImplementedError


class DryRunEmailProvider(EmailProvider):
    """Nao envia nada de verdade. Loga o que enviaria."""

    def send(self, to: str, subject: str, body: str) -> SendResult:
        fake_id = f"dryrun-{int(time.time() * 1000)}"
        logger.info(
            "DRY-RUN: enviaria e-mail para=%s assunto=%r corpo(%d chars) id=%s",
            to,
            subject,
            len(body),
            fake_id,
        )
        return SendResult(success=True, message_id=fake_id)


def _body_is_html(body: str) -> bool:
    body_lower = body.strip().lower()
    return body_lower.startswith("<!doctype html") or body_lower.startswith("<html") or "<body" in body_lower


def _html_to_plain_text(html: str) -> str:
    text = html
    replacements = {
        "<br>": "\n",
        "<br/>": "\n",
        "<br />": "\n",
        "</p>": "\n\n",
        "</div>": "\n",
        "</li>": "\n",
    }
    for old, new in replacements.items():
        text = text.replace(old, new).replace(old.upper(), new)
    import re

    text = re.sub(r"<[^>]+>", "", text)
    text = text.replace("&nbsp;", " ").replace("&amp;", "&")
    text = text.replace("&lt;", "<").replace("&gt;", ">")
    return "\n".join(line.strip() for line in text.splitlines() if line.strip())


def _build_message(from_address: str, to: str, subject: str, body: str):
    if _body_is_html(body):
        msg = MIMEMultipart("alternative")
        msg.attach(MIMEText(_html_to_plain_text(body), "plain", "utf-8"))
        msg.attach(MIMEText(body, "html", "utf-8"))
    else:
        msg = MIMEText(body, "plain", "utf-8")

    msg["Subject"] = subject
    msg["From"] = from_address
    msg["To"] = to
    return msg


class GmailEmailProvider(EmailProvider):
    """Envia via Gmail SMTP usando App Password."""

    def __init__(self) -> None:
        self.address = os.getenv("GMAIL_ADDRESS", "").strip()
        self.app_password = os.getenv("GMAIL_APP_PASSWORD", "").strip()
        if not self.address or not self.app_password:
            raise RuntimeError(
                "EMAIL_PROVIDER=gmail mas GMAIL_ADDRESS/GMAIL_APP_PASSWORD nao estao configurados."
            )
        logger.warning("GmailEmailProvider ativo com remetente=%s", self.address)

    def send(self, to: str, subject: str, body: str) -> SendResult:
        msg = _build_message(self.address, to, subject, body)

        try:
            with smtplib.SMTP("smtp.gmail.com", 587, timeout=20) as smtp:
                smtp.starttls()
                smtp.login(self.address, self.app_password)
                smtp.sendmail(self.address, [to], msg.as_string())
            return SendResult(success=True, message_id=None)
        except smtplib.SMTPAuthenticationError as e:
            logger.error("Falha de autenticacao no Gmail SMTP: %s", e)
            return SendResult(success=False, error=f"falha de autenticacao SMTP: {e}")
        except (smtplib.SMTPException, OSError) as e:
            return SendResult(success=False, error=str(e))


class MicrosoftSmtpEmailProvider(EmailProvider):
    """Envia via Microsoft/Outlook SMTP com STARTTLS."""

    def __init__(self) -> None:
        self.address = os.getenv("MICROSOFT_SMTP_USER", "").strip()
        self.password = os.getenv("MICROSOFT_SMTP_PASS", "").strip()
        self.host = os.getenv("MICROSOFT_SMTP_HOST", "smtp.office365.com").strip()
        self.port = int(os.getenv("MICROSOFT_SMTP_PORT", "587"))
        self.from_address = os.getenv("MAIL_FROM", self.address).strip() or self.address

        if not self.address or not self.password:
            raise RuntimeError(
                "EMAIL_PROVIDER=microsoft mas MICROSOFT_SMTP_USER/MICROSOFT_SMTP_PASS nao estao configurados."
            )
        logger.warning(
            "MicrosoftSmtpEmailProvider ativo com remetente=%s host=%s:%s",
            self.from_address,
            self.host,
            self.port,
        )

    def send(self, to: str, subject: str, body: str) -> SendResult:
        msg = _build_message(self.from_address, to, subject, body)

        try:
            with smtplib.SMTP(self.host, self.port, timeout=20) as smtp:
                smtp.starttls()
                smtp.login(self.address, self.password)
                smtp.sendmail(self.address, [to], msg.as_string())
            return SendResult(success=True, message_id=None)
        except smtplib.SMTPAuthenticationError as e:
            logger.error("Falha de autenticacao no Microsoft SMTP: %s", e)
            return SendResult(success=False, error=f"falha de autenticacao SMTP Microsoft: {e}")
        except (smtplib.SMTPException, OSError) as e:
            return SendResult(success=False, error=str(e))


class MicrosoftGraphEmailProvider(EmailProvider):
    """Envia por Microsoft Graph usando OAuth2 delegado, sem segredo local."""

    _scope = "offline_access User.Read Mail.Send"

    def __init__(self) -> None:
        self.tenant_id = os.getenv("MICROSOFT_GRAPH_TENANT_ID", "").strip()
        self.client_id = os.getenv("MICROSOFT_GRAPH_CLIENT_ID", "").strip()
        self.address = os.getenv(
            "MICROSOFT_GRAPH_USER",
            os.getenv("MICROSOFT_SMTP_USER", ""),
        ).strip()
        self.from_address = os.getenv("MAIL_FROM", self.address).strip() or self.address
        cache_default_root = Path(os.getenv("LOCALAPPDATA") or Path.home() / ".cache")
        configured_cache = os.getenv("MICROSOFT_GRAPH_TOKEN_CACHE", "").strip()
        self.cache_path = Path(configured_cache) if configured_cache else (
            cache_default_root / "mei-mg-email" / "microsoft-graph-token.json"
        )

        if not self.tenant_id or not self.client_id or not self.address:
            raise RuntimeError(
                "EMAIL_PROVIDER=microsoft_graph exige "
                "MICROSOFT_GRAPH_TENANT_ID/MICROSOFT_GRAPH_CLIENT_ID/"
                "MICROSOFT_GRAPH_USER."
            )

        self._token: str | None = None
        logger.warning(
            "MicrosoftGraphEmailProvider ativo com remetente=%s",
            self.from_address,
        )

    @property
    def _authority(self) -> str:
        return f"https://login.microsoftonline.com/{self.tenant_id}"

    def _post_form(self, url: str, values: dict[str, str]) -> dict:
        req = Request(
            url,
            data=urlencode(values).encode("utf-8"),
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            method="POST",
        )
        try:
            with urlopen(req, timeout=30) as response:
                return json.loads(response.read().decode("utf-8"))
        except HTTPError as error:
            try:
                detail = json.loads(error.read().decode("utf-8"))
            except (ValueError, UnicodeDecodeError):
                detail = {}
            code = detail.get("error", f"http_{error.code}")
            description = detail.get("error_description", "falha OAuth Microsoft")
            raise RuntimeError(f"OAuth Microsoft: {code}: {description}") from error
        except URLError as error:
            raise RuntimeError(f"OAuth Microsoft indisponivel: {error.reason}") from error

    def _load_cache(self) -> dict:
        try:
            return json.loads(self.cache_path.read_text(encoding="utf-8"))
        except (FileNotFoundError, OSError, ValueError):
            return {}

    def _save_cache(self, token_data: dict) -> None:
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        temporary_path = self.cache_path.with_suffix(self.cache_path.suffix + ".tmp")
        temporary_path.write_text(
            json.dumps(token_data, ensure_ascii=False),
            encoding="utf-8",
        )
        os.replace(temporary_path, self.cache_path)

    def _store_token(self, response: dict, previous: dict | None = None) -> str:
        token_data = dict(previous or {})
        token_data["access_token"] = response["access_token"]
        token_data["expires_at"] = int(time.time()) + int(response.get("expires_in", 3600))
        if response.get("refresh_token"):
            token_data["refresh_token"] = response["refresh_token"]
        self._save_cache(token_data)
        self._token = token_data["access_token"]
        return self._token

    def _device_login(self) -> str:
        device = self._post_form(
            f"{self._authority}/oauth2/v2.0/devicecode",
            {"client_id": self.client_id, "scope": self._scope},
        )
        message = device.get("message")
        if message:
            print(message, flush=True)

        deadline = time.time() + int(device.get("expires_in", 900))
        interval = max(int(device.get("interval", 5)), 2)
        while time.time() < deadline:
            time.sleep(interval)
            try:
                response = self._post_form(
                    f"{self._authority}/oauth2/v2.0/token",
                    {
                        "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
                        "client_id": self.client_id,
                        "device_code": device["device_code"],
                    },
                )
            except RuntimeError as error:
                if "authorization_pending" in str(error):
                    continue
                raise
            return self._store_token(response)
        raise RuntimeError("OAuth Microsoft expirou antes da autorizacao do dispositivo.")

    def _get_access_token(self) -> str:
        if self._token:
            return self._token

        cache = self._load_cache()
        if cache.get("access_token") and int(cache.get("expires_at", 0)) > int(time.time()) + 60:
            self._token = cache["access_token"]
            return self._token

        if cache.get("refresh_token"):
            try:
                response = self._post_form(
                    f"{self._authority}/oauth2/v2.0/token",
                    {
                        "grant_type": "refresh_token",
                        "client_id": self.client_id,
                        "scope": self._scope,
                        "refresh_token": cache["refresh_token"],
                    },
                )
                return self._store_token(response, previous=cache)
            except RuntimeError as error:
                if "invalid_grant" not in str(error):
                    raise

        return self._device_login()

    def authenticate(self) -> None:
        """Completa o login OAuth e salva somente o cache local do token."""
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
        payload = {
            "message": {
                "subject": subject,
                "body": {"contentType": content_type, "content": body},
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
                    "Content-Type": "application/json",
                },
                method="POST",
            )
            with urlopen(req, timeout=30) as response:
                if response.status not in {200, 202}:
                    return SendResult(success=False, error=f"Microsoft Graph HTTP {response.status}")
            return SendResult(success=True, message_id=None)
        except HTTPError as error:
            retry_after = self._parse_retry_after(error)
            try:
                detail = json.loads(error.read().decode("utf-8"))
            except (ValueError, UnicodeDecodeError):
                detail = {}
            graph_error = detail.get("error", {}).get("code", f"http_{error.code}")
            return SendResult(
                success=False,
                error=f"Microsoft Graph: {graph_error}; http_{error.code}",
                retry_after_seconds=retry_after,
            )
        except (RuntimeError, URLError, OSError) as error:
            return SendResult(success=False, error=str(error))


def get_email_provider(name: str) -> EmailProvider:
    if name == "dryrun":
        return DryRunEmailProvider()
    if name == "gmail":
        return GmailEmailProvider()
    if name in {"microsoft_graph", "microsoft-oauth", "graph"}:
        return MicrosoftGraphEmailProvider()
    if name in {"microsoft", "outlook", "office365"}:
        return MicrosoftSmtpEmailProvider()
    raise ValueError(
        f"Provedor de e-mail '{name}' nao reconhecido. Use 'dryrun', 'gmail', 'microsoft_graph' ou 'microsoft'."
    )
