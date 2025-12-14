"""Async client for rigctld TCP protocol.

rigctld Protocol Reference:
---------------------------
rigctld uses a simple text-based protocol over TCP (default port 4532).
Commands are sent as text lines terminated with newline.

Command convention:
- Lowercase letters = GET commands (query state)
- Uppercase letters = SET commands (change state)

Common commands:
- f / F <freq>           : Get/Set frequency in Hz
- m / M <mode> <width>   : Get/Set mode and passband width
- l <name> / L <name> <val> : Get/Set level (RFGAIN, RFPOWER, etc) 0.0-1.0
- u <name> / U <name> <val> : Get/Set function (SPOT, BKIN) 0/1
- p <name> / P <name> <val> : Get/Set parameter (AGC) integer
- j / J <offset>         : Get/Set RIT offset in Hz

Responses:
- GET commands: return value on success
- SET commands: return "RPRT 0" on success, "RPRT <negative>" on error

Documentation: https://hamlib.sourceforge.net/html/rigctld.1.html
"""

import asyncio
import logging
from typing import Optional, Tuple

logger = logging.getLogger(__name__)


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
            cmd_bytes = f"{cmd}\n".encode()
            logger.debug(f"→ rigctld: {cmd}")
            self._writer.write(cmd_bytes)
            await self._writer.drain()
            response = await self._reader.readline()
            response_str = response.decode().strip()
            logger.debug(f"← rigctld: {response_str}")
            return response_str

    async def get_freq(self) -> int:
        """Get current frequency in Hz.

        rigctld command: f
        """
        response = await self._send_command("f")
        return int(response)

    async def get_mode(self) -> Tuple[str, int]:
        """Get current mode and passband width.

        rigctld command: m
        Returns: Two lines - mode (USB/LSB/CW/etc) and width in Hz
        Note: Uses direct I/O instead of _send_command for multi-line response
        """
        async with self._lock:
            self._writer.write(b"m\n")
            await self._writer.drain()
            mode = (await self._reader.readline()).decode().strip()
            width = int((await self._reader.readline()).decode().strip())
            return mode, width

    async def set_freq(self, freq: int) -> bool:
        """Set frequency in Hz. Returns True on success.

        rigctld command: F <freq>
        Response: RPRT 0 on success
        """
        response = await self._send_command(f"F {freq}")
        return response == "RPRT 0"

    async def set_mode(self, mode: str, passband: int = 0) -> bool:
        """Set mode (USB, LSB, CW, AM, FM). Returns True on success.

        rigctld command: M <mode> <passband>
        passband: 0 = use default for mode
        Response: RPRT 0 on success
        """
        response = await self._send_command(f"M {mode} {passband}")
        return response == "RPRT 0"

    async def get_smeter(self) -> int:
        """Get S-meter reading in dBm.

        rigctld command: l STRENGTH
        Returns: Signal strength in dBm (typically -120 to -20)
        """
        response = await self._send_command("l STRENGTH")
        return int(response)

    async def get_level(self, level_name: str) -> float:
        """Get level value (RFGAIN, RFPOWER, etc). Returns float 0.0-1.0.

        rigctld command: l <level_name>
        level_name: RFGAIN, RFPOWER, AF, SQL, etc
        Returns: Value normalized to 0.0-1.0 range
        """
        response = await self._send_command(f"l {level_name}")
        return float(response)

    async def get_func(self, func_name: str) -> bool:
        """Get function status (SPOT, etc). Returns True if enabled.

        rigctld command: u <func_name>
        func_name: SPOT, BKIN (break-in), NB (noise blanker), etc
        Returns: "1" if enabled, "0" if disabled
        """
        response = await self._send_command(f"u {func_name}")
        return response == "1"

    async def get_parm(self, parm_name: str) -> int:
        """Get parameter value (AGC, etc). Returns integer.

        rigctld command: p <parm_name>
        parm_name: AGC (0=OFF, 1=SLOW, 2=MED, 3=FAST), etc
        Returns: Integer parameter value (meaning depends on parameter)
        """
        response = await self._send_command(f"p {parm_name}")
        return int(response)

    async def get_rit(self) -> int:
        """Get RIT (Receiver Incremental Tuning) offset in Hz.

        rigctld command: j
        Returns: RIT offset in Hz (typically -9999 to +9999)
        """
        response = await self._send_command("j")
        return int(response)

    async def set_level(self, level_name: str, value: float) -> bool:
        """Set level value (RFGAIN, RFPOWER, etc). Value 0.0-1.0. Returns True on success.

        rigctld command: L <level_name> <value>
        value: 0.0-1.0 (normalized, hamlib scales to hardware range)
        Response: RPRT 0 on success
        """
        response = await self._send_command(f"L {level_name} {value}")
        return response == "RPRT 0"

    async def set_func(self, func_name: str, enable: bool) -> bool:
        """Set function (SPOT, etc). Returns True on success.

        rigctld command: U <func_name> <value>
        value: "1" to enable, "0" to disable
        Response: RPRT 0 on success
        """
        value = "1" if enable else "0"
        response = await self._send_command(f"U {func_name} {value}")
        return response == "RPRT 0"

    async def set_parm(self, parm_name: str, value: int) -> bool:
        """Set parameter (AGC, etc). Returns True on success.

        rigctld command: P <parm_name> <value>
        Example: P AGC 2 (sets AGC to MED)
        Response: RPRT 0 on success
        """
        response = await self._send_command(f"P {parm_name} {value}")
        return response == "RPRT 0"

    async def set_rit(self, offset: int) -> bool:
        """Set RIT offset in Hz. Returns True on success.

        rigctld command: J <offset>
        offset: RIT offset in Hz (typically -9999 to +9999)
        Response: RPRT 0 on success
        """
        response = await self._send_command(f"J {offset}")
        return response == "RPRT 0"

    async def get_state(self) -> dict:
        """Get full radio state with extended controls.

        Uses try/except for each command to handle unsupported features gracefully.
        If a command fails, a default value is used instead.
        """
        state = {}

        # Core controls (required)
        try:
            state["freq"] = await self.get_freq()
        except Exception as e:
            logger.warning(f"Failed to get frequency: {e}")
            state["freq"] = 0

        try:
            mode, width = await self.get_mode()
            state["mode"] = mode
            state["filter_width"] = width
        except Exception as e:
            logger.warning(f"Failed to get mode: {e}")
            state["mode"] = "USB"
            state["filter_width"] = 2400

        try:
            state["smeter"] = await self.get_smeter()
        except Exception as e:
            logger.warning(f"Failed to get S-meter: {e}")
            state["smeter"] = -100

        # Extended controls (optional - use defaults if not supported)
        try:
            rf_gain = await self.get_level("RFGAIN")
            state["rf_gain"] = int(rf_gain * 100)
        except Exception as e:
            logger.debug(f"RFGAIN not supported: {e}")
            state["rf_gain"] = 80

        try:
            power = await self.get_level("RFPOWER")
            state["power"] = int(power * 100)
        except Exception as e:
            logger.debug(f"RFPOWER not supported: {e}")
            state["power"] = 50

        try:
            # AGC is a LEVEL (0.0-1.0), not a parameter
            # Hamlib AGC values: 0=OFF, 1=SUPERFAST, 2=FAST, 3=SLOW, 4=USER, 5=MEDIUM, 6=AUTO
            # Normalized to 0.0-1.0 range
            agc_level = await self.get_level("AGC")
            # Map normalized value to UI strings
            if agc_level < 0.1:
                state["agc"] = "OFF"      # 0/6 = 0.0
            elif agc_level < 0.4:
                state["agc"] = "FAST"     # 2/6 ≈ 0.33
            elif agc_level < 0.7:
                state["agc"] = "SLOW"     # 3/6 = 0.5
            else:
                state["agc"] = "MED"      # 5/6 ≈ 0.83
        except Exception as e:
            logger.debug(f"AGC not supported: {e}")
            state["agc"] = "MED"

        try:
            state["break_in"] = await self.get_func("BKIN")
        except Exception as e:
            logger.debug(f"BKIN not supported: {e}")
            state["break_in"] = False

        try:
            state["rit"] = await self.get_rit()
        except Exception as e:
            logger.debug(f"RIT not supported: {e}")
            state["rit"] = 0

        return state
