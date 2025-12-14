# Phase 2: Extended Radio Controls - Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add extended radio control features (filter width, AGC, RF gain, power, spot, break-in, RIT) to the web radio interface.

**Architecture:** Extend RigClient with new rigctld commands, update WebSocket protocol to broadcast/handle new state fields, add UI controls in Alpine.js frontend.

**Tech Stack:** Python (FastAPI, asyncio), rigctld protocol, Alpine.js, WebSocket

---

## Task 1: RigClient - Get Extended State (Read-Only)

**Files:**
- Modify: `/home/sf/src/web_radio/rig_client.py`
- Modify: `/home/sf/src/web_radio/tests/test_rig_client.py`

**Step 1: Add tests for new get methods**

Append to `/home/sf/src/web_radio/tests/test_rig_client.py`:

```python
@pytest.mark.asyncio
async def test_rig_client_get_level_rfgain():
    """Test getting RF gain level."""
    client = RigClient(host="127.0.0.1", port=4532)

    mock_reader = AsyncMock()
    mock_reader.readline = AsyncMock(return_value=b"0.8\n")
    mock_writer = MagicMock()
    mock_writer.write = MagicMock()
    mock_writer.drain = AsyncMock()
    mock_writer.close = MagicMock()
    mock_writer.wait_closed = AsyncMock()
    mock_writer.is_closing = MagicMock(return_value=False)

    with patch("asyncio.open_connection", return_value=(mock_reader, mock_writer)):
        await client.connect()
        rf_gain = await client.get_level("RFGAIN")
        assert rf_gain == 0.8
        mock_writer.write.assert_called_with(b"l RFGAIN\n")


@pytest.mark.asyncio
async def test_rig_client_get_level_rfpower():
    """Test getting RF power level."""
    client = RigClient(host="127.0.0.1", port=4532)

    mock_reader = AsyncMock()
    mock_reader.readline = AsyncMock(return_value=b"0.5\n")
    mock_writer = MagicMock()
    mock_writer.write = MagicMock()
    mock_writer.drain = AsyncMock()
    mock_writer.close = MagicMock()
    mock_writer.wait_closed = AsyncMock()
    mock_writer.is_closing = MagicMock(return_value=False)

    with patch("asyncio.open_connection", return_value=(mock_reader, mock_writer)):
        await client.connect()
        power = await client.get_level("RFPOWER")
        assert power == 0.5
        mock_writer.write.assert_called_with(b"l RFPOWER\n")


@pytest.mark.asyncio
async def test_rig_client_get_func():
    """Test getting function status (SPOT)."""
    client = RigClient(host="127.0.0.1", port=4532)

    mock_reader = AsyncMock()
    mock_reader.readline = AsyncMock(return_value=b"1\n")
    mock_writer = MagicMock()
    mock_writer.write = MagicMock()
    mock_writer.drain = AsyncMock()
    mock_writer.close = MagicMock()
    mock_writer.wait_closed = AsyncMock()
    mock_writer.is_closing = MagicMock(return_value=False)

    with patch("asyncio.open_connection", return_value=(mock_reader, mock_writer)):
        await client.connect()
        spot = await client.get_func("SPOT")
        assert spot is True
        mock_writer.write.assert_called_with(b"u SPOT\n")


@pytest.mark.asyncio
async def test_rig_client_get_parm():
    """Test getting parameter (AGC)."""
    client = RigClient(host="127.0.0.1", port=4532)

    mock_reader = AsyncMock()
    mock_reader.readline = AsyncMock(return_value=b"2\n")
    mock_writer = MagicMock()
    mock_writer.write = MagicMock()
    mock_writer.drain = AsyncMock()
    mock_writer.close = MagicMock()
    mock_writer.wait_closed = AsyncMock()
    mock_writer.is_closing = MagicMock(return_value=False)

    with patch("asyncio.open_connection", return_value=(mock_reader, mock_writer)):
        await client.connect()
        agc = await client.get_parm("AGC")
        assert agc == 2
        mock_writer.write.assert_called_with(b"p AGC\n")
```

**Step 2: Run tests to verify they fail**

Run: `cd /home/sf/src/web_radio && source venv/bin/activate && pytest tests/test_rig_client.py -v`

Expected: 4 new tests FAIL

**Step 3: Implement get_level, get_func, get_parm methods**

