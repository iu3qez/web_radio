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
