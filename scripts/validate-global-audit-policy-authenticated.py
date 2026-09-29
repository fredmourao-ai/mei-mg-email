#!/usr/bin/env python3
"""Run the immutable global audit validator with authenticated GitHub reads."""
from __future__ import annotations
import os
import runpy
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "scripts" / "validate-global-audit-policy.py"

def install_authenticated_opener() -> None:
    token = os.environ.get("GITHUB_TOKEN", "").strip()
    if not token:
        return
    opener = urllib.request.build_opener()
    opener.addheaders = [
        ("Authorization", f"Bearer {token}"),
        ("Accept", "application/vnd.github.raw+json"),
        ("User-Agent", "shopvivaliz-absolute-audit-v5-auth-wrapper"),
    ]
    urllib.request.install_opener(opener)

if __name__ == "__main__":
    install_authenticated_opener()
    runpy.run_path(str(TARGET), run_name="__main__")
