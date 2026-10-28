def test_sliding_window_client_is_limited(client):
    r = client.put(
        "/admin/clients/sw-test-a",
        json={"rate": 1, "burst": 3, "algorithm": "sliding_window"},
    )
    assert r.status_code == 200
    codes = [
        client.post("/check", json={"client_key": "sw-test-a"}).status_code
        for _ in range(4)
    ]
    assert codes == [200, 200, 200, 429]  # 3 requests per 3-second window