from __future__ import annotations

from dotenv import load_dotenv

load_dotenv()

import os

from app.email_provider import MicrosoftGraphEmailProvider


RECIPIENT = os.getenv("TEST_RECIPIENT", "fredmourao@gmail.com")


def main() -> None:
    provider = MicrosoftGraphEmailProvider()
    result = provider.send(
        to=RECIPIENT,
        subject="Teste OAuth - Contabilidade Melo",
        body=(
            "<!doctype html><html><body>"
            "<h1>Teste de envio OAuth</h1>"
            "<p>Mensagem de teste da Contabilidade Melo enviada pelo Microsoft Graph.</p>"
            "</body></html>"
        ),
    )
    if not result.success:
        raise SystemExit(f"Falha no envio de teste: {result.error}")
    print(f"Envio de teste aceito pelo Microsoft Graph para {RECIPIENT}.")


if __name__ == "__main__":
    main()


