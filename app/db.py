from psycopg_pool import ConnectionPool

from app.config import settings

pool = ConnectionPool(settings.database_url, min_size=1, max_size=10, open=False)

SCHEMA = """
CREATE TABLE IF NOT EXISTS client_config (
    client_key TEXT PRIMARY KEY,
    rate       DOUBLE PRECISION NOT NULL CHECK (rate > 0),
    burst      INTEGER NOT NULL CHECK (burst > 0),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
"""


def init_db() -> None:
    pool.open()
    with pool.connection() as conn:
        conn.execute(SCHEMA)


def close_db() -> None:
    pool.close()