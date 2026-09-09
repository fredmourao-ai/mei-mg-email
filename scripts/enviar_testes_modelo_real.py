#!/usr/bin/env python3
"""Retired Microsoft Graph send entrypoint.

Production sending is Brevo-only. Use ``scripts/enviar_teste_brevo.py`` for the
current controlled delivery test, which records the external quota ledger and
requires provider delivery evidence.
"""


def main() -> int:
    print("RETIRED_MICROSOFT_GRAPH_SEND_ENTRYPOINT=true")
    print("USE=scripts/enviar_teste_brevo.py")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