Add to `/home/sf/src/web_radio/rig_client.py`:

```python
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
```

**Step 4: Run tests to verify they pass**

Run: `pytest tests/test_rig_client.py -v`

Expected: All tests PASS (16 tests total)

**Step 5: Commit**

```bash
git add rig_client.py tests/test_rig_client.py
git commit -m "feat: add get_level, get_func, get_parm, get_rit to RigClient"
```

---

## Task 2: RigClient - Set Extended Controls

**Files:**
- Modify: `/home/sf/src/web_radio/rig_client.py`
- Modify: `/home/sf/src/web_radio/tests/test_rig_client.py`

**Step 1: Add tests for set methods**

Append to `/home/sf/src/web_radio/tests/test_rig_client.py`:

```python
@pytest.mark.asyncio
async def test_rig_client_set_level():
    """Test setting level value."""
    client = RigClient(host="127.0.0.1", port=4532)

    mock_reader = AsyncMock()
    mock_reader.readline = AsyncMock(return_value=b"RPRT 0\n")
    mock_writer = MagicMock()
    mock_writer.write = MagicMock()
    mock_writer.drain = AsyncMock()
    mock_writer.close = MagicMock()
    mock_writer.wait_closed = AsyncMock()
    mock_writer.is_closing = MagicMock(return_value=False)

    with patch("asyncio.open_connection", return_value=(mock_reader, mock_writer)):
        await client.connect()
        success = await client.set_level("RFGAIN", 0.75)
        assert success is True
        mock_writer.write.assert_called_with(b"L RFGAIN 0.75\n")


@pytest.mark.asyncio
async def test_rig_client_set_func():
    """Test setting function."""
    client = RigClient(host="127.0.0.1", port=4532)

    mock_reader = AsyncMock()
    mock_reader.readline = AsyncMock(return_value=b"RPRT 0\n")
    mock_writer = MagicMock()
    mock_writer.write = MagicMock()
    mock_writer.drain = AsyncMock()
    mock_writer.close = MagicMock()
    mock_writer.wait_closed = AsyncMock()
    mock_writer.is_closing = MagicMock(return_value=False)

    with patch("asyncio.open_connection", return_value=(mock_reader, mock_writer)):
        await client.connect()
        success = await client.set_func("SPOT", True)
        assert success is True
        mock_writer.write.assert_called_with(b"U SPOT 1\n")


@pytest.mark.asyncio
async def test_rig_client_set_parm():
    """Test setting parameter."""
    client = RigClient(host="127.0.0.1", port=4532)

    mock_reader = AsyncMock()
    mock_reader.readline = AsyncMock(return_value=b"RPRT 0\n")
    mock_writer = MagicMock()
    mock_writer.write = MagicMock()
    mock_writer.drain = AsyncMock()
    mock_writer.close = MagicMock()
    mock_writer.wait_closed = AsyncMock()
    mock_writer.is_closing = MagicMock(return_value=False)

    with patch("asyncio.open_connection", return_value=(mock_reader, mock_writer)):
        await client.connect()
        success = await client.set_parm("AGC", 2)
        assert success is True
        mock_writer.write.assert_called_with(b"P AGC 2\n")


@pytest.mark.asyncio
async def test_rig_client_set_rit():
    """Test setting RIT offset."""
    client = RigClient(host="127.0.0.1", port=4532)

    mock_reader = AsyncMock()
    mock_reader.readline = AsyncMock(return_value=b"RPRT 0\n")
    mock_writer = MagicMock()
    mock_writer.write = MagicMock()
    mock_writer.drain = AsyncMock()
    mock_writer.close = MagicMock()
    mock_writer.wait_closed = AsyncMock()
    mock_writer.is_closing = MagicMock(return_value=False)

    with patch("asyncio.open_connection", return_value=(mock_reader, mock_writer)):
        await client.connect()
        success = await client.set_rit(100)
        assert success is True
        mock_writer.write.assert_called_with(b"J 100\n")
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/test_rig_client.py -v`

Expected: 4 new tests FAIL (20 tests total)

**Step 3: Implement set methods**

Add to `/home/sf/src/web_radio/rig_client.py`:

```python
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
```

**Step 4: Run tests to verify all pass**

Run: `pytest tests/test_rig_client.py -v`

Expected: All 20 tests PASS

**Step 5: Commit**

