#!/usr/bin/env python3
"""Falha o CI quando credenciais aparentes entram no working tree.

Nao tenta substituir um secret scanner dedicado; funciona como gate local para
os formatos que este repositorio ja utilizou ou que seriam especialmente
perigosos em scripts de email/deploy.
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

PATTERNS = (
    ("github_token", re.compile(r"\bgh[pousr]_[A-Za-z0-9_]{20,}\b")),
    ("openai_key", re.compile(r"\bsk-(?:proj-)?[A-Za-z0-9_-]{20,}\b")),
    ("private_key", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----")),
    ("hardcoded_smtp_login", re.compile(r"server\.login\(\s*['\"][^'\"]+['\"]\s*,\s*['\"][^'\"]{8,}['\"]\s*\)")),
    ("hardcoded_access_token", re.compile(r"(?i)(?:access[_-]?token|client[_-]?secret|app[_-]?password)\s*[=:]\s*['\"][^'\"]{8,}['\"]")),
)

TEXT_SUFFIXES = {
    ".py", ".ps1", ".sh", ".yml", ".yaml", ".json", ".toml", ".ini",
    ".env", ".md", ".txt", ".sql", ".conf", ".service", ".timer",
}


def tracked_files() -> list[Path]:
    output = subprocess.check_output(["git", "ls-files", "-z"], cwd=ROOT)
    return [ROOT / item.decode("utf-8") for item in output.split(b"\0") if item]


def scan() -> list[tuple[str, str]]:
    findings: list[tuple[str, str]] = []
    for path in tracked_files():
        if not path.is_file():
            continue
        if path.name == ".env.example":
            # Placeholders vazios sao esperados; ainda escaneamos chaves/token
            # completos pelos padroes abaixo.
            pass
        if path.suffix.casefold() not in TEXT_SUFFIXES and path.name not in {"Dockerfile", "Makefile"}:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for name, pattern in PATTERNS:
            if pattern.search(text):
                findings.append((str(path.relative_to(ROOT)), name))
    return findings


def main() -> int:
    findings = scan()
    if findings:
        print("SECRET_SCAN_FAILED")
        for path, kind in findings:
            print(f"finding={kind} path={path}")
        return 2
    print("SECRET_SCAN_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
