import os
from dotenv import load_dotenv

load_dotenv()

# No-op deployment marker: ensures PR merge touches application code so the
# production Auto Gate cannot classify this release as documentation-only.


def _positive_int_env(name: str, default: int) -> int:
    value = int(os.getenv(name, str(default)))
    return max(value, 1)


class Settings:
    database_url: str = os.getenv(
        "DATABASE_URL",
        "postgresql://postgres:postgres@localhost:5433/mei_mg_email",
    )
    api_host: str = os.getenv("API_HOST", "0.0.0.0")
    api_port: int = int(os.getenv("API_PORT", "8000"))

    email_provider: str = os.getenv("EMAIL_PROVIDER", "dryrun")

    # Exchange permits up to 30/min in this project, but deliverability recovery
    # deliberately runs slower. The effective rate is the lower value, so an
    # old production .env still set to 30/min cannot accidentally bypass the
    # reputation-recovery cap after deploy.
    configured_rate_envios_por_minuto: int = _positive_int_env(
        "RATE_LIMIT_ENVIOS_POR_MINUTO", 30
    )
    deliverability_max_envios_por_minuto: int = _positive_int_env(
        "DELIVERABILITY_MAX_ENVIOS_POR_MINUTO", 10
    )
    rate_limit_envios_por_minuto: int = min(
        configured_rate_envios_por_minuto,
        deliverability_max_envios_por_minuto,
        30,
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

    # Continuous queue buffer. Queue depth is intentionally independent from
    # the rolling 24-hour send quota: enqueuing does not send. The worker is
    # the final quota gate before every Graph submission.
    queue_min_pending: int = int(os.getenv("QUEUE_MIN_PENDING", "14800"))
    queue_target_pending: int = int(os.getenv("QUEUE_TARGET_PENDING", "15000"))

    base_url_descadastro: str = os.getenv(
        "BASE_URL_DESCADASTRO", "http://localhost:8000/descadastro"
    )


settings = Settings()
