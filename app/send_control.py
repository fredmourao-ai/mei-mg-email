"""Controle operacional simples para pausar e retomar envios."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent
PAUSE_FILE = BASE_DIR / "shared" / "email-sends.paused"


def email_sends_paused() -> bool:
    return PAUSE_FILE.exists()


def pause_email_sends(reason: str) -> None:
    PAUSE_FILE.parent.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).isoformat()
    PAUSE_FILE.write_text(f"paused_at={timestamp}\nreason={reason}\n", encoding="utf-8")


def resume_email_sends() -> None:
    PAUSE_FILE.unlink(missing_ok=True)
