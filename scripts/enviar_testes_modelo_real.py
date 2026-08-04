from __future__ import annotations

import os
from pathlib import Path
from urllib.parse import urlencode

from dotenv import load_dotenv

from app.email_provider import MicrosoftGraphEmailProvider


load_dotenv()

TEMPLATE_PATH = Path(__file__).resolve().parents[1] / "templates" / "mei-contabilidade-melo.html"
SUBJECT = "MEI: Ganhe Certificado Digital + 10 Notas Fiscais por mes"
RECIPIENTS = {
    "atendimento@shopvivaliz.com.br": "Equipe ShopVivaliz",
}


def render(template: str, recipient: str, name: str) -> str:
    base_url = os.environ["BASE_URL_DESCADASTRO"].rstrip("?")
    unsubscribe_url = f"{base_url}?{urlencode({'email': recipient})}"
    return (
        template.replace("{{nome_fantasia}}", name)
        .replace("{{unsubscribe_url}}", unsubscribe_url)
    )


def main() -> None:
    template = TEMPLATE_PATH.read_text(encoding="utf-8")
    provider = MicrosoftGraphEmailProvider()
    failures: list[str] = []

    for recipient, name in RECIPIENTS.items():
        result = provider.send(
            to=recipient,
            subject=SUBJECT,
            body=render(template, recipient, name),
        )
        if result.success:
            print(f"Aceito pelo Microsoft Graph: {recipient}")
        else:
            failures.append(f"{recipient}: {result.error}")

    if failures:
        raise SystemExit("Falha no envio de teste: " + "; ".join(failures))


if __name__ == "__main__":
    main()
