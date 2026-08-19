from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT / "scripts" / "recuperar_sender_block_sentinel.py").read_text(
    encoding="utf-8"
)


def test_recovery_never_unblocks_exchange_automatically():
    assert "desbloquear_exchange_app_cert.ps1" in SOURCE
    assert "ConfirmUnblock" not in SOURCE
    assert '"EXCHANGE_SENDER_NOT_BLOCKED"' in SOURCE


def test_recovery_requires_internal_probe_and_quota_ledger():
    assert "_is_internal_recipient(TEST_RECIPIENT)" in SOURCE
    assert "@shopvivaliz.com.br" in SOURCE
    assert "envios_externos_cota" in SOURCE
    assert "sender_block_recovery_probe" in SOURCE
    assert "settings.max_envios_por_dia" in SOURCE


def test_recovery_requires_async_ndr_observation_before_clear():
    assert SOURCE.count("ndr_guard.check_once(provider)") >= 2
    assert "time.sleep(NDR_WAIT_SECONDS)" in SOURCE
    assert "sender-block NDR detected after controlled probe" in SOURCE
    assert SOURCE.index("time.sleep(NDR_WAIT_SECONDS)") < SOURCE.index(
        "path.unlink()"
    )


def test_recovery_checks_exchange_before_and_after_probe():
    assert "exchange_before = _exchange_not_blocked()" in SOURCE
    assert "exchange_after = _exchange_not_blocked()" in SOURCE
    assert SOURCE.index("exchange_after = _exchange_not_blocked()") < SOURCE.index(
        "path.unlink()"
    )


def test_recovery_preserves_fail_closed_propagation_window():
    assert "SENDER_BLOCK_RECOVERY_MIN_AGE_MINUTES" in SOURCE
    assert "sender-block sentinel too recent for safe recovery" in SOURCE
    assert "SENDER_BLOCK_RECOVERY_NDR_WAIT_SECONDS" in SOURCE
