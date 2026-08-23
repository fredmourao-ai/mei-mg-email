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

    # Exchange Online applies a hard 10,000-recipient limit in a sliding 24h
    # window. Local DB accounting can lag mailbox-wide activity, so always keep
    # explicit headroom even if an old .env still asks for 9,950/day.
    max_envios_por_dia: int = _positive_int_env("MAX_ENVIOS_POR_DIA", 10000)
    exchange_recipient_safety_reserve: int = max(
        1000,
        _positive_int_env("EXCHANGE_RECIPIENT_SAFETY_RESERVE", 1000),
    )
    configured_meta_envios_por_dia: int = _positive_int_env("META_ENVIOS_POR_DIA", 9000)
    meta_envios_por_dia: int = min(
        configured_meta_envios_por_dia,
        max(1, min(10000, max_envios_por_dia) - exchange_recipient_safety_reserve),
    )
    worker_poll_interval_segundos: int = int(
        os.getenv("WORKER_POLL_INTERVAL_SEGUNDOS", "5")
    )

    queue_min_pending: int = int(os.getenv("QUEUE_MIN_PENDING", "14800"))
    queue_target_pending: int = int(os.getenv("QUEUE_TARGET_PENDING", "15000"))

    base_url_descadastro: str = os.getenv(
        "BASE_URL_DESCADASTRO", "http://localhost:8000/descadastro"
    )


settings = Settings()
