def test_metrics_endpoint_shows_checked_clients(client):
    for _ in range(3):
        client.post("/check", json={"client_key": "metrics-test-a"})
    data = client.get("/admin/metrics").json()
    assert "metrics-test-a" in [c["client_key"] for c in data["clients"]]


def test_dashboard_page_is_served(client):
    r = client.get("/dashboard")
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]