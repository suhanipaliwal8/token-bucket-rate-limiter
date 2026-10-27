import os

import pytest
from dotenv import dotenv_values

# Must run BEFORE the app is imported, so tests use the test database.
os.environ["DATABASE_URL"] = dotenv_values(".env")["TEST_DATABASE_URL"]

from fastapi.testclient import TestClient  # noqa: E402

from app.db import pool  # noqa: E402
from app.main import app, store  # noqa: E402


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as c:
        # Start every test session from a clean slate, because startup now
        # restores the buckets saved by the previous session.
        store._buckets.clear()
        with pool.connection() as conn:
            conn.execute("TRUNCATE bucket_state")
        yield c