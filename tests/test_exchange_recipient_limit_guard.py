import os
import subprocess
import sys
from pathlib import Path

from scripts.ndr_guard import contains_sender_blocked_marker, is_permanent_recipient_ndr

ROOT = Path(__file__).resolve().parents[1]


def test_exchange_5_1_90_is_global_sender_circuit_breaker():
    samples = (
        "550 5.1.90 Your message can't be sent because you've reached your daily limit for message recipients. (AS:46601)",
        "Your message can't be sent because you've reached your 24 hour limit for message recipients.",
    )
    for text in samples:
        assert contains_sender_blocked_marker(text), text
        assert not is_permanent_recipient_ndr(text), text


def test_exchange_recipient_safety_reserve_caps_old_9950_configuration():
    env = os.environ.copy()
    env["META_ENVIOS_POR_DIA"] = "9950"
    env["EXCHANGE_RECIPIENT_SAFETY_RESERVE"] = "1000"
    command = [
        sys.executable,
        "-c",
        "from app.config import settings; print(settings.meta_envios_por_dia)",
    ]
    completed = subprocess.run(command, cwd=ROOT, env=env, capture_output=True, text=True, check=True)
    assert completed.stdout.strip() == "9000"