```bash
git add rig_client.py tests/test_rig_client.py
git commit -m "feat: add set_level, set_func, set_parm, set_rit to RigClient"
```

---

## Task 3: Update get_state with Extended Fields

**Files:**
- Modify: `/home/sf/src/web_radio/rig_client.py`
- Modify: `/home/sf/src/web_radio/tests/test_rig_client.py`

**Step 1: Update test_rig_client_get_state**

Modify existing test in `/home/sf/src/web_radio/tests/test_rig_client.py`:

Replace the `test_rig_client_get_state` test with:

```python
@pytest.mark.asyncio
async def test_rig_client_get_state():
    """Test getting full radio state with extended controls."""
    client = RigClient(host="127.0.0.1", port=4532)

    responses = [
        b"14074000\n",  # freq
        b"USB\n", b"2400\n",  # mode, width
        b"-65\n",  # smeter
        b"0.8\n",  # RF gain
        b"0.5\n",  # RF power
        b"1\n",  # SPOT
        b"2\n",  # AGC
        b"0\n",  # Break-in
        b"100\n",  # RIT
    ]
    response_iter = iter(responses)

    mock_reader = AsyncMock()
    mock_reader.readline = AsyncMock(side_effect=lambda: next(response_iter))
    mock_writer = MagicMock()
    mock_writer.write = MagicMock()
    mock_writer.drain = AsyncMock()
    mock_writer.close = MagicMock()
    mock_writer.wait_closed = AsyncMock()
    mock_writer.is_closing = MagicMock(return_value=False)

    with patch("asyncio.open_connection", return_value=(mock_reader, mock_writer)):
        await client.connect()
        state = await client.get_state()

        assert state["freq"] == 14074000
        assert state["mode"] == "USB"
        assert state["filter_width"] == 2400
        assert state["smeter"] == -65
        assert state["rf_gain"] == 80
        assert state["power"] == 50
        assert state["spot"] is True
        assert state["agc"] == "MED"
        assert state["break_in"] is False
        assert state["rit"] == 100
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_rig_client.py::test_rig_client_get_state -v`

Expected: FAIL

**Step 3: Update get_state implementation**

Modify `get_state()` in `/home/sf/src/web_radio/rig_client.py`:

```python
    async def get_state(self) -> dict:
        """Get full radio state with extended controls."""
        freq = await self.get_freq()
        mode, width = await self.get_mode()
        smeter = await self.get_smeter()

        # Extended controls
        rf_gain = await self.get_level("RFGAIN")
        power = await self.get_level("RFPOWER")
        spot = await self.get_func("SPOT")
        agc_value = await self.get_parm("AGC")
        break_in = await self.get_func("BKIN")
        rit = await self.get_rit()

        # Convert AGC value to string
        agc_map = {0: "OFF", 1: "SLOW", 2: "MED", 3: "FAST"}
        agc = agc_map.get(agc_value, "MED")

        # Convert levels from 0.0-1.0 to percentages
        rf_gain_pct = int(rf_gain * 100)
        power_pct = int(power * 100)

        return {
            "freq": freq,
            "mode": mode,
            "filter_width": width,
            "smeter": smeter,
            "rf_gain": rf_gain_pct,
            "power": power_pct,
            "spot": spot,
            "agc": agc,
            "break_in": break_in,
            "rit": rit,
        }
```

**Step 4: Run tests to verify all pass**

Run: `pytest tests/test_rig_client.py -v`

Expected: All 20 tests PASS

**Step 5: Commit**

```bash
git add rig_client.py tests/test_rig_client.py
git commit -m "feat: extend get_state with Phase 2 controls"
```

---

## Task 4: WebSocket Protocol - Handle Phase 2 Commands

**Files:**
- Modify: `/home/sf/src/web_radio/main.py`

**Step 1: Update handle_command function**

Modify `handle_command()` in `/home/sf/src/web_radio/main.py` to add new commands:

```python
async def handle_command(data: dict, websocket: WebSocket):
    """Handle incoming WebSocket command."""
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
            success = await rig_client.set_func("SPOT", bool(value))
        elif cmd == "set_agc":
            agc_map = {"OFF": 0, "SLOW": 1, "MED": 2, "FAST": 3}
            agc_value = agc_map.get(str(value).upper(), 2)
            success = await rig_client.set_parm("AGC", agc_value)
        elif cmd == "set_rf_gain":
            success = await rig_client.set_level("RFGAIN", int(value) / 100.0)
        elif cmd == "set_break_in":
            success = await rig_client.set_func("BKIN", bool(value))
        elif cmd == "set_power":
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
```

