# Web Radio MVP - Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a webapp to control RTX radios via rigctld with real-time WebSocket updates.

**Architecture:** FastAPI async server connects to rigctld via TCP, polls radio state, broadcasts via WebSocket to Alpine.js frontend. Basic auth protects access.

**Tech Stack:** Python 3.12, FastAPI, uvicorn, Alpine.js, WebSocket, YAML config

---

## Task 1: Project Setup

**Files:**
- Create: `requirements.txt`
- Create: `config.yaml`

**Step 1: Create requirements.txt**

```
fastapi
uvicorn[standard]
pyyaml
websockets
```

**Step 2: Create config.yaml**

```yaml
rigctld:
  host: "127.0.0.1"
  port: 4532

server:
  host: "0.0.0.0"
  port: 8080

auth:
  username: "operator"
  password: "changeme"

polling:
  interval_ms: 200

ui:
  default_step: 1000
```

**Step 3: Create virtual environment and install**

Run: `cd /home/sf/src/web_radio && python3 -m venv venv && source venv/bin/activate && pip install -r requirements.txt`

**Step 4: Commit**

```bash
git add requirements.txt config.yaml
git commit -m "chore: add project dependencies and config"
```

---

## Task 2: RigClient - Connection and Basic Read

**Files:**
- Create: `rig_client.py`
- Create: `tests/test_rig_client.py`

**Step 1: Create tests directory**

Run: `mkdir -p /home/sf/src/web_radio/tests && touch /home/sf/src/web_radio/tests/__init__.py`

**Step 2: Write failing test for RigClient connection**

Create `tests/test_rig_client.py`:

```python
import pytest
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock

from rig_client import RigClient


@pytest.mark.asyncio
async def test_rig_client_connect():
    """Test RigClient connects to rigctld."""
    client = RigClient(host="127.0.0.1", port=4532)

    mock_reader = AsyncMock()
    mock_writer = MagicMock()
    mock_writer.close = MagicMock()
    mock_writer.wait_closed = AsyncMock()

    with patch("asyncio.open_connection", return_value=(mock_reader, mock_writer)):
        await client.connect()
        assert client.connected is True
        await client.disconnect()
        assert client.connected is False


@pytest.mark.asyncio
async def test_rig_client_get_freq():
    """Test getting frequency from rigctld."""
    client = RigClient(host="127.0.0.1", port=4532)

    mock_reader = AsyncMock()
    mock_reader.readline = AsyncMock(return_value=b"14074000\n")
    mock_writer = MagicMock()
    mock_writer.write = MagicMock()
    mock_writer.drain = AsyncMock()
    mock_writer.close = MagicMock()
    mock_writer.wait_closed = AsyncMock()

    with patch("asyncio.open_connection", return_value=(mock_reader, mock_writer)):
        await client.connect()
        freq = await client.get_freq()
        assert freq == 14074000
        mock_writer.write.assert_called_with(b"f\n")


@pytest.mark.asyncio
async def test_rig_client_get_mode():
    """Test getting mode from rigctld."""
    client = RigClient(host="127.0.0.1", port=4532)

    mock_reader = AsyncMock()
    mock_reader.readline = AsyncMock(return_value=b"USB\n2400\n")
    mock_writer = MagicMock()
    mock_writer.write = MagicMock()
    mock_writer.drain = AsyncMock()
    mock_writer.close = MagicMock()
    mock_writer.wait_closed = AsyncMock()

    with patch("asyncio.open_connection", return_value=(mock_reader, mock_writer)):
        await client.connect()
        mode, width = await client.get_mode()
        assert mode == "USB"
        assert width == 2400
        mock_writer.write.assert_called_with(b"m\n")
```

**Step 3: Run test to verify it fails**

Run: `cd /home/sf/src/web_radio && source venv/bin/activate && pytest tests/test_rig_client.py -v`

Expected: FAIL with "ModuleNotFoundError: No module named 'rig_client'"

