#!/usr/bin/env python3
from __future__ import annotations

import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAX_ACTIVE_MIGRATION = 20
TEXT_SUFFIXES = {'.py', '.sql', '.sh', '.md', '.yml', '.yaml', '.service', '.timer'}

PROTECTED_PREFIXES = (
    'app/',
    'worker/',
    'scripts/',
    'deploy/systemd/',
    '.github/workflows/',
    '.githooks/',
)
PROTECTED_DOCS = {'docs/fila-continua.md'}

OLD_FILTER_PATTERNS = (
    re.compile(r"\b(where|and)\b[^\n;]{0,180}\b" + "marketing_" + "autorizado" + r"\b", re.I),
    re.compile(r"\b(where|and)\b[^\n;]{0,180}\bmei_verificado\b", re.I),
    re.compile(r"\b(where|and)\b[^\n;]{0,180}\btipo_regime\b", re.I),
    re.compile(r"\b(where|and)\b[^\n;]{0,180}\buf\b[^\n;]{0,60}=\s*['\"]MG['\"]", re.I),
    re.compile(r"\bvw_empresas_elegiveis\b", re.I),
    re.compile(r"\bfilter_not_mei\b", re.I),
    re.compile(r"\binsert_filter_gate\b", re.I),
)

DESTRUCTIVE_PATTERNS = (
    re.compile(r"delete\s+from\s+mei_email\.envios\b", re.I),
    re.compile(r"delete\s+from\s+mei_email\.empresas\b", re.I),
)


def git_check_output(*args: str) -> str:
    return subprocess.check_output(
        ['git', '-c', f'safe.directory={ROOT}', '-C', str(ROOT), *args],
        text=True,
    )


def repo_files() -> list[str]:
    out = git_check_output('ls-files', '--cached', '--others', '--exclude-standard')
    return sorted({line.strip() for line in out.splitlines() if line.strip()})


def changed_paths() -> set[str]:
    out = git_check_output('status', '--porcelain=v1')
    paths: set[str] = set()
    for line in out.splitlines():
        if len(line) >= 4:
            path = line[3:].strip()
            if ' -> ' in path:
                path = path.split(' -> ', 1)[1]
            paths.add(path)
    return paths


def is_protected(path: str, changed: set[str]) -> bool:
    if path in PROTECTED_DOCS:
        return True
    if path.startswith(PROTECTED_PREFIXES):
        return True
    if path.startswith('db/migrations/') and path in changed:
        return True
    return False


def scan_file(path: str, changed: set[str]) -> list[str]:
    if path in {'scripts/repo_policy_guard.py', 'scripts/runtime_policy_guard.py'}:
        return []
    if not is_protected(path, changed):
        return []
    full = ROOT / path
    if full.suffix.lower() not in TEXT_SUFFIXES and path not in PROTECTED_DOCS:
        return []
    try:
        text = full.read_text(encoding='utf-8')
    except (UnicodeDecodeError, OSError):
        return []

    violations: list[str] = []
    for pattern in OLD_FILTER_PATTERNS:
        if pattern.search(text):
            violations.append(f'{path}: politica antiga detectada: {pattern.pattern}')
    if path.startswith(('app/', 'worker/', 'scripts/')):
        for pattern in DESTRUCTIVE_PATTERNS:
            if pattern.search(text):
                violations.append(f'{path}: delete operacional destrutivo: {pattern.pattern}')
    return violations


def main() -> int:
    changed = changed_paths()
    violations: list[str] = []
    for path in (ROOT / 'db' / 'migrations').glob('V[0-9]*__*.sql'):
        match = re.match(r'V(\d+)__', path.name)
        if match and int(match.group(1)) > MAX_ACTIVE_MIGRATION:
            violations.append(
                f'{path.relative_to(ROOT)}: active migration above canonical ceiling V{MAX_ACTIVE_MIGRATION:03d}'
            )
    for path in repo_files():
        violations.extend(scan_file(path, changed))

    if violations:
        print('REPO_POLICY_GUARD_FAIL')
        for item in sorted(set(violations)):
            print(item)
        return 2

    print('REPO_POLICY_GUARD_OK')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
