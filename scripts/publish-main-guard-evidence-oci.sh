#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OCI_CLI="${OCI_CLI:-/home/ubuntu/.venvs/oci-cli/bin/oci}"
OCI_NAMESPACE="${OCI_NAMESPACE:-gruilpqsbqqb}"
OCI_BUCKET="${OCI_BUCKET:-shopvivaliz-free-archive}"
OCI_AUDIT_PREFIX="${OCI_AUDIT_PREFIX:-audit-evidence/mei-mg-email}"
GITHUB_SHA="${GITHUB_SHA:?GITHUB_SHA is required}"
GITHUB_RUN_ID="${GITHUB_RUN_ID:?GITHUB_RUN_ID is required}"

for dir in audit-governance-self-test global-audit-policy main-merge-provenance; do
  test -d "$ROOT/artifacts/$dir"
done
test -x "$OCI_CLI"

tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT INT TERM

archive="$tmp/absolute-audit-main-guard.tar.gz"
manifest="$tmp/absolute-audit-main-guard.tar.gz.sha256"
remote_manifest="$tmp/remote.sha256"
object="$OCI_AUDIT_PREFIX/$GITHUB_SHA/$GITHUB_RUN_ID/absolute-audit-main-guard.tar.gz"

tar -C "$ROOT/artifacts" -czf "$archive"   audit-governance-self-test   global-audit-policy   main-merge-provenance

size="$(stat -c %s "$archive")"
hash="$(sha256sum "$archive" | awk '{print $1}')"
printf '%s  absolute-audit-main-guard.tar.gz\n' "$hash" > "$manifest"

"$OCI_CLI" os object put   --auth instance_principal   --namespace-name "$OCI_NAMESPACE"   --bucket-name "$OCI_BUCKET"   --file "$archive"   --name "$object"   --force >/dev/null

"$OCI_CLI" os object put   --auth instance_principal   --namespace-name "$OCI_NAMESPACE"   --bucket-name "$OCI_BUCKET"   --file "$manifest"   --name "$object.sha256"   --force >/dev/null

remote_size="$("$OCI_CLI" os object head   --auth instance_principal   --namespace-name "$OCI_NAMESPACE"   --bucket-name "$OCI_BUCKET"   --name "$object" |
  sed -n 's/.*"content-length": "\([0-9][0-9]*\)".*/\1/p')"
test "$remote_size" = "$size"

"$OCI_CLI" os object get   --auth instance_principal   --namespace-name "$OCI_NAMESPACE"   --bucket-name "$OCI_BUCKET"   --name "$object.sha256"   --file "$remote_manifest" >/dev/null
cmp -s "$manifest" "$remote_manifest"

outdir="$ROOT/artifacts/main-guard-evidence-fallback"
mkdir -p "$outdir"
python3 - "$outdir/verification.json" "$object" "$size" "$hash" <<'PY'
import json
import sys
from pathlib import Path

path, object_name, size, digest = sys.argv[1:]
Path(path).write_text(
    json.dumps(
        {
            "status": "verified",
            "transport": "oci_object_storage",
            "object": object_name,
            "size_bytes": int(size),
            "sha256": digest,
        },
        sort_keys=True,
    ) + "\n",
    encoding="utf-8",
)
PY

echo "MAIN_GUARD_EVIDENCE_FALLBACK=PASS object=$object bytes=$size sha256=$hash"
