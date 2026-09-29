#!/usr/bin/env python3
"""Governance guard: caps the number of active direct ``issue_comment`` listeners.

Scans real GitHub Actions workflow files under ``.github/workflows`` (skipping
``*.disabled`` files and anything under an ``archive``/``historical`` path
segment) and counts how many declare ``issue_comment`` as a direct top-level
trigger key under ``on:``. Exits non-zero when more than one active listener
is found, keeping ``ACTIVE_DIRECT_ISSUE_COMMENT_LISTENERS <= 1`` enforced.

This intentionally does not require a YAML parsing dependency: it walks the
``on:`` trigger block line by line, tracking indentation, so a mention of the
string ``issue_comment`` inside a step's ``run:`` script or a comment never
counts as a trigger.
"""
from __future__ import annotations

import argparse
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_WORKFLOWS_DIR = ROOT / ".github" / "workflows"

WORKFLOW_SUFFIXES = {".yml", ".yaml"}
EXCLUDED_PATH_SEGMENTS = {"archive", "historical"}

_ON_KEY_RE = re.compile(r"^(on|['\"]on['\"]):\s*(.*)$")
_ITEM_KEY_RE = re.compile(r"^([A-Za-z0-9_.\-]+)\s*:")
_LIST_ITEM_RE = re.compile(r"^-\s*(.+?)\s*$")


def _indent(line: str) -> int:
    return len(line) - len(line.lstrip(" "))


def _strip_comment(line: str) -> str:
    # Workflow trigger keys never legitimately contain a ``#``; a naive
    # strip is safe here because we only apply it to lines inside the
    # ``on:`` block, never to arbitrary script content.
    if "#" in line:
        return line.split("#", 1)[0]
    return line


def has_direct_issue_comment_trigger(text: str) -> bool:
    lines = text.splitlines()
    on_line_index = None
    on_indent = 0
    inline_value = ""

    for index, raw_line in enumerate(lines):
        if not raw_line.strip() or raw_line.lstrip().startswith("#"):
            continue
        if _indent(raw_line) != 0:
            continue
        match = _ON_KEY_RE.match(raw_line.strip())
        if match:
            on_line_index = index
            on_indent = _indent(raw_line)
            inline_value = match.group(2).strip()
            break

    if on_line_index is None:
        return False

    # Shorthand forms on the same line as ``on:``.
    if inline_value:
        if inline_value.startswith("["):
            items = [item.strip().strip("'\"") for item in inline_value.strip("[]").split(",")]
            return "issue_comment" in items
        # Single scalar trigger, e.g. ``on: workflow_dispatch``.
        return inline_value.strip("'\"") == "issue_comment"

    # Block form: collect the immediate children of the ``on:`` mapping.
    block_indent = None
    for raw_line in lines[on_line_index + 1 :]:
        if not raw_line.strip() or raw_line.lstrip().startswith("#"):
            continue
        current_indent = _indent(raw_line)
        if current_indent <= on_indent:
            break
        if block_indent is None:
            block_indent = current_indent
        if current_indent != block_indent:
            continue
        content = _strip_comment(raw_line.strip()).strip()
        if not content:
            continue
        list_match = _LIST_ITEM_RE.match(content)
        if list_match:
            item = list_match.group(1).strip().strip("'\"")
            if item.rstrip(":") == "issue_comment":
                return True
            continue
        key_match = _ITEM_KEY_RE.match(content)
        if key_match and key_match.group(1) == "issue_comment":
            return True

    return False


def iter_workflow_files(workflows_dir: Path) -> list[Path]:
    if not workflows_dir.is_dir():
        return []
    found = []
    for path in sorted(workflows_dir.rglob("*")):
        if not path.is_file():
            continue
        if path.suffix not in WORKFLOW_SUFFIXES:
            continue
        relative_parts = path.relative_to(workflows_dir).parts
        if any(segment.lower() in EXCLUDED_PATH_SEGMENTS for segment in relative_parts[:-1]):
            continue
        found.append(path)
    return found


def count_listeners(workflows_dir: Path) -> tuple[int, list[Path]]:
    matches = []
    for path in iter_workflow_files(workflows_dir):
        text = path.read_text(encoding="utf-8")
        if has_direct_issue_comment_trigger(text):
            matches.append(path)
    return len(matches), matches


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--workflows-dir",
        default=str(DEFAULT_WORKFLOWS_DIR),
        help="Directory containing GitHub Actions workflow files.",
    )
    parser.add_argument(
        "--max-listeners",
        type=int,
        default=1,
        help="Maximum number of active direct issue_comment listeners allowed.",
    )
    args = parser.parse_args(argv)

    workflows_dir = Path(args.workflows_dir)
    count, matches = count_listeners(workflows_dir)

    print(f"Direct issue_comment listeners found: {count}")
    for path in matches:
        print(f"  - {path}")

    if count > args.max_listeners:
        print(
            f"FAIL: {count} active direct issue_comment listener(s) exceed the "
            f"allowed maximum of {args.max_listeners}."
        )
        return 1

    print(f"OK: {count} active direct issue_comment listener(s) (max {args.max_listeners}).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
