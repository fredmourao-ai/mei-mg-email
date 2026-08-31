from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "templates" / "mei-contabilidade-melo.html"


def test_new_mei_template_keeps_deliverability_contract():
    html = TEMPLATE.read_text(encoding="utf-8")
    required = (
        "Seu MEI em dia",
        "R$ 200,00/mês",
        "Certificado digital incluído",
        "Até 10 notas fiscais por mês",
        "DASN-SIMEI",
        "Atendimento ágil e humanizado",
        "https://wa.me/5537996704011",
        "{{unsubscribe_url}}",
        "Contabilidade Melo",
        "Sua empresa é do Simples Nacional?",
        "fiscalmelo@hotmail.com",
        "logo-contabilidade-melo-transparente.png",
    )
    for token in required:
        assert token in html
    assert "<script" not in html.lower()
    assert "data:image" not in html.lower()
    assert len(html.encode("utf-8")) < 100_000
