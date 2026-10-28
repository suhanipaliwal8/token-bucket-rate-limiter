from dataclasses import dataclass
import threading
import time

from app import client_config
from app.algorithms.sliding_window import WindowDecision, WindowState, consume_window
from app.algorithms.token_bucket import BucketState, Decision, consume
from app.client_config import ClientConfig
from app.algorithms.idle import bucket_is_full, window_is_empty
from app.errors import CostExceedsLimit

DEFAULT_RATE = 5.0   # tokens per second
DEFAULT_BURST = 10   # bucket capacity
LOCK_STRIPES = 256   # size of the shared lock pool

@dataclass(frozen=True)
class CheckResult:
    allowed: bool
    limit: int          # max requests the client may make (burst / window limit)
    remaining: int
    retry_after: float  # seconds until a request would be allowed (0 if allowed)
    reset_after: float  # seconds until the limit is fully restored
    reset_at: float     # the same moment as a unix timestamp

class InMemoryBucketStore:
    def __init__(self) -> None:
        self._buckets: dict[str, BucketState] = {}
        self._windows: dict[str, WindowState] = {}
        self._configs: dict[str, ClientConfig] = {}
        self._stripes = [threading.Lock() for _ in range(LOCK_STRIPES)]
        # _guard protects the dictionaries above. It is held only for
        # microseconds, and never while calling the database.
        self._guard = threading.Lock()

    def _key_lock(self, client_key: str) -> threading.Lock:
        # A fixed pool of locks shared by all keys ("lock striping"). Two keys may
        # occasionally share a lock, which is harmless, and no lock object ever has
        # to be created or deleted per client.
        return self._stripes[hash(client_key) % LOCK_STRIPES]

    def _get_config(self, client_key: str) -> ClientConfig:
        with self._guard:
            cfg = self._configs.get(client_key)
        if cfg is not None:
            return cfg
        loaded = client_config.get(client_key) or ClientConfig(
            client_key, DEFAULT_RATE, DEFAULT_BURST
        )
        with self._guard:
            return self._configs.setdefault(client_key, loaded)

    def set_config(self, cfg: ClientConfig) -> None:
        with self._guard:
            self._configs[cfg.client_key] = cfg

    def remove_config(self, client_key: str) -> None:
        with self._guard:
            self._configs.pop(client_key, None)

    def check(self, client_key: str, cost: int = 1) -> CheckResult:
        cfg = self._get_config(client_key)
        if cost > cfg.burst:
            raise CostExceedsLimit(cost, cfg.burst)
        with self._key_lock(client_key):
            now = time.time()  # taken inside the lock, so time never goes backwards
            if cfg.algorithm == "sliding_window":
                decision = self._check_window(client_key, cfg, now, cost)
            else:
                decision = self._check_bucket(client_key, cfg, now, cost)
        return CheckResult(
            allowed=decision.allowed,
            limit=cfg.burst,
            remaining=decision.remaining,
            retry_after=decision.retry_after,
            reset_after=decision.reset_after,
            reset_at=now + decision.reset_after,
        )

    def _check_bucket(
        self, client_key: str, cfg: ClientConfig, now: float, cost: int
    ) -> Decision:
        with self._guard:
            state = self._buckets.get(client_key)
        if state is None:
            state = BucketState(tokens=cfg.burst, last_refill=now)
        decision = consume(state, cfg.rate, cfg.burst, now, cost)
        with self._guard:
            self._buckets[client_key] = decision.state
        return decision

    def _check_window(
        self, client_key: str, cfg: ClientConfig, now: float, cost: int
    ) -> WindowDecision:
        with self._guard:
            state = self._windows.get(client_key, WindowState())
        window = cfg.burst / cfg.rate  # limit = burst, window length = burst / rate
        decision = consume_window(state, cfg.burst, window, now, cost)
        with self._guard:
            self._windows[client_key] = decision.state
        return decision
    
    def export_buckets(self) -> dict[str, BucketState]:
        with self._guard:
            return self._buckets.copy()

    def import_buckets(self, buckets: dict[str, BucketState]) -> None:
        with self._guard:
            self._buckets.update(buckets)

    def export_windows(self) -> dict[str, WindowState]:
        with self._guard:
            return self._windows.copy()

    def import_windows(self, windows: dict[str, WindowState]) -> None:
        with self._guard:
            self._windows.update(windows)

    def evict_idle(self, now: float | None = None) -> tuple[list[str], list[str]]:
        """Drop state identical to a brand-new client's state.

        Returns (evicted bucket keys, evicted window keys)."""
        now = time.time() if now is None else now
        with self._guard:
            bucket_items = list(self._buckets.items())
            window_items = list(self._windows.items())

        evicted_buckets: list[str] = []
        for key, state in bucket_items:
            cfg = self._get_config(key)  # cached; hits the database only for restored keys
            if bucket_is_full(state, cfg.rate, cfg.burst, now):
                with self._guard:
                    if self._buckets.get(key) is state:  # unchanged since we looked
                        del self._buckets[key]
                        evicted_buckets.append(key)

        evicted_windows: list[str] = []
        for key, state in window_items:
            cfg = self._get_config(key)
            if window_is_empty(state, cfg.burst / cfg.rate, now):
                with self._guard:
                    if self._windows.get(key) is state:
                        del self._windows[key]
                        evicted_windows.append(key)

        # forget cached configs of clients with no state left (reloaded on demand)
        with self._guard:
            for key in evicted_buckets + evicted_windows:
                if key not in self._buckets and key not in self._windows:
                    self._configs.pop(key, None)
        return evicted_buckets, evicted_windows