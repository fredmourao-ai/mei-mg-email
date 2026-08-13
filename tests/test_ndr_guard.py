from pathlib import Path

from scripts.ndr_guard import contains_sender_blocked_marker, looks_like_ndr

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


def test_ndr_subject_detection():
    assert looks_like_ndr("Undeliverable: campaign")
    assert looks_like_ndr("Não é possível entregar: campaign")
    assert not looks_like_ndr("Contabilidade Melo para MEI")


def test_ndr_guard_service_is_resident_and_fail_safe():
    unit = (ROOT / "deploy" / "systemd" / "mei-mg-email-ndr-guard.service").read_text(encoding="utf-8")
    assert "ExecStart=__PYTHON__ scripts/ndr_guard.py" in unit
    assert "Restart=always" in unit
    assert "/var/lib/mei-mg-email/sender_blocked.pause" in unit


def test_installer_moves_pause_state_outside_git_and_enables_guard():
    script = (ROOT / "scripts" / "instalar_monitoramento_vm.sh").read_text(encoding="utf-8")
    assert 'STATE_DIR="/var/lib/mei-mg-email"' in script
    assert "mei-mg-email-ndr-guard.service" in script
    assert "enable --now mei-mg-email-ndr-guard.service" in script
    assert 'ln -s "$STATE_DIR/sender_blocked.pause"' in script
