from pathlib import Path

from scripts.ndr_guard import (
    contains_sender_blocked_marker,
    extract_email_addresses,
    is_permanent_recipient_ndr,
    looks_like_ndr,
)

ROOT = Path(__file__).resolve().parents[1]


def test_sender_block_markers_detect_async_exchange_restriction():
    for text in (
        "550 5.1.8 Access denied, bad outbound sender AS(42004)",
        "Access denied, bad outbound sender",
        "restricted sender",
        "address was not recognized as a valid sender",
    ):
        assert contains_sender_blocked_marker(text), text


def test_normal_bounce_is_not_misclassified_as_sender_block():
    assert not contains_sender_blocked_marker("550 5.1.1 recipient mailbox does not exist")


def test_permanent_recipient_ndr_classification_is_narrow():
    for text in (
        "550 5.1.1 recipient mailbox does not exist",
        "Address not found for pessoa@example.com",
        "The email account that you tried to reach does not exist",
        "Recipient address rejected: User unknown",
        "Host or domain name not found",
    ):
        assert is_permanent_recipient_ndr(text), text

    assert not is_permanent_recipient_ndr("550 5.7.0 recipient rejected by policy")
    assert not is_permanent_recipient_ndr("554 5.4.14 hop count exceeded")
    assert not is_permanent_recipient_ndr("550 5.1.8 bad outbound sender AS(42004)")


def test_extract_email_addresses_normalizes_and_filters_internal_ledger():
    text = (
        "Failed for Pessoa.Example+tag@Example.COM; sender "
        "naoresponda@dev.shopvivaliz.com.br; ledger quota+abc@invalid.local"
    )
    assert extract_email_addresses(text) == [
        "naoresponda@dev.shopvivaliz.com.br",
        "pessoa.example+tag@example.com",
    ]


def test_ndr_subject_detection():
    assert looks_like_ndr("Undeliverable: campaign")
    assert looks_like_ndr("Não é possível entregar: campaign")
    assert looks_like_ndr("Address not found")
    assert not looks_like_ndr("Contabilidade Melo para MEI")


def test_ndr_guard_service_is_resident_and_fail_safe():
    unit = (ROOT / "deploy" / "systemd" / "mei-mg-email-ndr-guard.service").read_text(encoding="utf-8")
    assert "ExecStart=__PYTHON__ scripts/ndr_guard.py" in unit
    assert "Restart=always" in unit
    assert "/var/lib/mei-mg-email/sender_blocked.pause" in unit


def test_ndr_guard_registers_only_unambiguous_prior_send_hard_bounces():
    source = (ROOT / "scripts" / "ndr_guard.py").read_text(encoding="utf-8")
    assert "register_operational_suppression" in source
    assert "async_ndr_graph_guard" in source
    assert "hard_bounce" in source
    assert "len(matches) != 1" in source
    assert "email_suppressions" in source


def test_installer_moves_pause_state_outside_git_and_enables_guard():
    script = (ROOT / "scripts" / "instalar_monitoramento_vm.sh").read_text(encoding="utf-8")
    assert 'STATE_DIR="/var/lib/mei-mg-email"' in script
    assert "mei-mg-email-ndr-guard.service" in script
    assert "enable --now mei-mg-email-ndr-guard.service" in script
    assert 'ln -s "$STATE_DIR/sender_blocked.pause"' in script
