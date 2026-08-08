from __future__ import annotations

import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))
load_dotenv(BASE_DIR / ".env")

from app.email_provider import MicrosoftGraphEmailProvider
from worker.worker import montar_corpo

# atendimento@shopvivaliz.com.br encaminha para fredmourao@gmail.com e serve
# como caminho de validacao real sem usar Gmail como provedor de envio.
RECIPIENT = os.getenv("TEST_RECIPIENT", "atendimento@shopvivaliz.com.br")
EXPECTED_SENDER = "naoresponda@dev.shopvivaliz.com.br"
EXPECTED_NAME = "Contabilidade Melo"
TEMPLATE_PATH = BASE_DIR / "templates" / "mei-contabilidade-melo.html"


def main() -> None:
    template = TEMPLATE_PATH.read_text(encoding="utf-8")
    body = montar_corpo(
        template,
        {
            "cnpj": "00000000000000",
            "email": RECIPIENT,
            "razao_social": "Equipe ShopVivaliz",
            "nome_fantasia": "ShopVivaliz",
        },
    )
    if "logo-contabilidade-melo-transparente.png" not in body.casefold():
        raise SystemExit("Template de teste sem a logo oficial no rodape.")
    if "R$ 200,00/mês" not in body:
        raise SystemExit("Template de teste nao corresponde ao Plano Basico MEI aprovado.")
    if "Quero falar no WhatsApp" not in body:
        raise SystemExit("Template de teste sem CTA oficial do WhatsApp.")
    if "{{unsubscribe_url}}" in body:
        raise SystemExit("Template de teste saiu com placeholder de descadastro sem renderizar.")

    provider = MicrosoftGraphEmailProvider()
    if provider.address.casefold() != EXPECTED_SENDER:
        raise SystemExit(f"Remetente Graph incorreto: {provider.address}")
    if provider.from_address.casefold() != EXPECTED_SENDER:
        raise SystemExit(f"MAIL_FROM incorreto: {provider.from_address}")
    if provider.from_name != EXPECTED_NAME:
        raise SystemExit(f"Nome de remetente incorreto: {provider.from_name}")

    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%SZ")
    subject = f"VALIDACAO GRAPH CORRIGIDA - Contabilidade Melo - {stamp}"
    result = provider.send(to=RECIPIENT, subject=subject, body=body)
    if not result.success:
        raise SystemExit(f"Falha no envio de teste: status={result.status} erro={result.error}")
    if result.status != "submitted":
        raise SystemExit(f"Graph retornou status inesperado: {result.status!r}")

    print("GRAPH_TEST_SUBMITTED")
    print(f"recipient={RECIPIENT}")
    print(f"sender={EXPECTED_NAME} <{EXPECTED_SENDER}>")
    print(f"subject={subject}")
    print(f"status={result.status}")
    print(f"status_code={result.status_code}")
    print(f"request_id={result.message_id or ''}")


if __name__ == "__main__":
    main()
