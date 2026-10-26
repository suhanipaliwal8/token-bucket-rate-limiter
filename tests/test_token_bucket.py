import pytest
from app.algorithms.token_bucket import BucketState, consume


def test_burst_then_deny():
    state = BucketState(tokens=5, last_refill=0.0)
    for _ in range(5):
        d = consume(state, rate=1, burst=5, now=0.0)
        assert d.allowed
        state = d.state
    d = consume(state, rate=1, burst=5, now=0.0)
    assert not d.allowed
    assert d.retry_after == pytest.approx(1.0)


def test_refill_over_time():
    state = BucketState(tokens=0, last_refill=0.0)
    d = consume(state, rate=2, burst=5, now=1.0)  # 2 tokens refilled, 1 spent
    assert d.allowed
    assert d.remaining == 1


def test_refill_is_capped_at_burst():
    state = BucketState(tokens=0, last_refill=0.0)
    d = consume(state, rate=10, burst=5, now=100.0)
    assert d.remaining == 4  # capped at 5, then 1 spent