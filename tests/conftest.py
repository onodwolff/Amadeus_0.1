import os
import sys
import pytest
from fastapi.testclient import TestClient

# add project root to sys.path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# ensure API token is set before importing app
os.environ.setdefault("API_TOKEN", "test-token")

from backend.app.main import app


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c

@pytest.fixture
def auth_headers():
    return {"Authorization": f"Bearer {os.environ['API_TOKEN']}"}
