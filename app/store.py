import time

from app.algorithms.token_bucket import BucketState, Decision, consume

DEFAULT_RATE = 5.0   # tokens per second
DEFAULT_BURST = 10   # bucket capacity


class InMemoryBucketStore:
    def __init__(self) -> None:
        self._buckets: dict[str, BucketState] = {}

    def check(self, client_key: str) -> Decision:
        now = time.time()
        state = self._buckets.get(
            client_key, BucketState(tokens=DEFAULT_BURST, last_refill=now)
        )
        decision = consume(state, DEFAULT_RATE, DEFAULT_BURST, now)
        self._buckets[client_key] = decision.state
        return decision