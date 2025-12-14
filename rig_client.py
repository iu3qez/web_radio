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

    async def get_level(self, level_name: str) -> float:
        """Get level value (RFGAIN, RFPOWER, etc). Returns float 0.0-1.0."""
        response = await self._send_command(f"l {level_name}")
        return float(response)

    async def get_func(self, func_name: str) -> bool:
        """Get function status (SPOT, etc). Returns True if enabled."""
        response = await self._send_command(f"u {func_name}")
        return response == "1"

    async def get_parm(self, parm_name: str) -> int:
        """Get parameter value (AGC, etc). Returns integer."""
        response = await self._send_command(f"p {parm_name}")
        return int(response)

    async def get_rit(self) -> int:
        """Get RIT (Receiver Incremental Tuning) offset in Hz."""
        response = await self._send_command("j")
        return int(response)

    async def set_level(self, level_name: str, value: float) -> bool:
        """Set level value (RFGAIN, RFPOWER, etc). Value 0.0-1.0. Returns True on success."""
        response = await self._send_command(f"L {level_name} {value}")
        return response == "RPRT 0"

    async def set_func(self, func_name: str, enable: bool) -> bool:
        """Set function (SPOT, etc). Returns True on success."""
        value = "1" if enable else "0"
        response = await self._send_command(f"U {func_name} {value}")
        return response == "RPRT 0"

    async def set_parm(self, parm_name: str, value: int) -> bool:
        """Set parameter (AGC, etc). Returns True on success."""
        response = await self._send_command(f"P {parm_name} {value}")
        return response == "RPRT 0"

    async def set_rit(self, offset: int) -> bool:
        """Set RIT offset in Hz. Returns True on success."""
        response = await self._send_command(f"J {offset}")
        return response == "RPRT 0"

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