**Step 4: Write minimal RigClient implementation**

Create `rig_client.py`:

```python
"""Async client for rigctld TCP protocol."""

import asyncio
from typing import Optional, Tuple


class RigClient:
    """Async client to communicate with rigctld."""

    def __init__(self, host: str = "127.0.0.1", port: int = 4532):
        self.host = host
        self.port = port
        self._reader: Optional[asyncio.StreamReader] = None
        self._writer: Optional[asyncio.StreamWriter] = None
        self._lock = asyncio.Lock()

    @property
    def connected(self) -> bool:
        return self._writer is not None and not self._writer.is_closing()

    async def connect(self) -> None:
        """Connect to rigctld."""
        self._reader, self._writer = await asyncio.open_connection(
            self.host, self.port
        )

    async def disconnect(self) -> None:
        """Disconnect from rigctld."""
        if self._writer:
            self._writer.close()
            await self._writer.wait_closed()
            self._writer = None
            self._reader = None

    async def _send_command(self, cmd: str) -> str:
        """Send command and return response."""
        if not self.connected:
            raise ConnectionError("Not connected to rigctld")

        async with self._lock:
            self._writer.write(f"{cmd}\n".encode())
            await self._writer.drain()
            response = await self._reader.readline()
            return response.decode().strip()

    async def get_freq(self) -> int:
        """Get current frequency in Hz."""
        response = await self._send_command("f")
        return int(response)

    async def get_mode(self) -> Tuple[str, int]:
        """Get current mode and passband width."""
        async with self._lock:
            self._writer.write(b"m\n")
            await self._writer.drain()
            mode = (await self._reader.readline()).decode().strip()
            width = int((await self._reader.readline()).decode().strip())
            return mode, width
```

**Step 5: Run tests to verify they pass**

Run: `cd /home/sf/src/web_radio && source venv/bin/activate && pytest tests/test_rig_client.py -v`

Expected: All 3 tests PASS

**Step 6: Commit**

```bash
git add rig_client.py tests/
git commit -m "feat: add RigClient with frequency and mode reading"
```

---

## Task 3: RigClient - Set Commands and S-Meter

**Files:**
- Modify: `rig_client.py`
- Modify: `tests/test_rig_client.py`

**Step 1: Add tests for set_freq, set_mode, and get_smeter**

Append to `tests/test_rig_client.py`:

```python
@pytest.mark.asyncio
async def test_rig_client_set_freq():
    """Test setting frequency."""
    client = RigClient(host="127.0.0.1", port=4532)

    mock_reader = AsyncMock()
    mock_reader.readline = AsyncMock(return_value=b"RPRT 0\n")
    mock_writer = MagicMock()
    mock_writer.write = MagicMock()
    mock_writer.drain = AsyncMock()
    mock_writer.close = MagicMock()
    mock_writer.wait_closed = AsyncMock()

    with patch("asyncio.open_connection", return_value=(mock_reader, mock_writer)):
        await client.connect()
        success = await client.set_freq(7074000)
        assert success is True
        mock_writer.write.assert_called_with(b"F 7074000\n")


@pytest.mark.asyncio
async def test_rig_client_set_mode():
    """Test setting mode."""
    client = RigClient(host="127.0.0.1", port=4532)

    mock_reader = AsyncMock()
    mock_reader.readline = AsyncMock(return_value=b"RPRT 0\n")
    mock_writer = MagicMock()
    mock_writer.write = MagicMock()
    mock_writer.drain = AsyncMock()
    mock_writer.close = MagicMock()
    mock_writer.wait_closed = AsyncMock()

    with patch("asyncio.open_connection", return_value=(mock_reader, mock_writer)):
        await client.connect()
        success = await client.set_mode("LSB")
        assert success is True
        mock_writer.write.assert_called_with(b"M LSB 0\n")


@pytest.mark.asyncio
async def test_rig_client_get_smeter():
    """Test getting S-meter reading."""
    client = RigClient(host="127.0.0.1", port=4532)

    mock_reader = AsyncMock()
    mock_reader.readline = AsyncMock(return_value=b"-54\n")
    mock_writer = MagicMock()
    mock_writer.write = MagicMock()
    mock_writer.drain = AsyncMock()
    mock_writer.close = MagicMock()
    mock_writer.wait_closed = AsyncMock()

    with patch("asyncio.open_connection", return_value=(mock_reader, mock_writer)):
        await client.connect()
        smeter = await client.get_smeter()
        assert smeter == -54
        mock_writer.write.assert_called_with(b"l STRENGTH\n")
```

