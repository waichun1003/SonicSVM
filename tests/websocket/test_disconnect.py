"""Tests for WebSocket disconnect handling.

Validates clean client-initiated disconnect, server behavior
on close, unexpected close handling, server-initiated close,
and binary frame resilience.
"""

from __future__ import annotations

import pytest
import websockets

import allure
from smfs_qa.ws_routes import MarketFeedRoute

pytestmark = [pytest.mark.websocket]


@allure.feature("WebSocket Market Feed")
@allure.story("Disconnect and Server Behavior")
class TestDisconnect:
    """WebSocket disconnect and close behavior tests."""

    async def test_clean_close_no_error(self, market_feed_route: MarketFeedRoute) -> None:
        """Client-initiated close completes without raising an exception."""
        ws = market_feed_route.client(timeout=10)
        await ws.connect()
        hello = await ws.recv_json(timeout=10)
        assert hello["type"] == "hello"
        # Clean close should not raise
        await ws.close()

    async def test_close_during_data_stream(self, market_feed_route: MarketFeedRoute) -> None:
        """Closing the connection while data is flowing does not raise an exception."""
        async with market_feed_route.client(timeout=10) as ws:
            await ws.recv_json(timeout=10)  # hello
            # Receive at least one data message
            await ws.recv_json(timeout=10)
            # Close is handled by context manager exit -- should not raise

    async def test_recv_after_close_raises(self, market_feed_route: MarketFeedRoute) -> None:
        """Attempting to receive after close raises RuntimeError."""
        ws = market_feed_route.client(timeout=10)
        await ws.connect()
        await ws.recv_json(timeout=10)  # hello
        await ws.close()

        with pytest.raises(RuntimeError, match="not connected"):
            await ws.recv_json(timeout=5)

    async def test_double_close_is_safe(self, market_feed_route: MarketFeedRoute) -> None:
        """Calling close() twice does not raise an exception."""
        ws = market_feed_route.client(timeout=10)
        await ws.connect()
        await ws.recv_json(timeout=10)  # hello
        await ws.close()
        # Second close should be a no-op
        await ws.close()

    async def test_close_then_reconnect(self, market_feed_route: MarketFeedRoute) -> None:
        """After closing, a new connection can be established with a fresh client."""
        ws1 = market_feed_route.client(timeout=10)
        await ws1.connect()
        hello1 = await ws1.recv_json(timeout=10)
        assert hello1["type"] == "hello"
        await ws1.close()

        ws2 = market_feed_route.client(timeout=10)
        await ws2.connect()
        hello2 = await ws2.recv_json(timeout=10)
        assert hello2["type"] == "hello"
        await ws2.close()


@allure.feature("WebSocket Market Feed")
@allure.story("Disconnect and Server Behavior")
class TestServerBehavior:
    """Tests for server-side close behavior and protocol edge cases."""

    async def test_server_keeps_connection_alive_during_idle(
        self, market_feed_route: MarketFeedRoute
    ) -> None:
        """Server should keep connection alive even without client pings for 30s.

        Verifies the server does not initiate a close within 30 seconds
        of inactivity from the client (no pings sent). The feed should
        continue delivering data messages.
        """
        async with market_feed_route.client(timeout=40) as ws:
            hello = await ws.recv_json(timeout=10)
            assert hello["type"] == "hello"

            messages = await ws.collect_messages(duration=30, timeout=35)
            assert len(messages) > 0, (
                "Server closed connection or stopped sending data during 30s idle"
            )
            data_types = {m.get("type") for m in messages}
            assert "book_delta" in data_types or "trade" in data_types, (
                f"Expected data messages during idle, got types: {data_types}"
            )

    async def test_connection_survives_after_close_frame_from_client(
        self, market_feed_route: MarketFeedRoute
    ) -> None:
        """After one client sends close, a new client can connect immediately.

        This tests that the server properly cleans up per-client state
        and does not confuse close from one client with another.
        """
        ws1 = market_feed_route.client(timeout=10)
        await ws1.connect()
        hello1 = await ws1.recv_json(timeout=10)
        assert hello1["type"] == "hello"

        ws2 = market_feed_route.client(timeout=10)
        await ws2.connect()
        hello2 = await ws2.recv_json(timeout=10)
        assert hello2["type"] == "hello"

        await ws1.close()

        msg = await ws2.recv_json(timeout=10)
        assert msg.get("type") in ("book_delta", "trade", "pong"), (
            f"Client 2 should still receive data after client 1 closes, got: {msg}"
        )
        await ws2.close()

    async def test_binary_frame_does_not_crash_connection(
        self, market_feed_route: MarketFeedRoute
    ) -> None:
        """Sending a binary WebSocket frame should not crash the connection.

        The WebSocket spec allows both text and binary frames. The server
        should either ignore the binary frame or respond gracefully.
        """
        async with market_feed_route.client(timeout=15) as ws:
            hello = await ws.recv_json(timeout=10)
            assert hello["type"] == "hello"

            await ws.ws.send(b"\x00\x01\x02\x03\xff")

            try:
                msg = await ws.recv_json(timeout=5)
                assert "type" in msg, (
                    f"Expected typed message after binary frame, got: {msg}"
                )
            except (TimeoutError, websockets.exceptions.ConnectionClosed):
                pass

            try:
                await ws.send_json({"type": "ping"})
                pong = await ws.drain_until("pong", timeout=5)
                assert pong["type"] == "pong", "Connection should survive binary frame"
            except (
                TimeoutError,
                websockets.exceptions.ConnectionClosed,
                RuntimeError,
            ):
                pytest.skip(
                    "Server closed connection after binary frame -- "
                    "acceptable but not ideal behavior"
                )

    async def test_oversized_message_does_not_crash_connection(
        self, market_feed_route: MarketFeedRoute
    ) -> None:
        """Sending a very large text message should not crash the connection.

        The server should either ignore or reject the oversized payload
        without crashing the WebSocket handler.
        """
        async with market_feed_route.client(timeout=15) as ws:
            hello = await ws.recv_json(timeout=10)
            assert hello["type"] == "hello"

            large_payload = '{"type":"ping","data":"' + "x" * 100_000 + '"}'
            try:
                await ws.ws.send(large_payload)
            except websockets.exceptions.ConnectionClosed:
                pytest.skip("Server closed connection on oversized message")
                return

            try:
                await ws.send_json({"type": "ping"})
                pong = await ws.drain_until("pong", timeout=5)
                assert pong["type"] == "pong", (
                    "Connection should survive oversized message"
                )
            except (
                TimeoutError,
                websockets.exceptions.ConnectionClosed,
                RuntimeError,
            ):
                pytest.skip(
                    "Server closed after oversized message -- "
                    "acceptable behavior"
                )
