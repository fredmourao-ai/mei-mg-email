from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT / "scripts" / "autocorrigir_envios_hourly.py").read_text(
    encoding="utf-8"
)


def test_hourly_wrapper_delegates_only_to_canonical_fail_closed_repair():
    assert "return core.execute(apply=True)" in SOURCE
    assert "recuperar_sender_block_sentinel.py" not in SOURCE
    assert "_attempt_verified_stale_sender_recovery" not in SOURCE
    assert "send a probe message" in SOURCE


def test_hourly_wrapper_never_mutates_sender_block_sentinel():
    assert "unlink(" not in SOURCE
    assert "remove(" not in SOURCE
    assert "ConfirmUnblock" not in SOURCE
    assert "SENDER_BLOCK_RECOVERY_VERIFIED=true" not in SOURCE
