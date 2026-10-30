import pytest
from fastapi.routing import APIRoute

from app.main import app

ADMIN_ROUTES = [
    (method, route.path)
    for route in app.routes
    if isinstance(route, APIRoute) and route.path.startswith("/admin")
    for method in route.methods
]


def test_admin_routes_were_found():
    assert len(ADMIN_ROUTES) >= 4  # PUT, GET, DELETE clients and GET metrics


@pytest.mark.parametrize("method,path", ADMIN_ROUTES)
def test_every_admin_route_rejects_a_missing_key(anonymous_client, method, path):
    url = path.replace("{client_key}", "auth-test")
    body = {"rate": 1, "burst": 1} if method == "PUT" else None
    assert anonymous_client.request(method, url, json=body).status_code == 401


def test_wrong_key_is_rejected(anonymous_client):
    r = anonymous_client.get(
        "/admin/clients/auth-test", headers={"X-API-Key": "wrong-key-wrong-key-1"}
    )
    assert r.status_code == 401


def test_correct_key_is_accepted(client):
    # authenticated, so the answer is "not found", not "unauthorized"
    assert client.get("/admin/clients/auth-test-none").status_code == 404


def test_check_health_and_dashboard_stay_open(anonymous_client):
    assert anonymous_client.get("/health").status_code == 200
    assert anonymous_client.get("/dashboard").status_code == 200
    r = anonymous_client.post("/check", json={"client_key": "auth-open-test"})
    assert r.status_code == 200