from psycopg_pool import ConnectionPool
from app.config import settings

# Pool pequeno de proposito: isso e uma API de controle (criar campanha,
# consultar status), nao o caminho quente do envio em si. O worker abre sua
# propria conexao separada (ver worker/worker.py).
pool = ConnectionPool(conninfo=settings.database_url, min_size=1, max_size=5, open=False)


def get_pool() -> ConnectionPool:
    if pool.closed:
        pool.open()
    return pool
