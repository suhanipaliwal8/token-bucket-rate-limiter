from app import snapshots
from app.algorithms.token_bucket import BucketState
from app.store import InMemoryBucketStore


def test_save_and_load_roundtrip(client):
    state = BucketState(tokens=2.5, last_refill=1000.0)
    snapshots.save_snapshot({"snap-test-1": state})
    assert snapshots.load_snapshot()["snap-test-1"] == state


def test_save_overwrites_previous_snapshot(client):
    snapshots.save_snapshot({"snap-test-2": BucketState(3.0, 1000.0)})
    snapshots.save_snapshot({"snap-test-2": BucketState(1.0, 2000.0)})
    assert snapshots.load_snapshot()["snap-test-2"] == BucketState(1.0, 2000.0)


def test_restored_store_continues_from_saved_state(client):
    key = "snap-test-3"
    client.put(f"/admin/clients/{key}", json={"rate": 0.01, "burst": 2})

    before = InMemoryBucketStore()
    assert before.check(key).allowed
    assert before.check(key).allowed
    snapshots.save_snapshot(before.export_buckets())

    after = InMemoryBucketStore()  # simulates a restarted service
    after.import_buckets(snapshots.load_snapshot())
    assert not after.check(key).allowed