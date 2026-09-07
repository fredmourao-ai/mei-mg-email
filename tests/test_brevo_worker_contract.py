from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
QUEUE_SOURCE = (ROOT / "worker" / "worker_queue_first.py").read_text(encoding="utf-8")
BASE_SOURCE = (ROOT / "worker" / "worker.py").read_text(encoding="utf-8")


def test_quota_counts_only_brevo_submission_evidence():
    source = QUEUE_SOURCE.casefold()
    assert "provider_message_id like 'brevo:%'" in source
    assert "submitted_at >= statement_timestamp() - interval '24 hours'" in source
    assert "source like 'brevo%'" in source or "provider_message_id like 'brevo:%'" in source


def test_replay_guard_uses_durable_submission_evidence_across_final_statuses():
    source = QUEUE_SOURCE.casefold()
    assert "provider_message_id is not null" in source
    assert "submitted_at is not null" in source
    assert "lower(btrim(email::text)) = lower(btrim(%s))" in source


def test_brevo_worker_hard_fails_if_effective_cap_exceeds_300():
    source = QUEUE_SOURCE.casefold()
    assert "brevo" in source
    assert "max_envios_por_dia > 300" in source


def test_dispatch_and_pause_messages_are_provider_neutral():
    source = QUEUE_SOURCE
    forbidden = (
        "aguardando resultado do Microsoft Graph",
        "status Graph inesperado apos sendMail",
        "recuperacao verificada no Exchange",
    )
    for marker in forbidden:
        assert marker not in source


def test_base_worker_keeps_replay_evidence_after_delivery_or_bounce():
    source = BASE_SOURCE.casefold()
    assert "provider_message_id is not null" in source
    assert "submitted_at is not null" in source
