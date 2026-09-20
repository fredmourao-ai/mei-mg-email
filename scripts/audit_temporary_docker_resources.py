#!/usr/bin/env python3
"""Reject restore helpers that can leak anonymous Docker volumes.

A PostgreSQL image declares /var/lib/postgresql/data as a VOLUME. A temporary
restore container created without --rm can therefore leave an anonymous volume
behind even when the container itself is removed. Restore containers must also
carry execution provenance labels so abandoned resources can be attributed.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

SELF = Path(__file__).resolve()


def _logical_lines(text: str) -> list[tuple[int, str]]:
    raw = text.splitlines()
    out: list[tuple[int, str]] = []
    index = 0
    while index < len(raw):
        start = index + 1
        line = raw[index].strip()
        while line.endswith("\\") and index + 1 < len(raw):
            line = line[:-1].rstrip() + " " + raw[index + 1].strip()
            index += 1
        out.append((start, line))
        index += 1
    return out


def audit_text(path: Path, text: str) -> list[str]:
    if "pg_restore" not in text or "docker run" not in text:
        return []

    findings: list[str] = []
    for line_number, command in _logical_lines(text):
        if not re.search(r"\bdocker\s+run\b", command):
            continue

        prefix = f"{path}:{line_number}"
        if not re.search(r"(^|\s)--rm(\s|$)", command):
            findings.append(f"{prefix}: temporary restore docker run missing --rm")

        lowered = command.casefold()
        if "--label" not in command or "execution_id=" not in lowered:
            findings.append(f"{prefix}: temporary restore docker run missing execution_id label")
        if "--label" not in command or "origin=" not in lowered:
            findings.append(f"{prefix}: temporary restore docker run missing origin label")

    return findings


def _candidate_paths(root: Path) -> list[Path]:
    candidates: list[Path] = []
    workflows = root / ".github" / "workflows"
    if workflows.is_dir():
        candidates.extend(workflows.glob("*.yml"))
        candidates.extend(workflows.glob("*.yaml"))

    scripts = root / "scripts"
    if scripts.is_dir():
        for suffix in ("*.sh", "*.py", "*.ps1"):
            candidates.extend(scripts.rglob(suffix))

    return sorted(
        path
        for path in set(candidates)
        if path.is_file() and path.resolve() != SELF
    )


def audit_repository(root: Path) -> list[str]:
    findings: list[str] = []
    for path in _candidate_paths(root):
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        findings.extend(audit_text(path.relative_to(root), text))
    return findings


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    findings = audit_repository(root)
    if findings:
        print("TEMP_DOCKER_RESOURCE_AUDIT_FAIL")
        for finding in findings:
            print(finding)
        return 1

    print("TEMP_DOCKER_RESOURCE_AUDIT_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