**Step 2: Run tests to verify new ones fail**

Run: `pytest tests/test_rig_client.py -v`

Expected: 3 new tests FAIL

**Step 3: Implement set_freq, set_mode, get_smeter**

Add to `rig_client.py` class:

```python
    async def set_freq(self, freq: int) -> bool:
        """Set frequency in Hz. Returns True on success."""
        response = await self._send_command(f"F {freq}")
        return response == "RPRT 0"

    async def set_mode(self, mode: str, passband: int = 0) -> bool:
        """Set mode (USB, LSB, CW, AM, FM). Returns True on success."""
        response = await self._send_command(f"M {mode} {passband}")
        return response == "RPRT 0"

    async def get_smeter(self) -> int:
        """Get S-meter reading in dBm."""
        response = await self._send_command("l STRENGTH")
        return int(response)
```

**Step 4: Run tests to verify all pass**

Run: `pytest tests/test_rig_client.py -v`

Expected: All 6 tests PASS

**Step 5: Commit**

```bash
git add rig_client.py tests/test_rig_client.py
git commit -m "feat: add set_freq, set_mode, get_smeter to RigClient"
```

---

## Task 4: RigClient - Get Full State

**Files:**
- Modify: `rig_client.py`
- Modify: `tests/test_rig_client.py`

**Step 1: Add test for get_state**

Append to `tests/test_rig_client.py`:

```python
@pytest.mark.asyncio
async def test_rig_client_get_state():
    """Test getting full radio state."""
    client = RigClient(host="127.0.0.1", port=4532)

    responses = [
        b"14074000\n",  # freq
        b"USB\n", b"2400\n",  # mode
        b"-65\n",  # smeter
    ]
    response_iter = iter(responses)

    mock_reader = AsyncMock()
    mock_reader.readline = AsyncMock(side_effect=lambda: next(response_iter))
    mock_writer = MagicMock()
    mock_writer.write = MagicMock()
    mock_writer.drain = AsyncMock()
    mock_writer.close = MagicMock()
    mock_writer.wait_closed = AsyncMock()

    with patch("asyncio.open_connection", return_value=(mock_reader, mock_writer)):
        await client.connect()
        state = await client.get_state()

        assert state["freq"] == 14074000
        assert state["mode"] == "USB"
        assert state["filter_width"] == 2400
        assert state["smeter"] == -65
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_rig_client.py::test_rig_client_get_state -v`

Expected: FAIL with "AttributeError: 'RigClient' object has no attribute 'get_state'"

**Step 3: Implement get_state**

Add to `rig_client.py` class:

```python
    async def get_state(self) -> dict:
        """Get full radio state."""
        freq = await self.get_freq()
        mode, width = await self.get_mode()
        smeter = await self.get_smeter()

        return {
            "freq": freq,
            "mode": mode,
            "filter_width": width,
            "smeter": smeter,
        }
```

**Step 4: Run tests to verify all pass**

Run: `pytest tests/test_rig_client.py -v`

Expected: All 7 tests PASS

**Step 5: Commit**

```bash
git add rig_client.py tests/test_rig_client.py
git commit -m "feat: add get_state to RigClient"
```

---

## Task 5: FastAPI App - Basic Setup with Auth

**Files:**
- Create: `main.py`
- Create: `tests/test_main.py`

**Step 1: Write failing test for basic auth**

Create `tests/test_main.py`:

