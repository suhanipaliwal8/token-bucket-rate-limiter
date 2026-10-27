import os

import pytest
from dotenv import dotenv_values

# Must run BEFORE the app is imported, so tests use the test database.
os.environ["DATABASE_URL"] = dotenv_values(".env")["TEST_DATABASE_URL"]

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as c:  # `with` runs the lifespan (startup/shutdown)
        yield c