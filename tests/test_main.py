import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
import base64

from main import app, get_config


@pytest.fixture
def mock_config():
    return {
        "rigctld": {"host": "127.0.0.1", "port": 4532},
        "server": {"host": "0.0.0.0", "port": 8080},
        "auth": {"username": "operator", "password": "secret"},
        "polling": {"interval_ms": 200},
        "ui": {"default_step": 1000},
    }


@pytest.fixture
def client(mock_config):
    app.dependency_overrides[get_config] = lambda: mock_config
    return TestClient(app)


def test_root_requires_auth(client):
    """Test that root endpoint requires authentication."""
    response = client.get("/")
    assert response.status_code == 401


def test_root_with_valid_auth(client):
    """Test root endpoint with valid credentials."""
    credentials = base64.b64encode(b"operator:secret").decode()
    response = client.get("/", headers={"Authorization": f"Basic {credentials}"})
    assert response.status_code == 200


def test_root_with_invalid_auth(client):
    """Test root endpoint with invalid credentials."""
    credentials = base64.b64encode(b"operator:wrong").decode()
    response = client.get("/", headers={"Authorization": f"Basic {credentials}"})
    assert response.status_code == 401
