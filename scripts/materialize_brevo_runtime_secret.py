#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import shutil
import socket
import time
from pathlib import Path

EXPECTED_HOSTNAME = "always-free-arm-1787907847-26"
DEFAULT_ENV_PATH = Path("/home/ubuntu/mei-mg-email/.env")
BACKUP_DIR = Path("/home/ubuntu/.shopvivaliz/backups/mei-mg-email")

CUTOVER_VALUES = {
    "EMAIL_PROVIDER": "brevo",
    "MAX_ENVIOS_POR_DIA": "300",
    "META_ENVIOS_POR_DIA": "295",
    "RATE_LIMIT_ENVIOS_POR_MINUTO": "10",
    "DELIVERABILITY_MAX_ENVIOS_POR_MINUTO": "10",
    "MAIL_FROM": "Contabilidade Melo <atendimento@shopvivaliz.com.br>",
    "MAIL_FROM_NAME": "Contabilidade Melo",
    "MONITOR_BREVO_RECONCILER_UNIT": "mei-mg-email-brevo-reconciler.service",
    "TEST_RECIPIENT": "atendimento@shopvivaliz.com.br",
}


def _replace_values(lines: list[str], values: dict[str, str]) -> list[str]:
    remaining = dict(values)
    output: list[str] = []
    for line in lines:
        if "=" in line and not line.lstrip().startswith("#"):
            key = line.split("=", 1)[0].strip()
            if key in remaining:
                output.append(f"{key}={remaining.pop(key)}")
                continue
        output.append(line)
    for key, value in remaining.items():
        output.append(f"{key}={value}")
    return output


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("secret_only", "cutover"), required=True)
    parser.add_argument("--env-path", type=Path, default=DEFAULT_ENV_PATH)
    args = parser.parse_args()

    if socket.gethostname() != EXPECTED_HOSTNAME:
        raise RuntimeError(
            f"refusing runtime mutation outside {EXPECTED_HOSTNAME}: {socket.gethostname()}"
        )

    api_key = os.getenv("BREVO_API_KEY", "").strip()
    if len(api_key) < 20:
        raise RuntimeError("BREVO_API_KEY missing or invalid")
    if not args.env_path.is_file():
        raise RuntimeError(f"runtime env not found: {args.env_path}")

    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    backup = BACKUP_DIR / f"env-before-brevo-key-{stamp}"
    shutil.copy2(args.env_path, backup)

    values = {"BREVO_API_KEY": api_key}
    if args.mode == "cutover":
        values.update(CUTOVER_VALUES)

    lines = args.env_path.read_text(encoding="utf-8").splitlines()
    output = _replace_values(lines, values)
    tmp = args.env_path.with_name(args.env_path.name + ".brevo-runtime.tmp")
    tmp.write_text("\n".join(output) + "\n", encoding="utf-8")
    os.chmod(tmp, 0o600)
    tmp.replace(args.env_path)

    print(f"backend_brevo_key_present=true length={len(api_key)}")
    print(f"mode={args.mode}")
    print(f"backup={backup}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
