from scripts import ndr_guard as guard
from scripts import ndr_guard_v2  # noqa: F401  -- installs retention-aware markers


def test_google_inactive_account_is_individual_permanent_recipient_failure():
    text = (
        "Remote server returned '550-5.2.1 The email account that you tried "
        "to reach is inactive. For more information see DisabledUser'"
    )
    assert guard.is_permanent_recipient_ndr(text)
    assert not guard.contains_sender_blocked_marker(text)


def test_mailbox_full_remains_transient_not_hard_bounce():
    assert not guard.is_permanent_recipient_ndr(
        "554 5.2.2 mailbox full QuotaExceededException; try again later"
    )
