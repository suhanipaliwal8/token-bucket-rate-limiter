from app.algorithms.sliding_window import WindowState
from app.algorithms.token_bucket import BucketState


def bucket_is_full(state: BucketState, rate: float, burst: int, now: float) -> bool:
    """True once the bucket has refilled completely, so it equals a brand-new bucket."""
    elapsed = max(0.0, now - state.last_refill)
    return state.tokens + elapsed * rate >= burst


def window_is_empty(state: WindowState, window: float, now: float) -> bool:
    """True once every recorded request has left the window."""
    return all(t <= now - window for t in state.timestamps)