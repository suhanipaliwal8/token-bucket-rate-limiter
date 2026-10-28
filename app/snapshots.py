import logging
import threading

from app.algorithms.sliding_window import WindowState
from app.algorithms.token_bucket import BucketState
from app.db import pool

logger = logging.getLogger(__name__)

SNAPSHOT_INTERVAL_SECONDS = 5.0


def save_snapshot(buckets: dict[str, BucketState]) -> None:
    if not buckets:
        return
    rows = [(key, s.tokens, s.last_refill) for key, s in buckets.items()]
    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.executemany(
                """
                INSERT INTO bucket_state (client_key, tokens, last_refill)
                VALUES (%s, %s, %s)
                ON CONFLICT (client_key)
                DO UPDATE SET tokens = EXCLUDED.tokens,
                              last_refill = EXCLUDED.last_refill,
                              updated_at = now()
                """,
                rows,
            )


def load_snapshot() -> dict[str, BucketState]:
    with pool.connection() as conn:
        rows = conn.execute(
            "SELECT client_key, tokens, last_refill FROM bucket_state"
        ).fetchall()
    return {key: BucketState(tokens=t, last_refill=lr) for key, t, lr in rows}


def save_window_snapshot(windows: dict[str, WindowState]) -> None:
    if not windows:
        return
    rows = [(key, list(w.timestamps)) for key, w in windows.items()]
    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.executemany(
                """
                INSERT INTO window_state (client_key, timestamps)
                VALUES (%s, %s)
                ON CONFLICT (client_key)
                DO UPDATE SET timestamps = EXCLUDED.timestamps,
                              updated_at = now()
                """,
                rows,
            )


def load_window_snapshot() -> dict[str, WindowState]:
    with pool.connection() as conn:
        rows = conn.execute("SELECT client_key, timestamps FROM window_state").fetchall()
    return {key: WindowState(tuple(ts)) for key, ts in rows}


class SnapshotWorker:
    def __init__(self, store, interval: float = SNAPSHOT_INTERVAL_SECONDS) -> None:
        self._store = store
        self._interval = interval
        self._stop_event = threading.Event()
        self._thread = threading.Thread(
            target=self._run, name="snapshot-worker", daemon=True
        )

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        self._thread.join()
        self._save_all()  # final save on shutdown

    def _save_all(self) -> None:
        save_snapshot(self._store.export_buckets())
        save_window_snapshot(self._store.export_windows())

    def _run(self) -> None:
        # wait() returns True when stop is requested, ending the loop
        while not self._stop_event.wait(self._interval):
            try:
                self._save_all()
            except Exception:
                logger.exception("snapshot failed; will retry next interval")