from __future__ import annotations

import base64
from email import message_from_bytes
from email.policy import default

from app.email_provider import MicrosoftGraphEmailProvider, _extract_unsubscribe_url


def test_extract_unsubscribe_url_from_marketing_html() -> None:
    body = '<html><body><a href="https://dev.shopvivaliz.com.br/descadastro?email=x%40y.com">descadastrar</a></body></html>'
    assert _extract_unsubscribe_url(body) == "https://dev.shopvivaliz.com.br/descadastro?email=x%40y.com"


def test_rfc8058_headers_are_emitted() -> None:
    provider = MicrosoftGraphEmailProvider.__new__(MicrosoftGraphEmailProvider)
    provider.from_name = "Contabilidade Melo"
    provider.address = "naoresponda@dev.shopvivaliz.com.br"
    url = "https://dev.shopvivaliz.com.br/descadastro?email=fredmourao%40gmail.com"
    encoded = provider._mime_payload(
        "fredmourao@gmail.com",
        "Teste RFC8058",
        '<html><body>Teste <a href="%s">descadastrar</a></body></html>' % url,
        url,
    )
    msg = message_from_bytes(base64.b64decode(encoded), policy=default)
    assert msg["List-Unsubscribe"] == f"<{url}>"
    assert msg["List-Unsubscribe-Post"] == "List-Unsubscribe=One-Click"
    assert msg["From"] == "Contabilidade Melo <naoresponda@dev.shopvivaliz.com.br>"
    assert msg["To"] == "fredmourao@gmail.com"
    assert msg.is_multipart()
