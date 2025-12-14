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
