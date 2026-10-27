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

    def _get_config(self, client_key: str) -> ClientConfig:
        cfg = self._configs.get(client_key)
        if cfg is None:
            cfg = client_config.get(client_key) or ClientConfig(
                client_key, DEFAULT_RATE, DEFAULT_BURST
            )
            self._configs[client_key] = cfg
        return cfg

    def set_config(self, cfg: ClientConfig) -> None:
        self._configs[cfg.client_key] = cfg

    def check(self, client_key: str) -> Decision:
        cfg = self._get_config(client_key)
        now = time.time()
        state = self._buckets.get(
            client_key, BucketState(tokens=cfg.burst, last_refill=now)
        )
        decision = consume(state, cfg.rate, cfg.burst, now)
        self._buckets[client_key] = decision.state
        return decision

    def export_buckets(self) -> dict[str, BucketState]:
        return self._buckets.copy()

    def import_buckets(self, buckets: dict[str, BucketState]) -> None:
        self._buckets.update(buckets)