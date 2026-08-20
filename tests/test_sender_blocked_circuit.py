from pathlib import Path

from app.email_provider import _is_sender_blocked

ROOT = Path(__file__).resolve().parents[1]


def test_worker_has_persistent_sender_block_circuit():
    worker = (ROOT / "worker" / "worker.py").read_text(encoding="utf-8").casefold()
    assert "sender_block_sentinel" in worker
    assert "sender_blocked.pause" in worker
    assert "_registrar_sender_blocked_pause" in worker
    assert "_sender_blocked_pause_ativo" in worker
    assert "nenhum novo envio sera tentado" in worker


def test_current_incident_pause_is_runtime_state_not_git_state():
    assert not (ROOT / "runtime" / "sender_blocked.pause").exists()

    incident = (ROOT / "ops" / "incidents" / "2026-08-13-AS42004.md").read_text(
        encoding="utf-8"
    ).casefold()
    assert "naoresponda@dev.shopvivaliz.com.br" in incident
    assert "5.1.8" in incident
    assert "42004" in incident

    deploy = (ROOT / "scripts" / "deploy_hardening_20260813.sh").read_text(
        encoding="utf-8"
    ).casefold()
    assert 'state_dir="/var/lib/mei-mg-email"' in deploy
    assert 'sentinel="$state_dir/sender_blocked.pause"' in deploy
    assert "deploy_worker_stopped=true" in deploy
    assert "worker_resume_allowed=false" in deploy


def test_sender_blocked_classifier_only_matches_microsoft_sender_restriction():
    blocking_cases = [
        ("ErrorInvalidRecipients", "Remote server returned '550 5.1.8 Bad outbound sender AS(42004)'."),
        ("ErrorSendAsDenied", "The sender is a restricted sender and cannot send outbound mail."),
        ("Error", "bad outbound sender detected by Microsoft Exchange"),
    ]
    for code, message in blocking_cases:
        assert _is_sender_blocked(code, message)


def test_sender_blocked_classifier_does_not_stop_for_repairable_or_recipient_failures():
    non_blocking_cases = [
        ("MailboxNotFound", "Recipient mailbox does not exist."),
        ("ErrorInvalidRecipients", "The recipient address is invalid."),
        ("TooManyRequests", "Rate limit exceeded; retry later."),
        ("ServiceUnavailable", "Temporary Microsoft Graph failure."),
        ("RequestTimeout", "The request timed out."),
        ("DomainNotFound", "Recipient domain does not exist."),
        ("ErrorMessageSizeExceeded", "Message exceeds recipient limits."),
    ]
    for code, message in non_blocking_cases:
        assert not _is_sender_blocked(code, message)
