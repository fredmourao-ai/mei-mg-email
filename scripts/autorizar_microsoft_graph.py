from __future__ import annotations

from dotenv import load_dotenv

load_dotenv()

from app.email_provider import MicrosoftGraphEmailProvider


def main() -> None:
    provider = MicrosoftGraphEmailProvider()
    provider.authenticate()
    print("GRAPH_APP_ONLY_AUTH_OK")
    print("token_storage=memory_only")
    print(f"sender={provider.address}")


if __name__ == "__main__":
    main()
