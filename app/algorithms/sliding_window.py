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
    state: WindowState, limit: int, window: float, now: float
) -> WindowDecision:
    cutoff = now - window
    recent = tuple(t for t in state.timestamps if t > cutoff)

    if len(recent) < limit:
        recent = recent + (now,)
        allowed = True
        retry_after = 0.0
    else:
        allowed = False
        # the oldest request leaves the window at recent[0] + window
        retry_after = recent[0] + window - now

    return WindowDecision(
        allowed=allowed,
        state=WindowState(recent),
        remaining=max(0, limit - len(recent)),
        retry_after=retry_after,
        reset_after=(recent[-1] + window - now) if recent else 0.0,
    )