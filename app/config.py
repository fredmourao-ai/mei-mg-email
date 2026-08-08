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
    # Operational limit required for this sender. The worker still enforces
    # provider backoff/retry handling and the rolling 24-hour ceiling.
    rate_limit_envios_por_minuto: int = int(
        os.getenv("RATE_LIMIT_ENVIOS_POR_MINUTO", "30")
    )
    # Hard local ceiling for a rolling 24-hour window. This remains separate
    # from the operational target so there is always explicit safety margin.
    max_envios_por_dia: int = int(
        os.getenv("MAX_ENVIOS_POR_DIA", "10000")
    )
    meta_envios_por_dia: int = int(
        os.getenv("META_ENVIOS_POR_DIA", "9950")
    )
    worker_poll_interval_segundos: int = int(
        os.getenv("WORKER_POLL_INTERVAL_SEGUNDOS", "5")
    )

    base_url_descadastro: str = os.getenv(
        "BASE_URL_DESCADASTRO", "http://localhost:8000/descadastro"
    )


settings = Settings()
