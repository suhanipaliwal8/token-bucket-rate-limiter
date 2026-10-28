from app.algorithms.idle import bucket_is_full, window_is_empty
from app.algorithms.sliding_window import WindowState
from app.algorithms.token_bucket import BucketState


def test_bucket_is_full_after_enough_time():
    state = BucketState(tokens=0.0, last_refill=100.0)
    assert not bucket_is_full(state, rate=2, burst=10, now=104.9)  # 9.8 tokens
    assert bucket_is_full(state, rate=2, burst=10, now=105.0)      # exactly 10


def test_window_is_empty_after_the_window_passes():
    state = WindowState((100.0, 101.0))
    assert not window_is_empty(state, window=5.0, now=105.5)  # 101.0 still inside
    assert window_is_empty(state, window=5.0, now=106.0)