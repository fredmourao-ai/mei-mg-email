import base64
from email import policy
from email.parser import BytesParser

from app.email_provider import MicrosoftGraphEmailProvider, _one_click_unsubscribe_url


def test_marketing_mime_sets_reply_to_fiscalmelo():
    provider = object.__new__(MicrosoftGraphEmailProvider)
    provider.from_name = "Contabilidade Melo"
    provider.address = "naoresponda@dev.shopvivaliz.com.br"
    raw_b64 = provider._mime_payload(
        "cliente@example.com", "Assunto",
        '<a href="https://example.com/descadastro?email=x">descadastro</a>',
        "https://example.com/descadastro?email=x",
    )
    msg = BytesParser(policy=policy.default).parsebytes(base64.b64decode(raw_b64))
    assert msg["Reply-To"] == "fiscalmelo@hotmail.com"
    assert "/descadastro/one-click?" in msg["List-Unsubscribe"]
    assert msg["List-Unsubscribe-Post"] == "List-Unsubscribe=One-Click"


def test_one_click_url_preserves_query():
    url = _one_click_unsubscribe_url("https://example.com/descadastro?email=a%40b.com")
    assert url == "https://example.com/descadastro/one-click?email=a%40b.com"