**Step 2: Manual test**

Run: `cd /home/sf/src/web_radio && source venv/bin/activate && uvicorn main:app --reload`

Test WebSocket commands via browser console.

**Step 3: Commit**

```bash
git add main.py
git commit -m "feat: add Phase 2 commands to WebSocket handler"
```

---

## Task 5: Frontend - Add Phase 2 UI Controls (HTML)

**Files:**
- Modify: `/home/sf/src/web_radio/static/index.html`

**Step 1: Add control sections to HTML**

Add after the band selector and before VFO dial in `/home/sf/src/web_radio/static/index.html`:

```html
        <!-- Extended Controls -->
        <div class="extended-controls">
            <!-- AGC -->
            <div class="control-group">
                <label>AGC:</label>
                <div class="control-buttons">
                    <template x-for="a in agcModes">
                        <button
                            :class="{ active: state.agc === a }"
                            @click="setAGC(a)"
                            x-text="a">
                        </button>
                    </template>
                </div>
            </div>

            <!-- RF Gain -->
            <div class="control-group">
                <label>RF Gain: <span x-text="state.rf_gain + '%'"></span></label>
                <input
                    type="range"
                    min="0"
                    max="100"
                    :value="state.rf_gain"
                    @input="setRFGain($event.target.value)"
                    class="slider">
            </div>

            <!-- Power -->
            <div class="control-group">
                <label>Power: <span x-text="state.power + '%'"></span></label>
                <input
                    type="range"
                    min="0"
                    max="100"
                    :value="state.power"
                    @input="setPower($event.target.value)"
                    class="slider">
            </div>

            <!-- RIT -->
            <div class="control-group">
                <label>RIT: <span x-text="state.rit + ' Hz'"></span></label>
                <div class="rit-controls">
                    <button @click="adjustRIT(-10)">-10</button>
                    <button @click="adjustRIT(-1)">-1</button>
                    <button @click="setRIT(0)">CLR</button>
                    <button @click="adjustRIT(1)">+1</button>
                    <button @click="adjustRIT(10)">+10</button>
                </div>
            </div>

            <!-- Toggle Controls -->
            <div class="control-group toggle-group">
                <label>
                    <input type="checkbox" :checked="state.spot" @change="setSpot($event.target.checked)">
                    <span>Spot</span>
                </label>
                <label>
                    <input type="checkbox" :checked="state.break_in" @change="setBreakIn($event.target.checked)">
                    <span>Break-in</span>
                </label>
            </div>
        </div>
```

**Step 2: Commit**

```bash
git add static/index.html
git commit -m "feat: add Phase 2 control UI elements"
```

---

## Task 6: Frontend - Style Phase 2 Controls (CSS)

**Files:**
- Modify: `/home/sf/src/web_radio/static/style.css`

**Step 1: Add CSS for extended controls**

Add to `/home/sf/src/web_radio/static/style.css`:

