"""
Abstração de provedor de e-mail.

Provedor escolhido: Gmail via SMTP (smtp.gmail.com:587, STARTTLS, App
Password). DryRunEmailProvider continua sendo o PADRÃO em .env.example --
trocar pra 'gmail' é decisão explícita do Fred (EMAIL_PROVIDER=gmail no
.env), e o envio real só acontece se GMAIL_ADDRESS/GMAIL_APP_PASSWORD
estiverem configurados. Esta classe nunca gera nem tenta adivinhar a senha
-- ela só lê de variável de ambiente, e falha alto (erro na inicialização,
não silencioso) se estiver faltando.

Personalização (mail-merge): o corpo do e-mail é montado por
worker.worker.montar_corpo() ANTES de chegar em EmailProvider.send() --
troca {{razao_social}}, {{nome_fantasia}}, {{municipio}}, {{cnpj}} e
{{unsubscribe_url}} pelos dados de cada empresa. O EmailProvider só recebe
o texto já pronto, não sabe nada sobre merge -- então qualquer provedor
novo (SendGrid, SES...) ganha personalização de graça, sem reimplementar.
"""
from __future__ import annotations

import logging
import os
import smtplib
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
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
        """Envia um e-mail e retorna o resultado. Nunca deve lançar exceção
        por falha de envio esperada (timeout, bounce, etc.) — deve retornar
        SendResult(success=False, error=...) pro worker registrar e seguir."""
        raise NotImplementedError


class DryRunEmailProvider(EmailProvider):
    """Não envia nada de verdade. Loga o que enviaria e retorna sucesso
    simulado, com um id fake, pra permitir testar toda a esteira (API ->
    fila -> lotes -> worker -> envios) sem precisar de credencial de
    provedor real nem risco de mandar e-mail de verdade sem querer."""

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


class GmailEmailProvider(EmailProvider):
    """Envia via Gmail SMTP (smtp.gmail.com:587, STARTTLS) usando uma App
    Password -- NAO a senha normal da conta (Gmail exige 2FA habilitado +
    senha de app gerada em myaccount.google.com/apppasswords).

    Le GMAIL_ADDRESS e GMAIL_APP_PASSWORD do ambiente. Nunca gera, nunca
    tenta adivinhar, nunca loga a senha. Se faltar qualquer uma, levanta
    erro na hora de construir (falha alta, antes de qualquer tentativa de
    envio), pra nao mascarar configuracao incompleta como "0 falhas"."""

    def __init__(self) -> None:
        self.address = os.getenv("GMAIL_ADDRESS", "").strip()
        self.app_password = os.getenv("GMAIL_APP_PASSWORD", "").strip()
        if not self.address or not self.app_password:
            raise RuntimeError(
                "EMAIL_PROVIDER=gmail mas GMAIL_ADDRESS/GMAIL_APP_PASSWORD "
                "nao estao configurados no ambiente. Gere uma App Password "
                "em https://myaccount.google.com/apppasswords (exige 2FA "
                "ativado na conta) e defina as duas variaveis no .env -- "
                "esta classe nunca gera isso sozinha."
            )
        logger.warning(
            "GmailEmailProvider ativo com remetente=%s -- ISSO ENVIA E-MAIL "
            "DE VERDADE. Confirme que essa e a intencao antes de rodar o "
            "worker com EMAIL_PROVIDER=gmail.",
            self.address,
        )

    def send(self, to: str, subject: str, body: str) -> SendResult:
        msg = MIMEText(body, "plain", "utf-8")
        msg["Subject"] = subject
        msg["From"] = self.address
        msg["To"] = to

        try:
            with smtplib.SMTP("smtp.gmail.com", 587, timeout=20) as smtp:
                smtp.starttls()
                smtp.login(self.address, self.app_password)
                smtp.sendmail(self.address, [to], msg.as_string())
            return SendResult(success=True, message_id=None)
        except smtplib.SMTPRecipientsRefused as e:
            return SendResult(success=False, error=f"destinatario recusado: {e}")
        except smtplib.SMTPAuthenticationError as e:
            # Erro de config (App Password errada/expirada), nao do envio em
            # si -- vale distinguir no log pra nao confundir com bounce.
            logger.error("Falha de autenticacao no Gmail SMTP: %s", e)
            return SendResult(success=False, error=f"falha de autenticacao SMTP: {e}")
        except (smtplib.SMTPException, OSError) as e:
            return SendResult(success=False, error=str(e))


def get_email_provider(name: str) -> EmailProvider:
    if name == "dryrun":
        return DryRunEmailProvider()
    if name == "gmail":
        return GmailEmailProvider()
    raise ValueError(
        f"Provedor de e-mail '{name}' nao reconhecido. "
        f"Use 'dryrun' ou 'gmail' -- ver app/email_provider.py."
    )
