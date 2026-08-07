from __future__ import annotations

import sys
import time
import webbrowser
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))
load_dotenv(BASE_DIR / ".env")

from app.email_provider import MicrosoftGraphEmailProvider


def main() -> None:
    provider = MicrosoftGraphEmailProvider()
    device = provider._post_form(
        f"{provider._authority}/oauth2/v2.0/devicecode",
        {"client_id": provider.client_id, "scope": provider._scope},
    )

    verification_uri = device.get("verification_uri") or "https://microsoft.com/devicelogin"
    user_code = device.get("user_code") or ""
    if not user_code:
        raise SystemExit("GRAPH_DEVICE_AUTH_ERROR: codigo de dispositivo ausente")

    print("GRAPH_DEVICE_AUTH_STARTED", flush=True)
    print(f"sender={provider.address}", flush=True)
    print(f"verification_uri={verification_uri}", flush=True)
    print(f"user_code={user_code}", flush=True)

    # Open only the generic Microsoft device-login page. The user enters the
    # short-lived device code there; no password, MFA code or token is logged.
    webbrowser.open(verification_uri, new=1, autoraise=True)

    deadline = time.time() + int(device.get("expires_in", 900))
    interval = max(int(device.get("interval", 5)), 2)
    while time.time() < deadline:
        time.sleep(interval)
        try:
            response = provider._post_form(
                f"{provider._authority}/oauth2/v2.0/token",
                {
                    "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
                    "client_id": provider.client_id,
                    "device_code": device["device_code"],
                },
            )
        except RuntimeError as error:
            text = str(error)
            if "authorization_pending" in text:
                continue
            if "slow_down" in text:
                interval += 5
                continue
            raise SystemExit("GRAPH_DEVICE_AUTH_ERROR: " + text)

        provider._store_token(response)
        print("GRAPH_BROWSER_AUTH_READY", flush=True)
        print("token_value=REDACTED", flush=True)
        return

    raise SystemExit("GRAPH_DEVICE_AUTH_TIMEOUT")


if __name__ == "__main__":
    main()
