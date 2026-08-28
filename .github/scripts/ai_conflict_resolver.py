#!/usr/bin/env python3
import json
import os
import re
import subprocess
import sys
import urllib.request
from pathlib import Path

MARKERS = ("<<<<<<<", "=======", ">>>>>>>")
PROTECTED_PARTS = {
    ".env", "secret", "credential", "certificate", "certs/", ".key", ".pem",
    ".p12", ".pfx", "migration", "migrations/", ".github/workflows/", "auth/",
    "oauth", "token", "password", "billing", "payment", "checkout", "production",
    "deploy", "terraform", "k8s/", "helm/", "suppress", "send", "campaign",
    "graph", "recipient", "rate_limit", "email-safety", "repo-policy"
}
SENSITIVE_CONTENT = re.compile(
    r"BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY|(?:api[_-]?key|client[_-]?secret|password)\s*[:=]",
    re.IGNORECASE,
)


def run(*args, check=True):
    return subprocess.run(args, text=True, capture_output=True, check=check)


def is_protected_path(path):
    value = path.replace("\\", "/").lower()
    return any(part in value for part in PROTECTED_PARTS)


def has_conflict_markers(content):
    return any(marker in content for marker in MARKERS)


def parse_model_content(raw, expected_path):
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError("model did not return valid JSON") from exc
    if payload.get("path") != expected_path:
        raise ValueError("model returned a different path")
    content = payload.get("content")
    if not isinstance(content, str):
        raise ValueError("model response is missing string content")
    return content


def validate_candidate(path, original, candidate):
    if is_protected_path(path):
        raise ValueError("protected path")
    if not candidate.strip():
        raise ValueError("empty candidate")
    if has_conflict_markers(candidate):
        raise ValueError("candidate still has conflict markers")
    old_lines = max(1, len(original.splitlines()))
    new_lines = len(candidate.splitlines())
    if old_lines >= 20 and new_lines < max(2, int(old_lines * 0.40)):
        raise ValueError("candidate deletes too much content")
    return candidate


def git_stage(path, stage):
    result = run("git", "show", f":{stage}:{path}", check=False)
    return result.stdout if result.returncode == 0 else ""


def conflicted_files():
    result = run("git", "diff", "--name-only", "--diff-filter=U")
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def ollama_resolve(path, base, ours, theirs, rules):
    prompt = f"""You resolve one Git merge conflict conservatively.
Return ONLY JSON with exactly keys path and content. path must be {json.dumps(path)}.
Preserve compatible behavior from both sides. Do not invent secrets, delete unrelated behavior, or include markdown fences.
Repository rules:\n{rules[:12000]}\n
BASE:\n{base[:50000]}\n--- OURS ---\n{ours[:50000]}\n--- THEIRS ---\n{theirs[:50000]}\n"""
    body = json.dumps({
        "model": os.getenv("OLLAMA_MODEL", "qwen2.5-coder:1.5b"),
        "prompt": prompt,
        "stream": False,
        "format": "json",
        "options": {"temperature": 0.1},
    }).encode()
    request = urllib.request.Request(
        os.getenv("OLLAMA_URL", "http://127.0.0.1:11434/api/generate"),
        data=body,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=180) as response:
        envelope = json.loads(response.read().decode())
    return parse_model_content(envelope.get("response", ""), path)


def main():
    files = conflicted_files()
    if not files:
        print("AI_RESOLVER=no_conflicts")
        return 0
    blocked = [path for path in files if is_protected_path(path)]
    if blocked:
        print("AI_RESOLVER=human_review protected=" + ",".join(blocked), file=sys.stderr)
        return 3
    rules_path = Path("AI_CONFLICT_RULES.md")
    rules = rules_path.read_text(encoding="utf-8") if rules_path.exists() else "Preserve both compatible changes."
    for path in files:
        base, ours, theirs = (git_stage(path, n) for n in (1, 2, 3))
        if any("\x00" in text for text in (base, ours, theirs)):
            print(f"AI_RESOLVER=human_review binary={path}", file=sys.stderr)
            return 3
        if any(SENSITIVE_CONTENT.search(text or "") for text in (base, ours, theirs)):
            print(f"AI_RESOLVER=human_review sensitive_content={path}", file=sys.stderr)
            return 3
        reference = ours or theirs or base
        candidate = ollama_resolve(path, base, ours, theirs, rules)
        candidate = validate_candidate(path, reference, candidate)
        Path(path).write_text(candidate, encoding="utf-8")
        run("git", "add", "--", path)
    remaining = conflicted_files()
    if remaining:
        print("AI_RESOLVER=unresolved files=" + ",".join(remaining), file=sys.stderr)
        return 4
    print("AI_RESOLVER=resolved files=" + ",".join(files))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())