```python
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
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/test_main.py -v`

Expected: FAIL with "ModuleNotFoundError: No module named 'main'"

**Step 3: Implement basic FastAPI app with auth**

Create `main.py`:

```python
"""Web Radio - FastAPI server for RTX control via rigctld."""

import secrets
from functools import lru_cache
from pathlib import Path
from typing import Annotated

import yaml
from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse


app = FastAPI(title="Web Radio")
security = HTTPBasic()


@lru_cache
def get_config() -> dict:
    """Load configuration from YAML file."""
    config_path = Path(__file__).parent / "config.yaml"
    with open(config_path) as f:
        return yaml.safe_load(f)


def verify_credentials(
    credentials: Annotated[HTTPBasicCredentials, Depends(security)],
    config: Annotated[dict, Depends(get_config)],
) -> str:
    """Verify HTTP Basic auth credentials."""
    auth_config = config["auth"]

    is_user_ok = secrets.compare_digest(
        credentials.username.encode(), auth_config["username"].encode()
    )
    is_pass_ok = secrets.compare_digest(
        credentials.password.encode(), auth_config["password"].encode()
    )

    if not (is_user_ok and is_pass_ok):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Basic"},
        )

    return credentials.username


@app.get("/")
async def root(username: Annotated[str, Depends(verify_credentials)]):
    """Serve main UI page."""
    return FileResponse("static/index.html")
```

**Step 4: Create minimal static/index.html for test**

Run: `mkdir -p /home/sf/src/web_radio/static`

Create `static/index.html`:

```html
<!DOCTYPE html>
<html>
<head><title>Web Radio</title></head>
<body><h1>Web Radio</h1></body>
</html>
```

**Step 5: Run tests to verify they pass**

Run: `pytest tests/test_main.py -v`

Expected: All 3 tests PASS

**Step 6: Commit**

```bash
git add main.py tests/test_main.py static/index.html
git commit -m "feat: add FastAPI app with basic auth"
```

---

## Task 6: WebSocket Endpoint

**Files:**
- Modify: `main.py`
- Modify: `tests/test_main.py`

**Step 1: Add test for WebSocket connection**

Append to `tests/test_main.py`:

```python
import asyncio
from fastapi.websockets import WebSocket


def test_websocket_requires_auth(client):
    """Test WebSocket requires auth via query param."""
    with pytest.raises(Exception):
        with client.websocket_connect("/ws"):
            pass


def test_websocket_with_auth(client, mock_config):
    """Test WebSocket connects with valid auth."""
    with patch("main.rig_client") as mock_rig:
        mock_rig.connected = True
        mock_rig.get_state = MagicMock(return_value={
            "freq": 14074000,
            "mode": "USB",
            "filter_width": 2400,
            "smeter": -65,
        })

        with client.websocket_connect("/ws?token=operator:secret") as ws:
            # Should receive initial state
            data = ws.receive_json()
            assert data["type"] == "state"
            assert data["freq"] == 14074000
```

**Step 2: Run tests to verify new ones fail**

Run: `pytest tests/test_main.py -v`

Expected: 2 new tests FAIL

**Step 3: Add WebSocket endpoint to main.py**

Add imports and globals to `main.py`:

