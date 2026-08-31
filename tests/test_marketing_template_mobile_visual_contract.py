from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "templates" / "mei-contabilidade-melo.html"


def _html() -> str:
    return TEMPLATE.read_text(encoding="utf-8")


def test_mobile_layout_is_single_column_and_compact():
    html = _html()
    assert 'width="48%"' not in html
    assert 'width="4%"' not in html
    assert "max-width:640px" in html
    assert "font-size:32px" in html


def test_primary_cta_appears_before_secondary_simples_block():
    html = _html()
    cta = html.index("Falar com a Contabilidade Melo")
    simples = html.index("Sua empresa é do Simples Nacional?")
    assert cta < simples


def test_email_keeps_accessible_images_and_full_width_cta():
    html = _html()
    assert 'alt="Contabilidade Melo"' in html
    assert "width:100%;" in html
    assert "min-height:48px" in html
