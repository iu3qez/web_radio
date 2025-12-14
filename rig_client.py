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

    async def _send_command(self, cmd: str, timeout: float = 5.0) -> str:
        """Send command and return response.

        Args:
            cmd: Command to send
            timeout: Timeout in seconds (default: 5.0)

        Raises:
            ConnectionError: If not connected
            asyncio.TimeoutError: If rigctld doesn't respond within timeout
        """
        if not self.connected:
            raise ConnectionError("Not connected to rigctld")

        async with self._lock:
            cmd_bytes = f"{cmd}\n".encode()
            logger.debug(f"→ rigctld: {cmd}")

            try:
                self._writer.write(cmd_bytes)
                await asyncio.wait_for(self._writer.drain(), timeout=timeout)
                response = await asyncio.wait_for(self._reader.readline(), timeout=timeout)
                response_str = response.decode().strip()
                logger.debug(f"← rigctld: {response_str}")

                # Log length for debugging
                if len(response) != len(response_str) + 1:  # +1 for newline
                    logger.warning(f"Response length mismatch: raw={len(response)} stripped={len(response_str)}")

                return response_str
            except asyncio.TimeoutError:
                logger.error(f"Timeout waiting for rigctld response to command: {cmd}")
                # Try to read any pending data to prevent buffer pollution
                try:
                    pending = await asyncio.wait_for(self._reader.read(1024), timeout=0.1)
                    logger.warning(f"Found pending data after timeout: {pending}")
                except:
                    pass
                raise

    async def get_freq(self) -> int:
        """Get current frequency in Hz.

        rigctld command: f
        """
        response = await self._send_command("f")
        return int(response)

    async def get_mode(self, timeout: float = 5.0) -> Tuple[str, int]:
        """Get current mode and passband width.

        rigctld command: m
        Returns: Two lines - mode (USB/LSB/CW/etc) and width in Hz
        Note: Uses direct I/O instead of _send_command for multi-line response

        Args:
            timeout: Timeout in seconds (default: 5.0)
        """
        async with self._lock:
            try:
                self._writer.write(b"m\n")
                await asyncio.wait_for(self._writer.drain(), timeout=timeout)
                mode_line = await asyncio.wait_for(self._reader.readline(), timeout=timeout)
                width_line = await asyncio.wait_for(self._reader.readline(), timeout=timeout)
                mode = mode_line.decode().strip()
                width = int(width_line.decode().strip())
                return mode, width
            except asyncio.TimeoutError:
                logger.error("Timeout waiting for rigctld response to 'm' command")
                raise

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

    async def send_raw_command(self, cmd: str, timeout: float = 5.0) -> str:
        """Send raw command to rig via rigctld 'w' (write_cmd).

        For sending native rig commands (like Thetis ZZGT, Kenwood GT, etc)
        that hamlib doesn't abstract.

        rigctld command: w <native_cmd>
        Returns: Response from rig

        Args:
            cmd: Native rig command (e.g. "ZZGT;" for Thetis)
            timeout: Timeout in seconds (default: 5.0)

        Note: Commands sent via 'w' return responses terminated with '\x00' (null byte)
              instead of '\n' (newline), so we must use readuntil(b';') instead of readline()
        """
        if not self.connected:
            raise ConnectionError("Not connected to rigctld")

        async with self._lock:
            cmd_full = f"w {cmd}\n"
            cmd_bytes = cmd_full.encode()
            logger.debug(f"→ rigctld: w {cmd}")

            try:
                self._writer.write(cmd_bytes)
                await asyncio.wait_for(self._writer.drain(), timeout=timeout)

                # Read until semicolon (Thetis responses end with ';' then '\x00')
                response = await asyncio.wait_for(
                    self._reader.readuntil(b';'),
                    timeout=timeout
                )

                # Read the trailing null byte
                await asyncio.wait_for(self._reader.read(1), timeout=0.1)

                response_str = response.decode().strip()
                logger.debug(f"← rigctld: {response_str}")

                return response_str
            except asyncio.TimeoutError:
                logger.error(f"Timeout waiting for rigctld response to command: w {cmd}")
                raise

    async def get_agc_thetis(self) -> int:
        """Get AGC using Thetis native ZZGT command.

        Returns: AGC value (0=Fixed, 1=Long, 2=Slow, 3=Med, 4=Fast, 5=Custom)
        """
        response = await self.send_raw_command("ZZGT;")
        # Response format: "ZZGTX;" where X is the value
        if response.startswith("ZZGT") and len(response) >= 5:
            return int(response[4])
        raise ValueError(f"Invalid ZZGT response: {response}")

    async def set_agc_thetis(self, value: int) -> bool:
        """Set AGC using Thetis native ZZGT command.

        Args:
            value: AGC value (0=Fixed, 1=Long, 2=Slow, 3=Med, 4=Fast, 5=Custom)

        Returns: True (always - SET commands don't return responses via rigctld 'w')
        """
        # SET commands via rigctld 'w' don't return responses, just send and assume success
        if not self.connected:
            raise ConnectionError("Not connected to rigctld")

        async with self._lock:
            cmd = f"w ZZGT{value};\n"
            logger.debug(f"→ rigctld: w ZZGT{value};")
            self._writer.write(cmd.encode())
            await self._writer.drain()
            # No response expected from SET commands
            return True

    async def get_rf_gain_thetis(self) -> int:
        """Get RF Gain (AGC Threshold) using Thetis native ZZAR command.

        Returns: AGC Threshold value (-20 to +120)
        """
        response = await self.send_raw_command("ZZAR;")
        # Response format: "ZZAR+XXX;" or "ZZAR-XXX;"
        if response.startswith("ZZAR") and len(response) >= 9:
            # Extract value including sign: "+080" or "-020"
            value_str = response[4:8]  # e.g. "+080"
            return int(value_str)
        raise ValueError(f"Invalid ZZAR response: {response}")

    async def set_rf_gain_thetis(self, value: int) -> bool:
        """Set RF Gain (AGC Threshold) using Thetis native ZZAR command.

        Args:
            value: AGC Threshold (-20 to +120)

        Returns: True (always - SET commands don't return responses via rigctld 'w')
        """
        # Format with sign and 3 digits: +080, -020, +120
        if value >= 0:
            value_str = f"+{value:03d}"
        else:
            value_str = f"{value:04d}"  # Negative sign counts as character

        # SET commands via rigctld 'w' don't return responses, just send and assume success
        if not self.connected:
            raise ConnectionError("Not connected to rigctld")

        async with self._lock:
            cmd = f"w ZZAR{value_str};\n"
            logger.debug(f"→ rigctld: w ZZAR{value_str};")
            self._writer.write(cmd.encode())
            await self._writer.drain()
            # No response expected from SET commands
            return True

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
        # Execute Thetis commands FIRST to avoid mixing with standard commands
        try:
            # Use Thetis native ZZGT command instead of hamlib l AGC
            # Thetis values: 0=Fixed, 1=Long, 2=Slow, 3=Med, 4=Fast, 5=Custom
            agc_value = await self.get_agc_thetis()
            logger.debug(f"AGC from Thetis ZZGT: {agc_value}")
            # Map Thetis values to UI strings
            agc_map = {
                0: "OFF",   # Fixed
                1: "SLOW",  # Long (map to SLOW)
                2: "SLOW",  # Slow
                3: "MED",   # Med
                4: "FAST",  # Fast
                5: "MED"    # Custom (map to MED)
            }
            state["agc"] = agc_map.get(agc_value, "MED")
        except Exception as e:
            logger.debug(f"AGC not supported: {e}")
            state["agc"] = "MED"

        try:
            # Use Thetis native ZZAR (AGC Threshold) command
            # Thetis range: -20 to +120
            # UI range: 0% to 100%
            rf_gain_thetis = await self.get_rf_gain_thetis()
            logger.debug(f"RF Gain from Thetis ZZAR: {rf_gain_thetis}")
            # Convert Thetis range (-20 to +120) to percentage (0-100)
            state["rf_gain"] = int((rf_gain_thetis + 20) / 140 * 100)
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