```python
import asyncio
from contextlib import asynccontextmanager
from typing import List

from fastapi import WebSocket, WebSocketDisconnect, Query

from rig_client import RigClient


# Global state
rig_client: RigClient = None
connected_clients: List[WebSocket] = []
radio_state: dict = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    """App lifespan: connect to rigctld, start poller."""
    global rig_client
    config = get_config()

    rig_client = RigClient(
        host=config["rigctld"]["host"],
        port=config["rigctld"]["port"],
    )

    # Try to connect (don't fail if rigctld not available)
    try:
        await rig_client.connect()
    except Exception:
        pass

    # Start polling task
    poll_task = asyncio.create_task(poll_radio_state(config["polling"]["interval_ms"]))

    yield

    poll_task.cancel()
    if rig_client.connected:
        await rig_client.disconnect()


async def poll_radio_state(interval_ms: int):
    """Poll rigctld and broadcast state to clients."""
    global radio_state

    while True:
        try:
            if rig_client and rig_client.connected:
                radio_state = await rig_client.get_state()
                radio_state["type"] = "state"
                await broadcast(radio_state)
        except Exception:
            pass

        await asyncio.sleep(interval_ms / 1000)


async def broadcast(message: dict):
    """Send message to all connected WebSocket clients."""
    disconnected = []
    for client in connected_clients:
        try:
            await client.send_json(message)
        except Exception:
            disconnected.append(client)

    for client in disconnected:
        connected_clients.remove(client)


def verify_ws_token(token: str, config: dict) -> bool:
    """Verify WebSocket auth token (username:password)."""
    try:
        username, password = token.split(":", 1)
        auth = config["auth"]
        return (
            secrets.compare_digest(username, auth["username"]) and
            secrets.compare_digest(password, auth["password"])
        )
    except ValueError:
        return False


@app.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    token: str = Query(None),
):
    """WebSocket endpoint for real-time radio control."""
    config = get_config()

    if not token or not verify_ws_token(token, config):
        await websocket.close(code=4001)
        return

    await websocket.accept()
    connected_clients.append(websocket)

    # Send current state immediately
    if radio_state:
        await websocket.send_json(radio_state)

    try:
        while True:
            data = await websocket.receive_json()
            await handle_command(data, websocket)
    except WebSocketDisconnect:
        connected_clients.remove(websocket)


async def handle_command(data: dict, websocket: WebSocket):
    """Handle incoming WebSocket command."""
    cmd = data.get("cmd")
    value = data.get("value")

    try:
        if cmd == "set_freq":
            success = await rig_client.set_freq(int(value))
        elif cmd == "set_mode":
            success = await rig_client.set_mode(str(value))
        elif cmd == "get_state":
            state = await rig_client.get_state()
            state["type"] = "state"
            await websocket.send_json(state)
            return
        else:
            await websocket.send_json({"type": "error", "message": f"Unknown command: {cmd}"})
            return

        await websocket.send_json({"type": "ack", "cmd": cmd, "success": success})
    except Exception as e:
        await websocket.send_json({"type": "error", "message": str(e)})
```

Update FastAPI app initialization:

```python
app = FastAPI(title="Web Radio", lifespan=lifespan)
```

**Step 4: Run tests to verify all pass**

Run: `pytest tests/test_main.py -v`

Expected: All 5 tests PASS

**Step 5: Commit**

```bash
git add main.py tests/test_main.py
git commit -m "feat: add WebSocket endpoint with auth and command handling"
```

---

## Task 7: Frontend - HTML Structure

**Files:**
- Modify: `static/index.html`

**Step 1: Create complete HTML structure**

Replace `static/index.html`:

```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Web Radio</title>
    <link rel="stylesheet" href="/static/style.css">
    <script defer src="https://cdn.jsdelivr.net/npm/alpinejs@3.x.x/dist/cdn.min.js"></script>
</head>
<body>
    <div id="app" x-data="radioApp()">
        <!-- Connection Status -->
        <div class="status-bar">
            <span class="status-indicator" :class="connectionStatus"></span>
            <span x-text="connectionStatus"></span>
        </div>

        <!-- Main Display -->
        <div class="display">
            <div class="frequency" x-text="formatFreq(state.freq)"></div>
            <div class="mode" x-text="state.mode"></div>
        </div>

        <!-- S-Meter -->
        <div class="smeter-container">
            <span class="smeter-label">S</span>
            <div class="smeter-bar">
                <div class="smeter-fill" :style="`width: ${smeterPercent}%`"></div>
            </div>
            <span class="smeter-value" x-text="state.smeter + ' dBm'"></span>
        </div>

        <!-- Mode Buttons -->
        <div class="mode-buttons">
            <template x-for="m in modes">
                <button
                    :class="{ active: state.mode === m }"
                    @click="setMode(m)"
                    x-text="m">
                </button>
            </template>
        </div>

        <!-- Frequency Control -->
        <div class="freq-control">
            <div
                class="vfo-dial"
                @wheel.prevent="handleWheel($event)">
                <span>VFO</span>
            </div>
        </div>

        <!-- Step Selector -->
        <div class="step-selector">
            <span>Step:</span>
            <template x-for="s in steps">
                <button
                    :class="{ active: step === s.value }"
                    @click="step = s.value"
                    x-text="s.label">
                </button>
            </template>
        </div>
    </div>

    <script src="/static/app.js"></script>
</body>
</html>
```

