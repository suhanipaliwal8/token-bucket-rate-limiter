from dataclasses import dataclass


@dataclass(frozen=True)
class WindowState:
    timestamps: tuple[float, ...] = ()  # times of allowed requests, oldest first


@dataclass(frozen=True)
class WindowDecision:
    allowed: bool
    state: WindowState
    remaining: int
    retry_after: float   # seconds until a request would be allowed (0 if allowed)
    reset_after: float   # seconds until the window is completely empty


def consume_window(
    state: WindowState, limit: int, window: float, now: float, cost: int = 1
) -> WindowDecision:
    if cost > limit:
        raise ValueError("cost exceeds the window limit")
    cutoff = now - window
    recent = tuple(t for t in state.timestamps if t > cutoff)

    if len(recent) + cost <= limit:
        recent = recent + (now,) * cost
        allowed = True
        retry_after = 0.0
    else:
        allowed = False
        # this many of the oldest requests must leave the window first
        needed = len(recent) + cost - limit
        retry_after = recent[needed - 1] + window - now

    return WindowDecision(
        allowed=allowed,
        state=WindowState(recent),
        remaining=max(0, limit - len(recent)),
        retry_after=retry_after,
        reset_after=(recent[-1] + window - now) if recent else 0.0,
    )