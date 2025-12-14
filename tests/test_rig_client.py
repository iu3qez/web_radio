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
    mock_writer.is_closing = MagicMock(return_value=False)

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
    mock_writer.is_closing = MagicMock(return_value=False)

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
    mock_reader.readline = AsyncMock(side_effect=[b"USB\n", b"2400\n"])
    mock_writer = MagicMock()
    mock_writer.write = MagicMock()
    mock_writer.drain = AsyncMock()
    mock_writer.close = MagicMock()
    mock_writer.wait_closed = AsyncMock()
    mock_writer.is_closing = MagicMock(return_value=False)

    with patch("asyncio.open_connection", return_value=(mock_reader, mock_writer)):
        await client.connect()
        mode, width = await client.get_mode()
        assert mode == "USB"
        assert width == 2400
        mock_writer.write.assert_called_with(b"m\n")


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
    mock_writer.is_closing = MagicMock(return_value=False)

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
    mock_writer.is_closing = MagicMock(return_value=False)

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
    mock_writer.is_closing = MagicMock(return_value=False)

    with patch("asyncio.open_connection", return_value=(mock_reader, mock_writer)):
        await client.connect()
        smeter = await client.get_smeter()
        assert smeter == -54
        mock_writer.write.assert_called_with(b"l STRENGTH\n")


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
    mock_writer.is_closing = MagicMock(return_value=False)

    with patch("asyncio.open_connection", return_value=(mock_reader, mock_writer)):
        await client.connect()
        state = await client.get_state()

        assert state["freq"] == 14074000
        assert state["mode"] == "USB"
        assert state["filter_width"] == 2400
        assert state["smeter"] == -65