**Step 2: Commit**

```bash
git add static/index.html
git commit -m "feat: add HTML structure for radio UI"
```

---

## Task 8: Frontend - CSS Styling

**Files:**
- Create: `static/style.css`

**Step 1: Create LED-style CSS**

Create `static/style.css`:

```css
/* LED Display Font */
@import url('https://fonts.googleapis.com/css2?family=DSEG7+Classic:wght@400;700&display=swap');

* {
    box-sizing: border-box;
    margin: 0;
    padding: 0;
}

body {
    font-family: 'Segoe UI', sans-serif;
    background: #1a1a1a;
    color: #e0e0e0;
    min-height: 100vh;
    display: flex;
    justify-content: center;
    align-items: center;
}

#app {
    background: #252525;
    border-radius: 16px;
    padding: 24px;
    width: 100%;
    max-width: 480px;
    box-shadow: 0 8px 32px rgba(0, 0, 0, 0.5);
}

/* Status Bar */
.status-bar {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-bottom: 16px;
    font-size: 12px;
    text-transform: uppercase;
}

.status-indicator {
    width: 10px;
    height: 10px;
    border-radius: 50%;
}

.status-indicator.connected { background: #4caf50; }
.status-indicator.reconnecting { background: #ff9800; }
.status-indicator.disconnected { background: #f44336; }

/* Main Display */
.display {
    background: #0d0d0d;
    border-radius: 8px;
    padding: 24px;
    text-align: center;
    margin-bottom: 16px;
    border: 2px solid #333;
}

.frequency {
    font-family: 'DSEG7 Classic', monospace;
    font-size: 48px;
    color: #ffb300;
    text-shadow: 0 0 20px rgba(255, 179, 0, 0.5);
    letter-spacing: 4px;
}

.mode {
    font-family: 'DSEG7 Classic', monospace;
    font-size: 24px;
    color: #4caf50;
    margin-top: 8px;
}

/* S-Meter */
.smeter-container {
    display: flex;
    align-items: center;
    gap: 12px;
    margin-bottom: 16px;
    padding: 12px;
    background: #1a1a1a;
    border-radius: 8px;
}

.smeter-label {
    font-weight: bold;
    color: #888;
}

.smeter-bar {
    flex: 1;
    height: 16px;
    background: #333;
    border-radius: 4px;
    overflow: hidden;
}

.smeter-fill {
    height: 100%;
    background: linear-gradient(90deg, #4caf50 0%, #ffeb3b 60%, #f44336 100%);
    transition: width 0.1s ease;
}

.smeter-value {
    font-family: monospace;
    font-size: 14px;
    min-width: 70px;
    text-align: right;
}

/* Mode Buttons */
.mode-buttons {
    display: flex;
    gap: 8px;
    margin-bottom: 16px;
    flex-wrap: wrap;
}

.mode-buttons button {
    flex: 1;
    min-width: 60px;
    padding: 12px 8px;
    background: #333;
    border: none;
    border-radius: 8px;
    color: #e0e0e0;
    font-weight: bold;
    cursor: pointer;
    transition: all 0.2s;
}

.mode-buttons button:hover {
    background: #444;
}

.mode-buttons button.active {
    background: #ffb300;
    color: #1a1a1a;
}

/* VFO Dial */
.freq-control {
    margin-bottom: 16px;
}

.vfo-dial {
    background: linear-gradient(145deg, #2a2a2a, #1a1a1a);
    border-radius: 50%;
    width: 120px;
    height: 120px;
    margin: 0 auto;
    display: flex;
    justify-content: center;
    align-items: center;
    cursor: grab;
    border: 4px solid #333;
    font-weight: bold;
    color: #666;
    user-select: none;
}

.vfo-dial:hover {
    border-color: #ffb300;
}

.vfo-dial:active {
    cursor: grabbing;
}

/* Step Selector */
.step-selector {
    display: flex;
    align-items: center;
    gap: 8px;
    flex-wrap: wrap;
}

.step-selector span {
    color: #888;
    font-size: 14px;
}

.step-selector button {
    padding: 8px 12px;
    background: #333;
    border: none;
    border-radius: 4px;
    color: #e0e0e0;
    cursor: pointer;
    transition: all 0.2s;
}

.step-selector button:hover {
    background: #444;
}

.step-selector button.active {
    background: #4caf50;
    color: #1a1a1a;
}
```

