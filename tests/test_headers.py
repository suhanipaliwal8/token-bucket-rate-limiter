from app.headers import rate_limit_headers
from app.store import CheckResult


def make(allowed, remaining, retry_after=0.0, reset_after=0.0, limit=10, now=1000.0):
    return CheckResult(
        allowed=allowed,
        limit=limit,
        remaining=remaining,
        retry_after=retry_after,
        reset_after=reset_after,
        reset_at=now + reset_after,
    )


def test_allowed_response_headers():
    headers = rate_limit_headers(make(True, 7, reset_after=2.4))
    assert headers == {
        "X-RateLimit-Limit": "10",
        "X-RateLimit-Remaining": "7",
        "X-RateLimit-Reset": "1003",  # 1002.4 rounded up
    }


def test_denied_response_has_retry_after_rounded_up():
    headers = rate_limit_headers(make(False, 0, retry_after=0.2, reset_after=5.0))
    assert headers["X-RateLimit-Remaining"] == "0"
    assert headers["Retry-After"] == "1"


def test_no_retry_after_when_allowed():
    assert "Retry-After" not in rate_limit_headers(make(True, 3))