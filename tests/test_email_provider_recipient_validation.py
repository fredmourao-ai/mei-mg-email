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