**Step 2: Commit**

```bash
git add static/style.css
git commit -m "feat: add LED-style CSS for radio UI"
```

---

## Task 9: Frontend - Alpine.js App

**Files:**
- Create: `static/app.js`

**Step 1: Create Alpine.js application**

Create `static/app.js`:

```javascript
function radioApp() {
    return {
        // State
        state: {
            freq: 14074000,
            mode: 'USB',
            smeter: -100,
            filter_width: 2400,
        },
        connectionStatus: 'disconnected',
        step: 1000,
        ws: null,

        // Constants
        modes: ['LSB', 'USB', 'CW', 'AM', 'FM', 'DATA'],
        steps: [
            { label: '10', value: 10 },
            { label: '100', value: 100 },
            { label: '1k', value: 1000 },
            { label: '10k', value: 10000 },
            { label: '100k', value: 100000 },
        ],

        // Computed
        get smeterPercent() {
            // Convert dBm (-120 to -20) to percentage
            const min = -120;
            const max = -20;
            const clamped = Math.max(min, Math.min(max, this.state.smeter));
            return ((clamped - min) / (max - min)) * 100;
        },

        // Methods
        init() {
            this.connect();
        },

        connect() {
            const credentials = this.getCredentials();
            if (!credentials) {
                this.connectionStatus = 'disconnected';
                return;
            }

            const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
            const wsUrl = `${protocol}//${window.location.host}/ws?token=${credentials}`;

            this.ws = new WebSocket(wsUrl);
            this.connectionStatus = 'reconnecting';

            this.ws.onopen = () => {
                this.connectionStatus = 'connected';
            };

            this.ws.onmessage = (event) => {
                const data = JSON.parse(event.data);
                this.handleMessage(data);
            };

            this.ws.onclose = () => {
                this.connectionStatus = 'disconnected';
                // Reconnect after 3 seconds
                setTimeout(() => this.connect(), 3000);
            };

            this.ws.onerror = () => {
                this.connectionStatus = 'disconnected';
            };
        },

        getCredentials() {
            // Get from URL or prompt
            const params = new URLSearchParams(window.location.search);
            let token = params.get('auth');

            if (!token) {
                // Credentials come from HTTP Basic Auth header
                // We'll extract them from a meta tag or prompt
                token = sessionStorage.getItem('radioAuth');
                if (!token) {
                    const user = prompt('Username:');
                    const pass = prompt('Password:');
                    if (user && pass) {
                        token = `${user}:${pass}`;
                        sessionStorage.setItem('radioAuth', token);
                    }
                }
            }

            return token;
        },

        handleMessage(data) {
            switch (data.type) {
                case 'state':
                    this.state = { ...this.state, ...data };
                    break;
                case 'ack':
                    console.log('Command acknowledged:', data.cmd, data.success);
                    break;
                case 'error':
                    console.error('Error:', data.message);
                    alert('Error: ' + data.message);
                    break;
            }
        },

        sendCommand(cmd, value) {
            if (this.ws && this.ws.readyState === WebSocket.OPEN) {
                this.ws.send(JSON.stringify({ cmd, value }));
            }
        },

        setMode(mode) {
            this.sendCommand('set_mode', mode);
        },

        setFreq(freq) {
            this.sendCommand('set_freq', freq);
        },

        handleWheel(event) {
            const delta = event.deltaY < 0 ? this.step : -this.step;
            const newFreq = this.state.freq + delta;
            this.setFreq(newFreq);
            // Optimistic update
            this.state.freq = newFreq;
        },

        formatFreq(hz) {
            // Format as XX.XXX.XXX
            const str = hz.toString().padStart(8, '0');
            const mhz = str.slice(0, -6) || '0';
            const khz = str.slice(-6, -3);
            const h = str.slice(-3);
            return `${mhz}.${khz}.${h}`;
        },
    };
}
```

**Step 2: Commit**

```bash
git add static/app.js
git commit -m "feat: add Alpine.js radio control app"
```

---

## Task 10: Static File Serving

**Files:**
- Modify: `main.py`

**Step 1: Add static file mounting**

Add to `main.py` after app creation:

```python
# Mount static files
static_path = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=static_path), name="static")
```

**Step 2: Manual test**

Run: `cd /home/sf/src/web_radio && source venv/bin/activate && uvicorn main:app --reload`

Open browser: `http://localhost:8080`

