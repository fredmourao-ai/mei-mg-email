import os
import subprocess
import sys
from pathlib import Path

from scripts.ndr_guard import contains_sender_blocked_marker, is_permanent_recipient_ndr

ROOT = Path(__file__).resolve().parents[1]


def _legacy_exchange_env() -> dict[str, str]:
    env = os.environ.copy()
    env["EMAIL_PROVIDER"] = "microsoft_graph"
    env["MAX_ENVIOS_POR_DIA"] = "10000"
    return env


def test_exchange_5_1_90_is_global_sender_circuit_breaker():
    samples = (
        "550 5.1.90 Your message can't be sent because you've reached your daily limit for message recipients. (AS:46601)",
        "Your message can't be sent because you've reached your 24 hour limit for message recipients.",
    )
    for text in samples:
        assert contains_sender_blocked_marker(text), text
        assert not is_permanent_recipient_ndr(text), text


def test_exchange_recipient_safety_reserve_caps_old_9950_configuration():
    env = _legacy_exchange_env()
    env["META_ENVIOS_POR_DIA"] = "9950"
    env["EXCHANGE_RECIPIENT_SAFETY_RESERVE"] = "1000"
    command = [
        sys.executable,
        "-c",
        "from app.config import settings; print(settings.meta_envios_por_dia)",
    ]
    completed = subprocess.run(command, cwd=ROOT, env=env, capture_output=True, text=True, check=True)
    assert completed.stdout.strip() == "9000"


def test_active_send_auditors_do_not_require_9950_anymore():
    audit = (ROOT / "scripts" / "auditar_exchange_10000.py").read_text(encoding="utf-8")
    dispatch = (ROOT / "scripts" / "disparar_10000_mei_mg.py").read_text(encoding="utf-8")
    assert "META_ENVIOS_POR_DIA_deve_ser_9950" not in audit
    assert "EXPECTED_DAILY_TARGET = 9950" not in dispatch
    assert "9000" in audit
    assert "9000" in dispatch


def _effective_meta(**values):
    env = _legacy_exchange_env()
    env.update({key: str(value) for key, value in values.items()})
    command = [sys.executable, "-c", "from app.config import settings; print(settings.meta_envios_por_dia)"]
    completed = subprocess.run(command, cwd=ROOT, env=env, capture_output=True, text=True, check=True)
    return completed.stdout.strip()


def test_exchange_reserve_cannot_be_configured_below_500():
    assert _effective_meta(META_ENVIOS_POR_DIA=9950, EXCHANGE_RECIPIENT_SAFETY_RESERVE=50) == "9500"


def test_exchange_reserve_also_applies_to_lower_local_max():
    assert _effective_meta(META_ENVIOS_POR_DIA=9950, MAX_ENVIOS_POR_DIA=8000, EXCHANGE_RECIPIENT_SAFETY_RESERVE=1000) == "7000"


def test_active_docs_do_not_restore_stale_quota_or_retired_policy():
    paths = (
        "README.md",
        ".env.example",
        "docs/fila-continua.md",
        "docs/contabilidade-melo-disparo.md",
        "ops/README.md",
        "deploy/systemd/gate-release.txt",
    )
    combined = "\n".join((ROOT / path).read_text(encoding="utf-8") for path in paths)
    for stale in (
        "META_ENVIOS_POR_DIA=9950",
        "QUEUE_MIN_PENDING=1000",
        "QUEUE_TARGET_PENDING=5000",
        "V022 marca o estoque existente",
        "V023 aplica a mesma politica",
        "aplicar V022/V023/V024",
        "V022/V023/V024 applied",
    ):
        assert stale not in combined, stale
