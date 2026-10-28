import pytest

from app.algorithms.sliding_window import WindowState, consume_window
from app.algorithms.token_bucket import BucketState, consume


def test_token_bucket_cost_spends_multiple_tokens():
    d = consume(BucketState(5, 0.0), rate=1, burst=5, now=0.0, cost=3)
    assert d.allowed and d.remaining == 2


def test_token_bucket_denies_when_cost_exceeds_tokens():
    d = consume(BucketState(2, 0.0), rate=1, burst=5, now=0.0, cost=3)
    assert not d.allowed
    assert d.retry_after == pytest.approx(1.0)  # needs one more token


def test_sliding_window_cost_records_multiple_entries():
    d = consume_window(WindowState(), limit=5, window=10.0, now=1.0, cost=3)
    assert d.allowed and d.remaining == 2
    assert d.state.timestamps == (1.0, 1.0, 1.0)


def test_sliding_window_denies_when_cost_does_not_fit():
    state = WindowState((0.0, 1.0, 2.0))
    d = consume_window(state, limit=5, window=10.0, now=3.0, cost=4)  # 3 + 4 > 5
    assert not d.allowed
    assert d.retry_after == pytest.approx(8.0)  # two must leave; the 2nd oldest (t=1) leaves at 11


def test_sliding_window_rejects_cost_above_limit():
    with pytest.raises(ValueError):
        consume_window(WindowState(), limit=5, window=10.0, now=0.0, cost=6)