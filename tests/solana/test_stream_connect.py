"""Tests for Solana stream WebSocket connection lifecycle.

Validates connection handshake, hello message schema, server time accuracy,
multi-connection independence, graceful close, and error resilience.
"""

from __future__ import annotations

import time

import pytest

import allure
from smfs_qa.schemas import WsStreamHello
from smfs_qa.ws_routes import SolanaStreamRoute

pytestmark = [pytest.mark.solana]


@allure.feature("Solana Transaction Stream")
@allure.story("Stream Connection")
class TestStreamConnect:
    """Solana stream connection and hello message tests."""

    async def test_connect_receives_stream_hello(
        self, solana_stream_route: SolanaStreamRoute
    ) -> None:
        """Connecting to /ws/stream yields a stream_hello as the first message."""
        async with solana_stream_route.client(timeout=10) as ws:
            msg = await ws.recv_json(timeout=10)
            assert msg["type"] == "stream_hello", (
                f"Expected stream_hello, got type={msg.get('type')}"
            )

    async def test_stream_hello_schema_validates(
        self, solana_stream_route: SolanaStreamRoute
    ) -> None:
        """stream_hello conforms to WsStreamHello Pydantic model."""
        async with solana_stream_route.client(timeout=10) as ws:
            msg = await ws.recv_json(timeout=10)
            parsed = WsStreamHello.model_validate(msg)
            assert isinstance(parsed, WsStreamHello)
            assert parsed.type == "stream_hello"

    async def test_stream_hello_server_time_within_30s(
        self, solana_stream_route: SolanaStreamRoute
    ) -> None:
        """stream_hello.serverTime is within 30 seconds of local clock."""
        async with solana_stream_route.client(timeout=10) as ws:
            msg = await ws.recv_json(timeout=10)
            parsed = WsStreamHello.model_validate(msg)
            now_ms = time.time() * 1000
            drift = abs(now_ms - parsed.serverTime)
            assert drift < 30_000, f"Server time drift {drift:.0f}ms exceeds 30s"

    async def test_multiple_stream_connections_independent(
        self, solana_stream_route: SolanaStreamRoute
    ) -> None:
        """Two concurrent stream connections each receive their own hello."""
        async with solana_stream_route.client(timeout=10) as ws1:
            async with solana_stream_route.client(timeout=10) as ws2:
                msg1 = await ws1.recv_json(timeout=10)
                msg2 = await ws2.recv_json(timeout=10)
                assert msg1["type"] == "stream_hello"
                assert msg2["type"] == "stream_hello"

    async def test_stream_graceful_close(self, solana_stream_route: SolanaStreamRoute) -> None:
        """Stream connection can be closed gracefully without error."""
        ws = solana_stream_route.client(timeout=10)
        await ws.connect()
        msg = await ws.recv_json(timeout=10)
        assert msg["type"] == "stream_hello"
        await ws.close()

    async def test_invalid_json_does_not_crash_connection(
        self, solana_stream_route: SolanaStreamRoute
    ) -> None:
        """Sending invalid JSON does not crash the stream connection."""
        async with solana_stream_route.client(timeout=10) as ws:
            hello = await ws.recv_json(timeout=10)
            assert hello["type"] == "stream_hello"
            await ws.ws.send("not valid json {{{")
            await ws.send_json({"type": "ping"})
            try:
                msg = await ws.recv_json(timeout=5)
                assert "type" in msg
            except TimeoutError:
                pass

    async def test_text_message_does_not_crash_connection(
        self, solana_stream_route: SolanaStreamRoute
    ) -> None:
        """Sending a plain text message does not crash the connection."""
        async with solana_stream_route.client(timeout=10) as ws:
            hello = await ws.recv_json(timeout=10)
            assert hello["type"] == "stream_hello"
            await ws.ws.send("hello world")
            await ws.send_json({"type": "ping"})
            try:
                msg = await ws.recv_json(timeout=5)
                assert "type" in msg
            except TimeoutError:
                pass
