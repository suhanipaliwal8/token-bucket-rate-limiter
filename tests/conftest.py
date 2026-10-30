import os

import pytest
from dotenv import dotenv_values

# Must run BEFORE the app is imported, so tests use the test database and a known key.
os.environ["DATABASE_URL"] = dotenv_values(".env")["TEST_DATABASE_URL"]
TEST_ADMIN_KEY = "test-admin-key-0123456789"
os.environ["ADMIN_API_KEY"] = TEST_ADMIN_KEY

from fastapi.testclient import TestClient  # noqa: E402

from app.db import pool  # noqa: E402
from app.main import app, store  # noqa: E402


@pytest.fixture(scope="session")
def client():
    # This client sends the admin key on every request by default.
    with TestClient(app, headers={"X-API-Key": TEST_ADMIN_KEY}) as c:
        # Start every test session from a clean slate, because startup
        # restores the state saved by the previous session.
        store._buckets.clear()
        store._windows.clear()
        with pool.connection() as conn:
            conn.execute("TRUNCATE bucket_state, window_state")
        yield c


@pytest.fixture
def anonymous_client(client):
    # No `with`: entering the context would run startup/shutdown a second time and
    # close the shared database pool. The `client` dependency already started the app.
    return TestClient(app)