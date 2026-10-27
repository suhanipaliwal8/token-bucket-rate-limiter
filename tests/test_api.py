from fastapi.testclient import TestClient

from app.main import app
from app.store import DEFAULT_BURST

client = TestClient(app)


def test_health():
    assert client.get("/health").json() == {"status": "ok"}


def test_allows_until_burst_then_denies():
    for _ in range(DEFAULT_BURST):
        r = client.post("/check", json={"client_key": "client-a"})
        assert r.status_code == 200
        assert r.json()["decision"] == "ALLOW"
    r = client.post("/check", json={"client_key": "client-a"})
    assert r.status_code == 429
    assert r.json()["decision"] == "DENY"


def test_clients_are_independent():
    for _ in range(DEFAULT_BURST):
        client.post("/check", json={"client_key": "client-b"})
    r = client.post("/check", json={"client_key": "client-c"})
    assert r.json()["decision"] == "ALLOW"


def test_empty_client_key_is_rejected():
    r = client.post("/check", json={"client_key": ""})
    assert r.status_code == 422