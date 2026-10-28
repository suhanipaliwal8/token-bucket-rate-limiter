def test_cost_spends_multiple_tokens(client):
    client.put("/admin/clients/cost-test-a", json={"rate": 0.01, "burst": 5})
    r = client.post("/check", json={"client_key": "cost-test-a", "cost": 3})
    assert r.status_code == 200
    assert r.headers["X-RateLimit-Remaining"] == "2"
    r = client.post("/check", json={"client_key": "cost-test-a", "cost": 3})
    assert r.status_code == 429  # only 2 tokens left


def test_cost_above_the_limit_is_rejected_with_422(client):
    client.put("/admin/clients/cost-test-b", json={"rate": 1, "burst": 5})
    r = client.post("/check", json={"client_key": "cost-test-b", "cost": 6})
    assert r.status_code == 422


def test_cost_must_be_positive(client):
    r = client.post("/check", json={"client_key": "cost-test-c", "cost": 0})
    assert r.status_code == 422