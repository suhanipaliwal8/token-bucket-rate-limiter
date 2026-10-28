from app import snapshots
from app.algorithms.sliding_window import WindowState
from app.client_config import ClientConfig
from app.store import InMemoryBucketStore


def test_window_roundtrip(client):
    state = WindowState((1000.0, 1001.5, 1002.25))
    snapshots.save_window_snapshot({"wsnap-test-1": state})
    assert snapshots.load_window_snapshot()["wsnap-test-1"] == state


def test_window_save_overwrites_previous_snapshot(client):
    snapshots.save_window_snapshot({"wsnap-test-2": WindowState((1.0, 2.0))})
    snapshots.save_window_snapshot({"wsnap-test-2": WindowState((3.0,))})
    assert snapshots.load_window_snapshot()["wsnap-test-2"] == WindowState((3.0,))


def test_restored_sliding_window_still_limits(client):
    key = "wsnap-test-3"
    client.put(
        f"/admin/clients/{key}",
        json={"rate": 0.01, "burst": 2, "algorithm": "sliding_window"},
    )

    before = InMemoryBucketStore()
    assert before.check(key).allowed
    assert before.check(key).allowed
    snapshots.save_window_snapshot(before.export_windows())

    after = InMemoryBucketStore()  # simulates a restarted service
    after.import_windows(snapshots.load_window_snapshot())
    assert not after.check(key).allowed  # window is 200 seconds long here


def test_worker_final_save_includes_windows(client):
    key = "wsnap-test-4"
    store = InMemoryBucketStore()
    store.set_config(
        ClientConfig(key, rate=0.01, burst=2, algorithm="sliding_window")
    )
    store.check(key)

    worker = snapshots.SnapshotWorker(store, interval=60)
    worker.start()
    worker.stop()  # stopping triggers the final save immediately

    assert key in snapshots.load_window_snapshot()