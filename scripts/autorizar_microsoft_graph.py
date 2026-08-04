from __future__ import annotations

from dotenv import load_dotenv

load_dotenv()

from app.email_provider import MicrosoftGraphEmailProvider


def main() -> None:
    provider = MicrosoftGraphEmailProvider()
    provider.authenticate()
    print("OAuth Microsoft Graph autorizado e cache local salvo com seguranca.")


if __name__ == "__main__":
    main()


