from dataclasses import dataclass

from app.db import pool


@dataclass(frozen=True)
class ClientConfig:
    client_key: str
    rate: float
    burst: int
    algorithm: str = "token_bucket"


def upsert(
    client_key: str, rate: float, burst: int, algorithm: str = "token_bucket"
) -> ClientConfig:
    with pool.connection() as conn:
        conn.execute(
            """
            INSERT INTO client_config (client_key, rate, burst, algorithm)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (client_key)
            DO UPDATE SET rate = EXCLUDED.rate,
                          burst = EXCLUDED.burst,
                          algorithm = EXCLUDED.algorithm,
                          updated_at = now()
            """,
            (client_key, rate, burst, algorithm),
        )
    return ClientConfig(client_key, rate, burst, algorithm)


def get(client_key: str) -> ClientConfig | None:
    with pool.connection() as conn:
        row = conn.execute(
            "SELECT client_key, rate, burst, algorithm "
            "FROM client_config WHERE client_key = %s",
            (client_key,),
        ).fetchone()
    return ClientConfig(*row) if row else None


def delete(client_key: str) -> bool:
    with pool.connection() as conn:
        cur = conn.execute(
            "DELETE FROM client_config WHERE client_key = %s", (client_key,)
        )
        return cur.rowcount > 0