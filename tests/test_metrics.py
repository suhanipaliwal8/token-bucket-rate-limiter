import pytest

from app.metrics import Metrics


def test_counts_allowed_and_denied_per_client():
    m = Metrics()
    m.record("a", True, now=100.0)
    m.record("a", True, now=100.5)
    m.record("a", False, now=101.0)
    row = m.snapshot(now=102.0)["clients"][0]
    assert row["client_key"] == "a"
    assert row["allowed_60s"] == 2 and row["denied_60s"] == 1
    assert row["deny_rate_60s"] == pytest.approx(0.333, abs=0.001)


def test_old_traffic_leaves_the_window():
    m = Metrics()
    m.record("a", True, now=100.0)
    assert m.snapshot(now=161.0)["clients"] == []


def test_ten_second_rates():
    m = Metrics()
    for i in range(20):
        m.record("a", False, now=100.0 + i * 0.1)  # 20 denials within 2 seconds
    row = m.snapshot(now=102.0)["clients"][0]
    assert row["denied_per_sec_10s"] == 2.0


def test_busiest_clients_come_first():
    m = Metrics()
    m.record("quiet", True, now=100.0)
    for _ in range(5):
        m.record("busy", True, now=100.0)
    keys = [c["client_key"] for c in m.snapshot(now=101.0)["clients"]]
    assert keys == ["busy", "quiet"]


def test_idle_clients_are_forgotten():
    m = Metrics()
    m.record("a", True, now=100.0)
    assert m.snapshot(now=200.0)["tracked_clients"] == 0