"""Web Radio - FastAPI server for RTX control via rigctld."""

import asyncio
import logging
import secrets
from contextlib import asynccontextmanager
from functools import lru_cache
from pathlib import Path
from typing import Annotated, List

import yaml
from fastapi import Depends, FastAPI, HTTPException, status, WebSocket, WebSocketDisconnect, Query
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from rig_client import RigClient

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)


# Global state
rig_client: RigClient = None
connected_clients: List[WebSocket] = []
radio_state: dict = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    """App lifespan: connect to rigctld, start poller."""
    global rig_client
    config = get_config()
    logger = logging.getLogger(__name__)

    rig_client = RigClient(
        host=config["rigctld"]["host"],
        port=config["rigctld"]["port"],
    )

    # Try to connect (don't fail if rigctld not available)
    try:
        await rig_client.connect()
        logger.info(f"Connected to rigctld at {config['rigctld']['host']}:{config['rigctld']['port']}")
    except Exception as e:
        logger.warning(f"Failed to connect to rigctld: {e}. Will retry in polling loop.")

    # Start polling task
    poll_task = asyncio.create_task(poll_radio_state(config["polling"]["interval_ms"]))

    yield

    poll_task.cancel()
    if rig_client.connected:
        await rig_client.disconnect()


app = FastAPI(title="Web Radio", lifespan=lifespan)
security = HTTPBasic()

# Mount static files
static_path = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=static_path), name="static")


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


async def poll_radio_state(interval_ms: int):
    """Poll rigctld and broadcast state to clients.

    Automatically reconnects if connection is lost.
    """
    global rig_client, radio_state
    logger = logging.getLogger(__name__)
    config = get_config()
    reconnect_attempts = 0

    while True:
        try:
            # Try to reconnect if not connected
            if rig_client and not rig_client.connected:
                if reconnect_attempts == 0:
                    logger.info("Attempting to connect to rigctld...")
                try:
                    await rig_client.connect()
                    logger.info(f"Connected to rigctld at {config['rigctld']['host']}:{config['rigctld']['port']}")
                    reconnect_attempts = 0
                except Exception as e:
                    reconnect_attempts += 1
                    if reconnect_attempts % 10 == 1:  # Log every 10 attempts
                        logger.warning(f"Cannot connect to rigctld (attempt {reconnect_attempts}): {e}")
                    await asyncio.sleep(interval_ms / 1000)
                    continue

            # Poll radio state if connected
            if rig_client and rig_client.connected:
                radio_state = await rig_client.get_state()
                radio_state["type"] = "state"
                await broadcast(radio_state)
        except Exception as e:
            logger.error(f"Error polling radio state: {e}", exc_info=True)
            # Disconnect to trigger reconnection
            if rig_client and rig_client.connected:
                try:
                    await rig_client.disconnect()
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


async def handle_command(data: dict, websocket: WebSocket):
    """Handle incoming WebSocket command.

    Supported commands:
    - set_freq: Set frequency in Hz
    - set_mode: Set mode (USB, LSB, CW, AM, FM, DATA)
    - set_filter_width: Set filter width in Hz
    - set_spot: Momentary SPOT function (centers CW signal)
    - set_agc: Set AGC mode (OFF, SLOW, MED, FAST)
    - set_rf_gain: Set RF gain 0-100%
    - set_power: Set TX power 0-100%
    - set_break_in: Enable/disable break-in (full QSK)
    - set_rit: Set RIT offset in Hz
    - get_state: Request full radio state
    """
    if not rig_client or not rig_client.connected:
        await websocket.send_json({
            "type": "error",
            "message": "Radio not connected"
        })
        return

    cmd = data.get("cmd")
    value = data.get("value")

    try:
        if cmd == "set_freq":
            success = await rig_client.set_freq(int(value))
        elif cmd == "set_mode":
            success = await rig_client.set_mode(str(value))
        elif cmd == "set_filter_width":
            success = await rig_client.set_mode(data.get("mode", "USB"), int(value))
        elif cmd == "set_spot":
            # SPOT is momentary action - centers CW signal in filter
            success = await rig_client.set_func("SPOT", bool(value))
        elif cmd == "set_agc":
            # AGC is a LEVEL (0.0-1.0), not a parameter
            # Hamlib AGC values: 0=OFF, 1=SUPERFAST, 2=FAST, 3=SLOW, 4=USER, 5=MEDIUM, 6=AUTO
            # Map UI strings to normalized values (value/6)
            agc_map = {
                "OFF": 0.0,      # 0/6 = 0.0
                "FAST": 0.33,    # 2/6 ≈ 0.33
                "SLOW": 0.5,     # 3/6 = 0.5
                "MED": 0.83      # 5/6 ≈ 0.83
            }
            agc_value = agc_map.get(str(value).upper(), 0.83)
            success = await rig_client.set_level("AGC", agc_value)
        elif cmd == "set_rf_gain":
            # Convert percentage (0-100) to normalized value (0.0-1.0)
            success = await rig_client.set_level("RFGAIN", int(value) / 100.0)
        elif cmd == "set_break_in":
            # BKIN = Full break-in (QSK) for CW
            success = await rig_client.set_func("BKIN", bool(value))
        elif cmd == "set_power":
            # Convert percentage (0-100) to normalized value (0.0-1.0)
            success = await rig_client.set_level("RFPOWER", int(value) / 100.0)
        elif cmd == "set_rit":
            success = await rig_client.set_rit(int(value))
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


@app.get("/")
async def root(username: Annotated[str, Depends(verify_credentials)]):
    """Serve main UI page."""
    static_file = Path(__file__).parent / "static" / "index.html"
    return FileResponse(static_file)


@app.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    token: str = Query(None),
    config: dict = Depends(get_config),
):
    """WebSocket endpoint for real-time radio control."""
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
