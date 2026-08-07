import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    database_url: str = os.getenv(
        "DATABASE_URL",
        "postgresql://postgres:postgres@localhost:5433/mei_mg_email",
    )
    api_host: str = os.getenv("API_HOST", "0.0.0.0")
    api_port: int = int(os.getenv("API_PORT", "8000"))

    email_provider: str = os.getenv("EMAIL_PROVIDER", "dryrun")
    # Exchange Online service limit is 30 messages/minute. Keep a margin by
    # default so temporary throttling and other mailbox activity do not cause
    # avoidable failures.
    rate_limit_envios_por_minuto: int = int(
        os.getenv("RATE_LIMIT_ENVIOS_POR_MINUTO", "20")
    )
    # Exchange Online recipient rate limit is 10,000 recipients in a rolling
    # 24-hour window. This is a hard ceiling, not a guarantee of deliverability.
    max_envios_por_dia: int = int(
        os.getenv("MAX_ENVIOS_POR_DIA", "10000")
    )
    worker_poll_interval_segundos: int = int(
        os.getenv("WORKER_POLL_INTERVAL_SEGUNDOS", "5")
    )

    base_url_descadastro: str = os.getenv(
        "BASE_URL_DESCADASTRO", "http://localhost:8000/descadastro"
    )


settings = Settings()
