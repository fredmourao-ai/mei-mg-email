#!/usr/bin/env python3
"""Fail-closed provenance check for pushes to a protected default branch."""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

API = "https://api.github.com"


def evaluate_associated_prs(prs: list[dict], branch: str) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    if not prs:
        return False, ["no associated pull request"]

    valid = []
    for pr in prs:
        if not isinstance(pr, dict):
            continue
        base = pr.get("base")
        base_ref = base.get("ref") if isinstance(base, dict) else None
        merged_at = pr.get("merged_at")
        state = pr.get("state")
        number = pr.get("number")
        if merged_at and state == "closed" and base_ref == branch:
            valid.append(number)

    if not valid:
        reasons.append(
            f"no merged pull request targets default branch {branch!r}"
        )
        return False, reasons

    return True, [f"associated merged pull request(s): {valid}"]


def github_get_json(url: str, token: str) -> object:
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "User-Agent": "shopvivaliz-absolute-audit-main-guard",
            "X-GitHub-Api-Version": "2022-11-28",
            "Cache-Control": "no-cache",
        },
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        return json.loads(response.read().decode("utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository", default=os.environ.get("GITHUB_REPOSITORY", ""))
    parser.add_argument("--sha", default=os.environ.get("GITHUB_SHA", ""))
    parser.add_argument("--branch", default=os.environ.get("GITHUB_REF_NAME", ""))
    parser.add_argument("--token", default=os.environ.get("GITHUB_TOKEN", ""))
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args()

    report = {
        "schema": "AUDIT_MAIN_MERGE_PROVENANCE_V1",
        "repository": args.repository,
        "sha": args.sha,
        "branch": args.branch,
        "ok": False,
        "reasons": [],
    }

    missing = [
        name
        for name, value in [
            ("repository", args.repository),
            ("sha", args.sha),
            ("branch", args.branch),
            ("token", args.token),
        ]
        if not value
    ]
    if missing:
        report["reasons"] = ["missing required input(s): " + ", ".join(missing)]
        _write_report(report, args.output_dir)
        _print_report(report)
        return 1

    if args.branch not in {"main", "master"}:
        report["reasons"] = [f"unexpected guarded branch: {args.branch!r}"]
        _write_report(report, args.output_dir)
        _print_report(report)
        return 1

    repo = urllib.parse.quote(args.repository, safe="/")
    sha = urllib.parse.quote(args.sha, safe="")
    url = f"{API}/repos/{repo}/commits/{sha}/pulls"

    try:
        payload = github_get_json(url, args.token)
    except Exception as exc:
        report["reasons"] = [f"github provenance lookup failed: {type(exc).__name__}: {exc}"]
        _write_report(report, args.output_dir)
        _print_report(report)
        return 2

    if not isinstance(payload, list):
        report["reasons"] = ["GitHub returned a non-list pull request payload"]
        _write_report(report, args.output_dir)
        _print_report(report)
        return 1

    ok, reasons = evaluate_associated_prs(payload, args.branch)
    report["ok"] = ok
    report["reasons"] = reasons
    report["associated_pr_count"] = len(payload)

    _write_report(report, args.output_dir)
    _print_report(report)
    return 0 if ok else 1


def _write_report(report: dict, output_dir: Path | None) -> None:
    if not output_dir:
        return
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "report.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    lines = [
        "# Absolute Audit Main Merge Provenance",
        "",
        f"- repository: {report.get('repository')}",
        f"- sha: {report.get('sha')}",
        f"- branch: {report.get('branch')}",
        f"- ok: {report.get('ok')}",
        "",
        "## Reasons",
    ]
    lines.extend(f"- {item}" for item in report.get("reasons", []))
    (output_dir / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def _print_report(report: dict) -> None:
    print(f"AUDIT_MAIN_PROVENANCE={'PASS' if report.get('ok') else 'FAIL'}")
    for reason in report.get("reasons", []):
        print(f"AUDIT_MAIN_PROVENANCE_REASON={reason}")


if __name__ == "__main__":
    raise SystemExit(main())
