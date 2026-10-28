import pytest

from app.algorithms.sliding_window import WindowState, consume_window


def test_allows_up_to_limit_then_denies():
    state = WindowState()
    for i in range(3):
        d = consume_window(state, limit=3, window=10.0, now=float(i))
        assert d.allowed
        state = d.state
    d = consume_window(state, limit=3, window=10.0, now=3.0)
    assert not d.allowed
    assert d.remaining == 0
    assert d.retry_after == pytest.approx(7.0)  # the t=0 request leaves at t=10


def test_old_requests_expire():
    state = WindowState((0.0, 1.0, 2.0))
    d = consume_window(state, limit=3, window=10.0, now=10.5)  # t=0.0 has expired
    assert d.allowed
    assert d.state.timestamps == (1.0, 2.0, 10.5)


def test_denied_requests_are_not_recorded():
    state = WindowState((0.0, 1.0))
    d = consume_window(state, limit=2, window=10.0, now=2.0)
    assert not d.allowed
    assert d.state.timestamps == (0.0, 1.0)


def test_no_double_burst_across_a_boundary():
    state = WindowState()
    for _ in range(5):
        d = consume_window(state, limit=5, window=10.0, now=9.9)
        assert d.allowed
        state = d.state
    # a fixed-window counter that resets at t=10 would allow this one
    d = consume_window(state, limit=5, window=10.0, now=10.1)
    assert not d.allowed