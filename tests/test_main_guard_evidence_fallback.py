import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_main_guard_has_fail_closed_external_evidence_fallback():
    workflow = (ROOT / ".github/workflows/absolute-audit-main-guard.yml").read_text()

    assert "id: github_artifact" in workflow
    assert "continue-on-error: true" in workflow
    assert "steps.github_artifact.outcome == 'failure'" in workflow
    assert "scripts/publish-main-guard-evidence-oci.sh" in workflow
    assert "Require published main-guard evidence" in workflow


def test_oci_evidence_publisher_is_fail_closed():
    script = (ROOT / "scripts/publish-main-guard-evidence-oci.sh").read_text()

    assert "set -Eeuo pipefail" in script
    assert "--auth instance_principal" in script
    assert "os object put" in script
    assert "os object head" in script
    assert "sha256sum" in script
    assert "cmp -s" in script
    assert "verification.json" in script



def _run_publisher_with_fake_oci(corrupt_tar: bool):
    with tempfile.TemporaryDirectory(prefix="mei-main-guard-") as temporary:
        project = Path(temporary)
        publisher = project / "scripts" / "publish-main-guard-evidence-oci.sh"
        publisher.parent.mkdir(parents=True)
        shutil.copyfile(ROOT / "scripts" / "publish-main-guard-evidence-oci.sh", publisher)

        artifact_names = (
            "audit-governance-self-test",
            "global-audit-policy",
            "main-merge-provenance",
        )
        for name in artifact_names:
            artifact_dir = project / "artifacts" / name
            artifact_dir.mkdir(parents=True)
            (artifact_dir / "report.md").write_text("fixture evidence\n", encoding="utf-8")

        store = project / "object-store"
        store.mkdir()
        fake_cli = project / "oci"
        fake_cli.write_text(
            """#!/usr/bin/env python3
import json
import os
import shutil
import sys
from pathlib import Path

args = sys.argv[1:]
operation = args[2]

def option(name):
    return args[args.index(name) + 1]

store = Path(os.environ["FAKE_OCI_STORE"])
object_path = store / option("--name")
object_path.parent.mkdir(parents=True, exist_ok=True)

if operation == "put":
    source = Path(option("--file"))
    shutil.copyfile(source, object_path)
    if os.environ.get("CORRUPT_TAR") == "1" and object_path.name.endswith(".tar.gz"):
        contents = bytearray(object_path.read_bytes())
        contents[0] ^= 1
        object_path.write_bytes(contents)
elif operation == "head":
    print(json.dumps({"content-length": str(object_path.stat().st_size)}))
elif operation == "get":
    shutil.copyfile(object_path, Path(option("--file")))
else:
    raise SystemExit("unsupported fake OCI operation")
""",
            encoding="utf-8",
        )
        fake_cli.chmod(0o700)

        env = os.environ.copy()
        env.update(
            {
                "OCI_CLI": str(fake_cli),
                "OCI_NAMESPACE": "fixture-namespace",
                "OCI_BUCKET": "fixture-bucket",
                "OCI_AUDIT_PREFIX": "fixture-audit",
                "GITHUB_SHA": "a" * 40,
                "GITHUB_RUN_ID": "4242",
                "FAKE_OCI_STORE": str(store),
                "CORRUPT_TAR": "1" if corrupt_tar else "0",
            }
        )
        result = subprocess.run(
            ["bash", str(publisher)],
            cwd=project,
            env=env,
            text=True,
            capture_output=True,
            check=False,
        )
        verification = (
            project / "artifacts" / "main-guard-evidence-fallback" / "verification.json"
        )
        data = (
            json.loads(verification.read_text(encoding="utf-8"))
            if verification.exists()
            else None
        )
        return result, data


def test_publisher_rejects_same_size_remote_archive_corruption():
    result, _ = _run_publisher_with_fake_oci(corrupt_tar=True)

    assert result.returncode != 0


def test_publisher_accepts_and_binds_verified_remote_archive():
    result, data = _run_publisher_with_fake_oci(corrupt_tar=False)

    assert result.returncode == 0, result.stderr
    assert data is not None
    assert data["status"] == "verified"
    assert data["transport"] == "oci_object_storage"
    expected_object = f"fixture-audit/{'a' * 40}/4242/absolute-audit-main-guard.tar.gz"
    assert data["object"] == expected_object
    assert data["size_bytes"] > 0
    assert len(data["sha256"]) == 64

