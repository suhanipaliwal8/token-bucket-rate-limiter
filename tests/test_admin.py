def test_set_and_get_config(client):
    r = client.put("/admin/clients/admin-test-a", json={"rate": 2, "burst": 3})
    assert r.status_code == 200
    assert r.json() == {
        "client_key": "admin-test-a",
        "rate": 2.0,
        "burst": 3,
        "algorithm": "token_bucket",
    }

    r = client.get("/admin/clients/admin-test-a")
    assert r.status_code == 200
    assert r.json()["burst"] == 3


def test_custom_burst_is_enforced(client):
    client.put("/admin/clients/admin-test-b", json={"rate": 1, "burst": 3})
    codes = [
        client.post("/check", json={"client_key": "admin-test-b"}).status_code
        for _ in range(4)
    ]
    assert codes == [200, 200, 200, 429]


def test_unknown_client_has_no_custom_config(client):
    r = client.get("/admin/clients/never-configured")
    assert r.status_code == 404


def test_invalid_config_is_rejected(client):
    r = client.put("/admin/clients/admin-test-c", json={"rate": 5, "burst": 0})
    assert r.status_code == 422

def test_delete_config(client):
    client.put("/admin/clients/admin-test-d", json={"rate": 2, "burst": 3})
    assert client.delete("/admin/clients/admin-test-d").status_code == 204
    assert client.get("/admin/clients/admin-test-d").status_code == 404
    assert client.delete("/admin/clients/admin-test-d").status_code == 404

def test_algorithm_defaults_to_token_bucket_and_can_be_changed(client):
    r = client.put("/admin/clients/admin-test-e", json={"rate": 1, "burst": 3})
    assert r.json()["algorithm"] == "token_bucket"

    r = client.put(
        "/admin/clients/admin-test-e",
        json={"rate": 1, "burst": 3, "algorithm": "sliding_window"},
    )
    assert r.json()["algorithm"] == "sliding_window"
    assert client.get("/admin/clients/admin-test-e").json()["algorithm"] == "sliding_window"


def test_unknown_algorithm_is_rejected(client):
    r = client.put(
        "/admin/clients/admin-test-f",
        json={"rate": 1, "burst": 3, "algorithm": "leaky_bucket"},
    )
    assert r.status_code == 422