import math

from app.store import CheckResult


def rate_limit_headers(result: CheckResult) -> dict[str, str]:
    headers = {
        "X-RateLimit-Limit": str(result.limit),
        "X-RateLimit-Remaining": str(result.remaining),
        "X-RateLimit-Reset": str(math.ceil(result.reset_at)),
    }
    if not result.allowed:
        headers["Retry-After"] = str(math.ceil(result.retry_after))
    return headers