import time

from app import snapshots
from app.client_config import ClientConfig
from app.store import InMemoryBucketStore


def make_store(**config):
    store = InMemoryBucketStore()
    store.set_config(ClientConfig("evict-a", **config))
    return store


def test_idle_bucket_is_evicted_only_once_it_has_refilled():
    store = make_store(rate=1, burst=3)
    store.check("evict-a")  # 2 tokens left; full again after about 1 second
    assert store.evict_idle(now=time.time()) == ([], [])
    buckets, windows = store.evict_idle(now=time.time() + 2)
    assert buckets == ["evict-a"] and windows == []
    assert store.export_buckets() == {}


def test_idle_window_is_evicted_once_the_window_has_passed():
    store = make_store(rate=1, burst=3, algorithm="sliding_window")
    store.check("evict-a")  # the window is 3 seconds long
    assert store.evict_idle(now=time.time()) == ([], [])
    buckets, windows = store.evict_idle(now=time.time() + 4)
    assert windows == ["evict-a"] and buckets == []


def test_evicted_client_starts_fresh_with_a_full_bucket(client):
    key = "evict-fresh"
    client.put(f"/admin/clients/{key}", json={"rate": 1000, "burst": 2})
    store = InMemoryBucketStore()
    store.check(key)
    store.check(key)  # drained
    time.sleep(0.05)  # refills completely
    store.evict_idle()
    assert store.check(key).remaining == 1  # a new bucket of 2, minus this request


def test_worker_evicts_idle_clients_and_deletes_their_rows(client):
    key = "evict-db-1"
    store = InMemoryBucketStore()
    store.set_config(ClientConfig(key, rate=1000, burst=1))  # refills in 1 ms
    store.check(key)
    snapshots.save_snapshot(store.export_buckets())
    assert key in snapshots.load_snapshot()

    time.sleep(0.05)
    worker = snapshots.SnapshotWorker(store, interval=60, evict_every=1)
    worker.run_once()

    assert key not in store.export_buckets()
    assert key not in snapshots.load_snapshot()