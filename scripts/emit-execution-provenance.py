#!/usr/bin/env python3
"""Emit a secret-safe execution provenance record as JSON."""
from __future__ import annotations
import argparse, hashlib, hmac, json, os, platform, socket, uuid
from datetime import datetime, timezone

def env(name: str, default: str = "") -> str:
    return os.environ.get(name, default)

p = argparse.ArgumentParser()
p.add_argument("action")
p.add_argument("--target", default=env("EXECUTION_TARGET"))
p.add_argument("--result", default=env("EXECUTION_RESULT", "STARTED"))
p.add_argument("--exit-code", default=env("EXECUTION_EXIT_CODE"))
args = p.parse_args()

github = env("GITHUB_ACTIONS").lower() == "true"
execution_id = env("EXECUTION_ID") or (
    f"gh-{env('GITHUB_RUN_ID')}-{env('GITHUB_RUN_ATTEMPT','1')}-{env('GITHUB_JOB','job')}"
    if github and env("GITHUB_RUN_ID") else str(uuid.uuid4())
)
origin_type = env("EXECUTION_ORIGIN_TYPE") or ("github-actions" if github else "cli")
origin_ref = env("EXECUTION_ORIGIN_REF")
if github and not origin_ref:
    origin_ref = f"{env('GITHUB_SERVER_URL','https://github.com')}/{env('GITHUB_REPOSITORY')}/actions/runs/{env('GITHUB_RUN_ID')}"

record = {
    "schema": "shopvivaliz.execution-provenance.v1",
    "execution_id": execution_id,
    "timestamp_utc": datetime.now(timezone.utc).isoformat(),
    "actor": env("EXECUTION_ACTOR") or env("GITHUB_ACTOR") or env("USER") or env("USERNAME"),
    "agent_tool": env("EXECUTION_AGENT") or env("AGENT_NAME") or "unknown",
    "origin_type": origin_type,
    "origin_ref": origin_ref,
    "repository": env("EXECUTION_REPOSITORY") or env("GITHUB_REPOSITORY"),
    "ref": env("EXECUTION_REF") or env("GITHUB_REF"),
    "sha": env("EXECUTION_SHA") or env("GITHUB_SHA"),
    "host": env("EXECUTION_HOST") or socket.gethostname(),
    "pid": os.getpid(),
    "parent_pid": os.getppid(),
    "parent_execution_id": env("PARENT_EXECUTION_ID"),
    "session_id": env("EXECUTION_SESSION_ID") or env("CHAT_CLI_SESSION_ID"),
    "trigger": env("EXECUTION_TRIGGER") or env("GITHUB_EVENT_NAME"),
    "action": args.action,
    "target": args.target,
    "result": args.result,
    "exit_code": args.exit_code,
    "cleanup_status": env("EXECUTION_CLEANUP_STATUS"),
    "platform": platform.system().lower(),
}
canonical = json.dumps(record, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
digest = hashlib.sha256(canonical).hexdigest()
record["payload_sha256"] = digest
record["signature_id"] = f"{record['agent_tool']}:{origin_type}:{execution_id}:{digest[:16]}"
key = env("EXECUTION_PROVENANCE_HMAC_KEY")
if key:
    record["signature_status"] = "HMAC-SHA256"
    record["signature"] = hmac.new(key.encode(), canonical, hashlib.sha256).hexdigest()
    record["signing_key_id"] = env("EXECUTION_PROVENANCE_KEY_ID", "runtime-secret")
else:
    record["signature_status"] = "UNSIGNED"
print(json.dumps(record, sort_keys=True, ensure_ascii=False))