```css
/* Extended Controls */
.extended-controls {
    background: #1e1e1e;
    border-radius: 8px;
    padding: 16px;
    margin-bottom: 16px;
}

.control-group {
    margin-bottom: 12px;
}

.control-group:last-child {
    margin-bottom: 0;
}

.control-group label {
    display: block;
    color: #888;
    font-size: 13px;
    font-weight: bold;
    margin-bottom: 6px;
}

.control-buttons {
    display: flex;
    gap: 6px;
}

.control-buttons button {
    flex: 1;
    padding: 8px;
    background: #2a2a2a;
    border: 1px solid #444;
    border-radius: 4px;
    color: #e0e0e0;
    font-size: 12px;
    cursor: pointer;
    transition: all 0.2s;
}

.control-buttons button:hover {
    background: #333;
    border-color: #4caf50;
}

.control-buttons button.active {
    background: #4caf50;
    color: #1a1a1a;
    border-color: #4caf50;
}

.slider {
    width: 100%;
    height: 6px;
    border-radius: 3px;
    background: #333;
    outline: none;
    -webkit-appearance: none;
}

.slider::-webkit-slider-thumb {
    -webkit-appearance: none;
    appearance: none;
    width: 16px;
    height: 16px;
    border-radius: 50%;
    background: #4caf50;
    cursor: pointer;
}

.slider::-moz-range-thumb {
    width: 16px;
    height: 16px;
    border-radius: 50%;
    background: #4caf50;
    cursor: pointer;
    border: none;
}

.rit-controls {
    display: flex;
    gap: 4px;
}

.rit-controls button {
    flex: 1;
    padding: 8px;
    background: #2a2a2a;
    border: 1px solid #444;
    border-radius: 4px;
    color: #e0e0e0;
    font-size: 11px;
    cursor: pointer;
    transition: all 0.2s;
}

.rit-controls button:hover {
    background: #333;
    border-color: #ffb300;
}

.rit-controls button:active {
    background: #ffb300;
    color: #1a1a1a;
}

.toggle-group {
    display: flex;
    gap: 16px;
}

.toggle-group label {
    display: flex;
    align-items: center;
    gap: 8px;
    cursor: pointer;
    margin-bottom: 0;
}

.toggle-group input[type="checkbox"] {
    width: 16px;
    height: 16px;
    cursor: pointer;
}

.toggle-group span {
    color: #e0e0e0;
    font-size: 13px;
}
```

**Step 2: Commit**

```bash
git add static/style.css
git commit -m "feat: add CSS for Phase 2 controls"
```

---

## Task 7: Frontend - Alpine.js Logic for Phase 2

**Files:**
- Modify: `/home/sf/src/web_radio/static/app.js`

**Step 1: Add Phase 2 state fields**

Modify the `state` object in `/home/sf/src/web_radio/static/app.js`:

```javascript
        state: {
            freq: 14074000,
            mode: 'USB',
            smeter: -100,
            filter_width: 2400,
            rf_gain: 80,
            power: 50,
            spot: false,
            agc: 'MED',
            break_in: false,
            rit: 0,
        },
```

**Step 2: Add AGC modes constant**

Add after the `bands` array:

```javascript
        agcModes: ['OFF', 'SLOW', 'MED', 'FAST'],
```

**Step 3: Add Phase 2 command methods**

Add after the `setBand()` method:

```javascript
        setAGC(mode) {
            this.sendCommand('set_agc', mode);
        },

        setRFGain(value) {
            this.sendCommand('set_rf_gain', parseInt(value));
            this.state.rf_gain = parseInt(value);
        },

        setPower(value) {
            this.sendCommand('set_power', parseInt(value));
            this.state.power = parseInt(value);
        },

        setSpot(enabled) {
            this.sendCommand('set_spot', enabled);
            this.state.spot = enabled;
        },

        setBreakIn(enabled) {
            this.sendCommand('set_break_in', enabled);
            this.state.break_in = enabled;
        },

        setRIT(offset) {
            this.sendCommand('set_rit', offset);
            this.state.rit = offset;
        },

        adjustRIT(delta) {
            const newRIT = this.state.rit + delta;
            this.setRIT(newRIT);
        },
```

**Step 4: Commit**

```bash
git add static/app.js
git commit -m "feat: add Phase 2 control logic to Alpine.js"
```

---

## Task 8: Integration Test

**Step 1: Run all tests**

Run: `cd /home/sf/src/web_radio && source venv/bin/activate && pytest tests/ -v`

Expected: All tests PASS (20 tests)

**Step 2: Manual browser test**

Run: `uvicorn main:app --host 0.0.0.0 --port 8080`

Open browser to `http://localhost:8080`

Test all Phase 2 controls:
- AGC buttons
- RF Gain slider
- Power slider
- RIT adjustment
- Spot checkbox
- Break-in checkbox

**Step 3: Final commit**

```bash
git add -A
git commit -m "feat: complete Phase 2 extended radio controls"
```

---

## Summary

Phase 2 adds comprehensive radio control:
- **Backend**: Extended RigClient with rigctld level/func/parm commands
- **Protocol**: WebSocket handlers for all Phase 2 controls
- **Frontend**: UI controls with sliders, buttons, checkboxes

All controls follow same pattern:
- Backend: get/set methods in RigClient
- Protocol: WebSocket command handlers
- Frontend: Alpine.js bindings + optimistic updates

Next phase: Audio streaming (Phase 3)
