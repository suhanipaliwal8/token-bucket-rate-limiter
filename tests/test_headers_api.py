import time


def test_allowed_response_has_rate_limit_headers(client):
    client.put("/admin/clients/hdr-test-a", json={"rate": 1, "burst": 3})
    r = client.post("/check", json={"client_key": "hdr-test-a"})
    assert r.status_code == 200
    assert r.headers["X-RateLimit-Limit"] == "3"
    assert r.headers["X-RateLimit-Remaining"] == "2"
    assert int(r.headers["X-RateLimit-Reset"]) >= int(time.time())
    assert "Retry-After" not in r.headers


def test_denied_response_has_retry_after(client):
    client.put("/admin/clients/hdr-test-b", json={"rate": 0.1, "burst": 1})
    client.post("/check", json={"client_key": "hdr-test-b"})  # spends the only token
    r = client.post("/check", json={"client_key": "hdr-test-b"})
    assert r.status_code == 429
    assert r.headers["X-RateLimit-Remaining"] == "0"
    assert int(r.headers["Retry-After"]) >= 1  # about 10 seconds at 0.1 tokens/sec


def test_sliding_window_responses_have_headers_too(client):
    client.put(
        "/admin/clients/hdr-test-c",
        json={"rate": 1, "burst": 2, "algorithm": "sliding_window"},
    )
    r = client.post("/check", json={"client_key": "hdr-test-c"})
    assert r.headers["X-RateLimit-Limit"] == "2"
    assert r.headers["X-RateLimit-Remaining"] == "1"