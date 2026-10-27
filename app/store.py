import threading
import time

from app import client_config
from app.algorithms.token_bucket import BucketState, Decision, consume
from app.client_config import ClientConfig

DEFAULT_RATE = 5.0   # tokens per second
DEFAULT_BURST = 10   # bucket capacity


class InMemoryBucketStore:
    def __init__(self) -> None:
        self._buckets: dict[str, BucketState] = {}
        self._configs: dict[str, ClientConfig] = {}
        self._key_locks: dict[str, threading.Lock] = {}
        # _guard protects the three dictionaries above. It is held only for
        # microseconds, and never while calling the database.
        self._guard = threading.Lock()

    def _key_lock(self, client_key: str) -> threading.Lock:
        with self._guard:
            lock = self._key_locks.get(client_key)
            if lock is None:
                lock = self._key_locks[client_key] = threading.Lock()
            return lock

    def _get_config(self, client_key: str) -> ClientConfig:
        with self._guard:
            cfg = self._configs.get(client_key)
        if cfg is not None:
            return cfg
        loaded = client_config.get(client_key) or ClientConfig(
            client_key, DEFAULT_RATE, DEFAULT_BURST
        )
        with self._guard:
            # setdefault keeps a newer config that an admin call stored
            # while we were reading the database
            return self._configs.setdefault(client_key, loaded)

    def set_config(self, cfg: ClientConfig) -> None:
        with self._guard:
            self._configs[cfg.client_key] = cfg

    def remove_config(self, client_key: str) -> None:
        with self._guard:
            self._configs.pop(client_key, None)

    def check(self, client_key: str) -> Decision:
        cfg = self._get_config(client_key)
        with self._key_lock(client_key):
            now = time.time()  # taken inside the lock, so time never goes backwards
            with self._guard:
                state = self._buckets.get(client_key)
            if state is None:
                state = BucketState(tokens=cfg.burst, last_refill=now)
            decision = consume(state, cfg.rate, cfg.burst, now)
            with self._guard:
                self._buckets[client_key] = decision.state
        return decision

    def export_buckets(self) -> dict[str, BucketState]:
        with self._guard:
            return self._buckets.copy()

    def import_buckets(self, buckets: dict[str, BucketState]) -> None:
        with self._guard:
            self._buckets.update(buckets)