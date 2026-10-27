from app.store import DEFAULT_BURST


def test_health(client):
    assert client.get("/health").json() == {"status": "ok"}


def test_allows_until_burst_then_denies(client):
    for _ in range(DEFAULT_BURST):
        r = client.post("/check", json={"client_key": "client-a"})
        assert r.status_code == 200
        assert r.json()["decision"] == "ALLOW"
    r = client.post("/check", json={"client_key": "client-a"})
    assert r.status_code == 429
    assert r.json()["decision"] == "DENY"


def test_clients_are_independent(client):
    for _ in range(DEFAULT_BURST):
        client.post("/check", json={"client_key": "client-b"})
    r = client.post("/check", json={"client_key": "client-c"})
    assert r.json()["decision"] == "ALLOW"


def test_empty_client_key_is_rejected(client):
    r = client.post("/check", json={"client_key": ""})
    assert r.status_code == 422