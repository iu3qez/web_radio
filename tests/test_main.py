import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock, AsyncMock
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


def test_websocket_requires_auth(client):
    """Test WebSocket requires auth via query param."""
    with pytest.raises(Exception):
        with client.websocket_connect("/ws"):
            pass


def test_websocket_with_auth(client, mock_config):
    """Test WebSocket connects with valid auth."""
    import main

    # Clear the lru_cache for get_config so our override works
    main.get_config.cache_clear()

    # Set up radio_state in the module
    main.radio_state = {
        "type": "state",
        "freq": 14074000,
        "mode": "USB",
        "filter_width": 2400,
        "smeter": -65,
    }

    with client.websocket_connect("/ws?token=operator:secret") as ws:
        # Should receive initial state
        data = ws.receive_json()
        assert data["type"] == "state"
        assert data["freq"] == 14074000
