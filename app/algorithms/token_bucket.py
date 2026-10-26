from dataclasses import dataclass


@dataclass(frozen=True)
class BucketState:
    tokens: float
    last_refill: float  # unix timestamp in seconds


@dataclass(frozen=True)
class Decision:
    allowed: bool
    state: BucketState      # new state to be saved
    remaining: int          # whole tokens left
    retry_after: float      # seconds until a request would be allowed (0 if allowed)
    reset_after: float      # seconds until the bucket is completely full


def consume(state: BucketState, rate: float, burst: int, now: float, cost: int = 1) -> Decision:
    elapsed = max(0.0, now - state.last_refill)  # guard against the clock going backwards
    tokens = min(float(burst), state.tokens + elapsed * rate)

    if tokens >= cost:
        tokens -= cost
        allowed = True
        retry_after = 0.0
    else:
        allowed = False
        retry_after = (cost - tokens) / rate

    return Decision(
        allowed=allowed,
        state=BucketState(tokens=tokens, last_refill=now),
        remaining=int(tokens),
        retry_after=retry_after,
        reset_after=(burst - tokens) / rate,
    )