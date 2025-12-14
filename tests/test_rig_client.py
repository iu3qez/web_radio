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
