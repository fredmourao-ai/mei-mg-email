from __future__ import annotations

import os
import sys
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))
load_dotenv(BASE_DIR / ".env")

from app.email_provider import MicrosoftGraphEmailProvider
from worker.worker import montar_corpo

RECIPIENT = os.getenv("TEST_RECIPIENT", "fredmourao@gmail.com")
TEMPLATE_PATH = BASE_DIR / "templates" / "mei-contabilidade-melo.html"


def main() -> None:
    template = TEMPLATE_PATH.read_text(encoding="utf-8")
    body = montar_corpo(
        template,
        {
            "cnpj": "00000000000000",
            "email": RECIPIENT,
            "razao_social": "Empresa de Teste",
            "nome_fantasia": "Teste Contabilidade Melo",
        },
    )
    if "logo-contabilidade-melo-transparente.png" not in body.casefold():
        raise SystemExit("Template de teste sem a logo oficial no rodape.")

    provider = MicrosoftGraphEmailProvider()
    result = provider.send(
        to=RECIPIENT,
        subject="Teste do template HTML - Contabilidade Melo",
        body=body,
    )
    if not result.success:
        raise SystemExit(f"Falha no envio de teste: {result.error}")
    print(f"Template HTML oficial aceito pelo Microsoft Graph para {RECIPIENT}.")


if __name__ == "__main__":
    main()
