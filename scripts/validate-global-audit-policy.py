#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CANONICAL_REPO = "Vivaliz-site/-shopvivaliz-pipeline"
REMOTE_MANIFEST = "https://raw.githubusercontent.com/Vivaliz-site/-shopvivaliz-pipeline/main/docs/quality/GLOBAL_AUDIT_MANIFEST.json"
LOCAL_MANIFEST = ROOT / "docs/quality/GLOBAL_AUDIT_MANIFEST.json"


def git_blob_sha(data: bytes) -> str:
    header = f"blob {len(data)}\0".encode()
    return hashlib.sha1(header + data).hexdigest()


def load_manifest() -> dict:
    repo = os.environ.get("GITHUB_REPOSITORY", "")
    if repo == CANONICAL_REPO and LOCAL_MANIFEST.is_file():
        return json.loads(LOCAL_MANIFEST.read_text(encoding="utf-8"))
    with urllib.request.urlopen(REMOTE_MANIFEST, timeout=20) as response:
        return json.loads(response.read().decode("utf-8"))


def check(manifest: dict) -> dict:
    results = []
    for relative, expected in manifest["required_blobs"].items():
        path = ROOT / relative
        if not path.is_file():
            results.append({"path": relative, "ok": False, "reason": "missing"})
            continue
        actual = git_blob_sha(path.read_bytes())
        results.append({
            "path": relative,
            "ok": actual == expected,
            "expected": expected,
            "actual": actual,
        })

    entrypoints = []
    for relative, markers in manifest.get("required_entrypoint_markers", {}).items():
        path = ROOT / relative
        if not path.is_file():
            entrypoints.append({"path": relative, "ok": False, "missing": ["<file missing>"]})
            continue
        text = path.read_text(encoding="utf-8-sig")
        missing = [marker for marker in markers if marker not in text]
        entrypoints.append({"path": relative, "ok": not missing, "missing": missing})

    current_repo = os.environ.get("GITHUB_REPOSITORY", "")
    required_repositories = manifest.get("required_repositories", [])
    repo_covered = (not current_repo) or current_repo in required_repositories

    return {
        "schema": manifest.get("schema"),
        "version": manifest.get("version"),
        "canonical_repository": manifest.get("canonical_repository"),
        "required_repositories": required_repositories,
        "current_repository": current_repo,
        "repository_covered": repo_covered,
        "blob_results": results,
        "entrypoint_results": entrypoints,
        "ok": repo_covered and all(x["ok"] for x in results) and all(x["ok"] for x in entrypoints),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args()
    try:
        manifest = load_manifest()
    except Exception as exc:
        print(f"GLOBAL_AUDIT_MANIFEST_LOAD=FAIL {type(exc).__name__}", file=sys.stderr)
        return 2

    report = check(manifest)
    if args.output_dir:
        args.output_dir.mkdir(parents=True, exist_ok=True)
        (args.output_dir / "report.json").write_text(
            json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        lines = [
            "# Global Audit Policy Parity",
            "",
            f"- version: {report['version']}",
            f"- canonical_repository: {report['canonical_repository']}",
            "",
        ]
        lines.append(f"- repository_covered: {report['repository_covered']} ({report['current_repository']})")
        for item in report["blob_results"]:
            lines.append(f"- {'PASS' if item['ok'] else 'FAIL'} blob {item['path']}")
        for item in report["entrypoint_results"]:
            lines.append(f"- {'PASS' if item['ok'] else 'FAIL'} entrypoint {item['path']}")
        (args.output_dir / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"GLOBAL_REPOSITORY {'PASS' if report['repository_covered'] else 'FAIL'} {report['current_repository']}")
    for item in report["blob_results"]:
        print(f"GLOBAL_BLOB {'PASS' if item['ok'] else 'FAIL'} {item['path']}")
    for item in report["entrypoint_results"]:
        print(f"GLOBAL_ENTRYPOINT {'PASS' if item['ok'] else 'FAIL'} {item['path']}")
        if item.get("missing"):
            print("  missing=" + ", ".join(item["missing"]))

    if not report["ok"]:
        return 1
    print(f"GLOBAL_AUDIT_POLICY=PASS version={report['version']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
