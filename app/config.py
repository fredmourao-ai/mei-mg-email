import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    database_url: str = os.getenv(
        "DATABASE_URL",
        "postgresql://postgres:postgres_local_dev_change_me@localhost:5433/mei_mg_email",
    )
    api_host: str = os.getenv("API_HOST", "0.0.0.0")
    api_port: int = int(os.getenv("API_PORT", "8000"))

    email_provider: str = os.getenv("EMAIL_PROVIDER", "dryrun")
    rate_limit_envios_por_minuto: int = int(
        os.getenv("RATE_LIMIT_ENVIOS_POR_MINUTO", "60")
    )
    worker_poll_interval_segundos: int = int(
        os.getenv("WORKER_POLL_INTERVAL_SEGUNDOS", "5")
    )

    base_url_descadastro: str = os.getenv(
        "BASE_URL_DESCADASTRO", "http://localhost:8000/descadastro"
    )


settings = Settings()
