from app.email_provider import _is_valid_recipient_address


def test_accepts_normal_ascii_business_address():
    assert _is_valid_recipient_address("financeiro@empresa.com.br")


def test_rejects_common_malformed_addresses():
    invalid = (
        "nome..sobrenome@empresa.com",
        "nome @empresa.com",
        "nome@@empresa.com",
        "nome@empresa",
        "nome@-empresa.com",
        "nome@empresa-.com",
    )
    assert all(not _is_valid_recipient_address(value) for value in invalid)


def test_rejects_dns_label_longer_than_63_octets():
    address = "nome@" + ("a" * 64) + ".com"
    assert not _is_valid_recipient_address(address)


def test_rejects_obvious_provider_domain_typos():
    typo_domains = (
        "ahoo.com.br", "gmai.com", "gamail.com", "gamil.com", "gmaial.com",
        "gmail.co2", "gmail.comma", "gmail.comm", "gmail.ocm", "gmail.om",
        "gmaill.com", "gmial.com", "gmil.com", "homail.com", "hootmail.com",
        "hotamail.com", "hotamil.com", "hotimail.com", "hotmai.com",
        "hotmail.com11", "hotmail.om", "hotmailc.om", "hotmal.com",
        "hotmial.com", "hotmil.com", "hottmail.com", "htmail.com",
        "jahoo.com.br", "otmail.com", "oultlook.com", "outlouk.com",
        "outook.com", "yaahoo.com.br", "yahho.com.br", "yahoo.bom.br",
        "yahoo.cm.br", "yahoo.combr", "yahoo.con.br", "yahoocom.br",
        "yahool.com.br", "yaoo.com.br", "yhaoo.com.br", "yhoo.com.br",
        "yashoo.com.br", "yshoo.com.br",
    )
    invalid = tuple(f"owner@{domain}" for domain in typo_domains)
    assert all(not _is_valid_recipient_address(value) for value in invalid)


def test_keeps_legitimate_provider_domains_allowed():
    valid = (
        "owner@gmail.com",
        "owner@hotmail.com",
        "owner@yahoo.com.br",
        "owner@outlook.com",
        "owner@ig.com.br",
        "owner@bol.com.br",
    )
    assert all(_is_valid_recipient_address(value) for value in valid)
