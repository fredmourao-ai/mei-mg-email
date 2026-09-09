from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT / "app" / "email_provider.py").read_text(encoding="utf-8")


def test_active_provider_documentation_is_brevo_only():
    header = SOURCE.split("from __future__", 1)[0]
    assert "Brevo" in header
    assert "Production delivery is restricted to Microsoft Graph" not in header


def test_legacy_graph_thumbprint_marks_sha1_as_non_security_identifier():
    assert "hashlib.sha1(der, usedforsecurity=False)" in SOURCE
    assert 'OPENSSL_BIN = "/usr/bin/openssl"' in SOURCE
    assert '[OPENSSL_BIN, "x509"' in SOURCE
    assert '[OPENSSL_BIN, "dgst"' in SOURCE


def test_graph_provider_remains_fail_closed_for_runtime_selection():
    tail = SOURCE.split("def get_email_provider", 1)[1]
    assert "production uses Brevo only" in tail
    assert "MicrosoftGraphEmailProvider()" not in tail
