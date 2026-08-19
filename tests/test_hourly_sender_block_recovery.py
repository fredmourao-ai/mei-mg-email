from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT / "scripts" / "autocorrigir_envios_hourly.py").read_text(
    encoding="utf-8"
)


def test_hourly_guard_invokes_verified_sender_recovery_before_queue_lock():
    assert "_attempt_verified_stale_sender_recovery()" in SOURCE
    assert "recuperar_sender_block_sentinel.py" in SOURCE
    assert SOURCE.index("_attempt_verified_stale_sender_recovery()") < SOURCE.index(
        "with core._repair_lock():"
    )


def test_hourly_guard_requires_positive_live_proof_marker():
    assert "SENDER_BLOCK_RECOVERY_VERIFIED=true" in SOURCE
    assert "sentinel remains active" in SOURCE
    assert "keeping fail-closed sentinel" in SOURCE


def test_hourly_guard_never_deletes_sender_block_sentinel_directly():
    assert "unlink(" not in SOURCE
    assert "remove(" not in SOURCE
    assert "ConfirmUnblock" not in SOURCE