Expected: Login prompt, then radio UI displays

**Step 3: Commit**

```bash
git add main.py
git commit -m "feat: mount static files for frontend serving"
```

---

## Task 11: Docker Setup

**Files:**
- Create: `Dockerfile`
- Create: `docker-compose.yml`
- Create: `.dockerignore`

**Step 1: Create Dockerfile**

Create `Dockerfile`:

```dockerfile
FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8080

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
```

**Step 2: Create docker-compose.yml**

Create `docker-compose.yml`:

```yaml
services:
  web-radio:
    build: .
    ports:
      - "8080:8080"
    volumes:
      - ./config.yaml:/app/config.yaml:ro
    restart: unless-stopped
    extra_hosts:
      - "host.docker.internal:host-gateway"
```

**Step 3: Create .dockerignore**

Create `.dockerignore`:

```
venv/
__pycache__/
*.pyc
.git/
tests/
docs/
*.md
.dockerignore
```

**Step 4: Test Docker build**

Run: `cd /home/sf/src/web_radio && docker compose build`

Expected: Build succeeds

**Step 5: Commit**

```bash
git add Dockerfile docker-compose.yml .dockerignore
git commit -m "feat: add Docker configuration"
```

---

## Task 12: Final Integration Test

**Step 1: Start rigctld dummy (for testing)**

Run: `rigctld -m 1 &`  (model 1 = dummy rig)

**Step 2: Run the app**

Run: `cd /home/sf/src/web_radio && source venv/bin/activate && uvicorn main:app --host 0.0.0.0 --port 8080`

**Step 3: Test in browser**

1. Open `http://localhost:8080`
2. Enter credentials: operator / changeme
3. Verify frequency display shows
4. Scroll on VFO dial to change frequency
5. Click mode buttons to change mode
6. Verify S-meter updates

**Step 4: Run all tests**

Run: `pytest tests/ -v`

Expected: All tests PASS

**Step 5: Final commit**

```bash
git add -A
git commit -m "chore: complete MVP implementation"
```

---

## Summary

MVP complete with:
- RigClient for rigctld communication
- FastAPI server with WebSocket and basic auth
- Alpine.js frontend with LED-style display
- Docker support

Next phases:
- **Phase 2**: Add filter width, spot, AGC, RF gain, break-in, power controls
- **Phase 3**: Audio streaming via WebRTC
