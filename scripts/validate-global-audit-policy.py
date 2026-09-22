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
EXPECTED_SCHEMA = "GLOBAL_AUDIT_MANIFEST_V1"
EXPECTED_VERSION = "2026-09-21-absolute-v5"
REMOTE_MANIFEST = "https://raw.githubusercontent.com/Vivaliz-site/-shopvivaliz-pipeline/main/docs/quality/GLOBAL_AUDIT_MANIFEST.json"
LOCAL_MANIFEST = ROOT / "docs/quality/GLOBAL_AUDIT_MANIFEST.json"
EXPECTED_REPOSITORIES = [
    "Vivaliz-site/site-shopvivaliz",
    "Vivaliz-site/-shopvivaliz-pipeline",
    "Vivaliz-site/amazon-returns-safet",
    "Vivaliz-site/ml-pricing-api",
    "Vivaliz-site/mercadolivre-returns-recovery",
    "Vivaliz-site/shopvivaliz-m365",
    "Vivaliz-site/buscador",
    "fredmourao-ai/mei-mg-email",
    "fredmourao-ai/solange-rolla-consultorio",
    "fredmourao-ai/solange-rolla",
]


def git_blob_sha(data: bytes) -> str:
    header = f"blob {len(data)}\0".encode()
    return hashlib.sha1(header + data).hexdigest()


def read_local_manifest() -> dict:
    if not LOCAL_MANIFEST.is_file():
        raise FileNotFoundError(str(LOCAL_MANIFEST))
    return json.loads(LOCAL_MANIFEST.read_text(encoding="utf-8"))


def load_manifest() -> tuple[dict, bool]:
    repo = os.environ.get("GITHUB_REPOSITORY", "")
    local = read_local_manifest()

    if repo == CANONICAL_REPO:
        return local, True

    with urllib.request.urlopen(REMOTE_MANIFEST, timeout=20) as response:
        remote = json.loads(response.read().decode("utf-8"))

    return remote, local == remote


def check(manifest: dict, local_manifest_parity: bool) -> dict:
    results = []
    for relative, expected in manifest.get("required_blobs", {}).items():
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

    manifest_metadata_ok = (
        manifest.get("schema") == EXPECTED_SCHEMA
        and manifest.get("version") == EXPECTED_VERSION
        and manifest.get("canonical_repository") == CANONICAL_REPO
        and manifest.get("canonical_ref") == "main"
        and required_repositories == EXPECTED_REPOSITORIES
    )
    repo_covered = (not current_repo) or current_repo in required_repositories
    blobs_present = bool(manifest.get("required_blobs"))
    entrypoints_present = bool(manifest.get("required_entrypoint_markers"))

    ok = (
        manifest_metadata_ok
        and local_manifest_parity
        and repo_covered
        and blobs_present
        and entrypoints_present
        and all(x["ok"] for x in results)
        and all(x["ok"] for x in entrypoints)
    )

    return {
        "schema": manifest.get("schema"),
        "version": manifest.get("version"),
        "canonical_repository": manifest.get("canonical_repository"),
        "required_repositories": required_repositories,
        "current_repository": current_repo,
        "repository_covered": repo_covered,
        "manifest_metadata_ok": manifest_metadata_ok,
        "local_manifest_parity": local_manifest_parity,
        "required_blobs_present": blobs_present,
        "required_entrypoints_present": entrypoints_present,
        "blob_results": results,
        "entrypoint_results": entrypoints,
        "ok": ok,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args()

    try:
        manifest, local_manifest_parity = load_manifest()
    except Exception as exc:
        print(
            f"GLOBAL_AUDIT_MANIFEST_LOAD=FAIL {type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        return 2

    report = check(manifest, local_manifest_parity)

    if args.output_dir:
        args.output_dir.mkdir(parents=True, exist_ok=True)
        (args.output_dir / "report.json").write_text(
            json.dumps(report, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        lines = [
            "# Global Audit Policy Parity",
            "",
            f"- version: {report['version']}",
            f"- canonical_repository: {report['canonical_repository']}",
            f"- repository_covered: {report['repository_covered']} ({report['current_repository']})",
            f"- manifest_metadata_ok: {report['manifest_metadata_ok']}",
            f"- local_manifest_parity: {report['local_manifest_parity']}",
            "",
        ]
        for item in report["blob_results"]:
            lines.append(f"- {'PASS' if item['ok'] else 'FAIL'} blob {item['path']}")
        for item in report["entrypoint_results"]:
            lines.append(f"- {'PASS' if item['ok'] else 'FAIL'} entrypoint {item['path']}")
        (args.output_dir / "report.md").write_text(
            "\n".join(lines) + "\n",
            encoding="utf-8",
        )

    print(
        f"GLOBAL_MANIFEST_METADATA "
        f"{'PASS' if report['manifest_metadata_ok'] else 'FAIL'}"
    )
    print(
        f"GLOBAL_MANIFEST_LOCAL_PARITY "
        f"{'PASS' if report['local_manifest_parity'] else 'FAIL'}"
    )
    print(
        f"GLOBAL_REPOSITORY "
        f"{'PASS' if report['repository_covered'] else 'FAIL'} "
        f"{report['current_repository']}"
    )

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
