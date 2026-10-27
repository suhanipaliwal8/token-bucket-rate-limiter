import threading
import time

import pytest

from app.algorithms.token_bucket import consume as real_consume
from app.client_config import ClientConfig
from app.store import InMemoryBucketStore

BURST = 10


@pytest.fixture
def slow_consume(monkeypatch):
    """Widen the race window so the bug shows up reliably instead of rarely."""

    def slow(*args, **kwargs):
        time.sleep(0.001)
        return real_consume(*args, **kwargs)

    monkeypatch.setattr("app.store.consume", slow)


def make_store(keys):
    store = InMemoryBucketStore()
    for key in keys:
        # a very slow refill rate, so refill can't affect the count
        store.set_config(ClientConfig(key, rate=0.001, burst=BURST))
    return store


def run_concurrent_checks(store, keys, threads_per_key):
    results = {key: [] for key in keys}  # list.append is safe across threads
    barrier = threading.Barrier(len(keys) * threads_per_key)

    def worker(key):
        barrier.wait()  # release every thread at the same moment
        results[key].append(store.check(key).allowed)

    threads = [
        threading.Thread(target=worker, args=(key,))
        for key in keys
        for _ in range(threads_per_key)
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    return {key: sum(outcomes) for key, outcomes in results.items()}


def test_same_key_tokens_are_not_double_spent(slow_consume):
    keys = ["race-one"]
    store = make_store(keys)
    allowed = run_concurrent_checks(store, keys, threads_per_key=100)
    assert allowed["race-one"] == BURST


def test_different_keys_do_not_interfere(slow_consume):
    keys = [f"race-multi-{i}" for i in range(5)]
    store = make_store(keys)
    allowed = run_concurrent_checks(store, keys, threads_per_key=40)
    assert all(count == BURST for count in allowed.values())