#!/usr/bin/env python3
"""Fail closed before CI can touch Docker: isolate names, volumes and ports."""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]

def validate(compose_file: Path, project: str) -> None:
    if re.fullmatch(r"mei-ci-[0-9]+-[0-9]+", project) is None:
        raise ValueError("CI project must include numeric run id and attempt")
    env = dict(os.environ, COMPOSE_PROJECT_NAME=project, POSTGRES_PASSWORD="ci_guard_fixture_only")
    result = subprocess.run(
        ["docker", "compose", "--env-file", "/dev/null", "--project-name", project,
         "--file", str(compose_file), "config", "--format", "json"],
        env=env, text=True, capture_output=True, check=True, timeout=20,
    )
    config = json.loads(result.stdout)
    if config.get("name") != project or set(config.get("services", {})) != {"db", "flyway"}:
        raise ValueError("unexpected CI project or services")
    for resource in [*config.get("volumes", {}).values(), *config.get("networks", {}).values()]:
        if resource.get("external") or not resource.get("name", "").startswith(project + "_"):
            raise ValueError("CI resource could reuse a production volume or network")
    allowed_binds = {(ROOT / "db/init").resolve(), (ROOT / "db/migrations").resolve()}
    for service in config["services"].values():
        if service.get("container_name") or service.get("network_mode") or service.get("privileged"):
            raise ValueError("fixed container names, host networks and privileged mode are forbidden")
        for mount in service.get("volumes", []):
            if mount["type"] == "bind":
                if Path(mount["source"]).resolve() not in allowed_binds or not mount.get("read_only"):
                    raise ValueError("unexpected or writable host bind in CI")
            elif mount["type"] == "volume":
                if mount["source"] not in config.get("volumes", {}):
                    raise ValueError("unscoped CI data volume")
            else:
                raise ValueError("unsupported CI mount")
    ports = config["services"]["db"].get("ports", [])
    if len(ports) != 1 or ports[0].get("host_ip") != "127.0.0.1" or str(ports[0].get("published")) != "0":
        raise ValueError("CI database must use a random loopback-only port")
    if config["services"]["flyway"].get("ports"):
        raise ValueError("Flyway must not publish host ports")

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--compose-file", type=Path, default=ROOT / "docker-compose.ci.yml")
    parser.add_argument("--project-name", default=os.getenv("COMPOSE_PROJECT_NAME", "mei-ci-0-0"))
    args = parser.parse_args()
    try:
        validate(args.compose_file, args.project_name)
    except (ValueError, OSError, subprocess.SubprocessError, KeyError, json.JSONDecodeError) as exc:
        print("CI_COMPOSE_ISOLATION=FAIL " + type(exc).__name__)
        return 1
    print("CI_COMPOSE_ISOLATION=PASS")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
