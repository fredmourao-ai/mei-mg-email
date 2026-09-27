#!/usr/bin/env python3
"""Fail-closed adapter to the canonical ShopVivaliz task-continuity controller."""
from __future__ import annotations
import json, os, subprocess, sys
from pathlib import Path

REPOSITORY = "fredmourao-ai/mei-mg-email"
CONTROLLER_ENV = "SHOPVIVALIZ_CONTINUITY_STATE_CLI"
RUNTIME_ENV = "SHOPVIVALIZ_AGENT_TASK_STATE_DIR"

def controller_path() -> Path:
    configured = os.getenv(CONTROLLER_ENV, "").strip()
    return Path(configured).expanduser() if configured else Path()

def build_controller_env(base=None):
    env = dict(base or os.environ)
    env["SHOPVIVALIZ_TASK_REPOSITORY"] = REPOSITORY
    runtime = env.get(RUNTIME_ENV, "").strip()
    if runtime:
        env[RUNTIME_ENV] = str(Path(runtime).expanduser())
    return env

def main() -> int:
    if sys.argv[1:] == ["--adapter-self-test"]:
        print(json.dumps({"ok": True, "repository": REPOSITORY, "mode": "canonical-controller-adapter"}))
        return 0
    controller = controller_path()
    try:
        same_file = controller.resolve() == Path(__file__).resolve()
    except OSError:
        same_file = False
    if same_file or not controller.is_file():
        print(json.dumps({"ok": False, "error": "global_continuity_controller_unavailable", "repository": REPOSITORY}, sort_keys=True), file=sys.stderr)
        return 69
    return int(subprocess.run([sys.executable, str(controller), *sys.argv[1:]], env=build_controller_env(), check=False).returncode)

if __name__ == "__main__":
    raise SystemExit(main())
