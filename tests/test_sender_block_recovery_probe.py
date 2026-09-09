from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT / "scripts" / "recuperar_sender_block_sentinel.py").read_text(
    encoding="utf-8"
)


def test_retired_recovery_is_fail_closed_tombstone():
    assert "RETIRED_AUTOMATIC_SENDER_RECOVERY=true" in SOURCE
    assert "SENDER_BLOCK_SENTINEL_PRESERVED=true" in SOURCE
    assert "runtime_sender_preflight.py" in SOURCE
    assert "return 2" in SOURCE


def test_retired_recovery_cannot_probe_or_remove_sentinel():
    for forbidden in (
        "desbloquear_exchange_app_cert.ps1",
        "ndr_guard.check_once",
        "path.unlink()",
        "ConfirmUnblock",
        "envios_externos_cota",
    ):
        assert forbidden not in SOURCE
