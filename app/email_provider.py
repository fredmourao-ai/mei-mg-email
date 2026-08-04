"""
Abstracao de provedor de e-mail.

O padrao continua sendo DryRunEmailProvider para evitar disparos reais por
engano. Para envio real, configure EMAIL_PROVIDER=microsoft ou gmail e defina
as credenciais correspondentes no .env.

Personalizacao (mail-merge): o corpo do e-mail e montado por
worker.worker.montar_corpo() antes de chegar em EmailProvider.send().
"""
from __future__ import annotations

import logging
import os
import smtplib
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

logger = logging.getLogger("mei_mg_email.email_provider")


@dataclass
class SendResult:
    success: bool
    message_id: str | None = None
    error: str | None = None


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
    """Envia via Microsoft/Outlook SMTP com STARTTLS.

    Para Microsoft 365/Exchange Online, o host mais comum e smtp.office365.com:587.
    Para contas Outlook.com, a Microsoft tambem documenta smtp-mail.outlook.com:587.
    O host e configuravel por MICROSOFT_SMTP_HOST.
    """

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


def get_email_provider(name: str) -> EmailProvider:
    if name == "dryrun":
        return DryRunEmailProvider()
    if name == "gmail":
        return GmailEmailProvider()
    if name in {"microsoft", "outlook", "office365"}:
        return MicrosoftSmtpEmailProvider()
    raise ValueError(
        f"Provedor de e-mail '{name}' nao reconhecido. Use 'dryrun', 'gmail' ou 'microsoft'."
    )
