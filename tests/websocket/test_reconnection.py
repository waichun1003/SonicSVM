"""Tests for WebSocket reconnection behavior.

Validates that after disconnecting and reconnecting, a new
hello message is received and the data stream resumes.
"""

from __future__ import annotations

import asyncio

import pytest

import allure
from smfs_qa.ws_routes import MarketFeedRoute

pytestmark = [pytest.mark.websocket]


@allure.feature("WebSocket Market Feed")
@allure.story("Reconnection")
class TestReconnection:
    """WebSocket disconnect and reconnect resilience tests."""

    async def test_reconnect_receives_new_hello(self, market_feed_route: MarketFeedRoute) -> None:
        """After disconnect and reconnect, a fresh hello message is received."""
        # First connection
        async with market_feed_route.client(timeout=10) as ws:
            hello1 = await ws.recv_json(timeout=10)
            assert hello1["type"] == "hello"

        # Brief pause then reconnect
        await asyncio.sleep(0.5)

        # Second connection
        async with market_feed_route.client(timeout=10) as ws:
            hello2 = await ws.recv_json(timeout=10)
            assert hello2["type"] == "hello"
            assert hello2["marketId"] == "BTC-PERP"

    async def test_reconnect_data_stream_resumes(self, market_feed_route: MarketFeedRoute) -> None:
        """After reconnect, book_delta and trade messages resume flowing."""
        # First connection -- receive some data
        async with market_feed_route.client(timeout=15) as ws:
            await ws.recv_json(timeout=10)  # hello
            msg1 = await ws.recv_json(timeout=10)
            assert msg1["type"] in ("book_delta", "trade")

        await asyncio.sleep(0.5)

        # Reconnect -- data should resume
        async with market_feed_route.client(timeout=15) as ws:
            await ws.recv_json(timeout=10)  # hello
            messages = await ws.collect_messages(count=5, timeout=10)
            types = {m["type"] for m in messages}
            assert "book_delta" in types, f"Expected book_delta after reconnect, got types: {types}"

    async def test_reconnect_seq_continues_from_server_state(
        self, market_feed_route: MarketFeedRoute
    ) -> None:
        """After reconnect, seq numbers continue from server state (not reset to 0)."""
        # First connection -- capture last seq
        async with market_feed_route.client(timeout=15) as ws:
            await ws.recv_json(timeout=10)  # hello
            messages = await ws.collect_messages(count=10, timeout=10)
            deltas = [m for m in messages if m.get("type") == "book_delta"]
            if deltas:
                last_seq = deltas[-1]["seq"]
            else:
                pytest.skip("No book_delta messages in first connection")

        await asyncio.sleep(0.5)

        # Reconnect -- seq should be >= last_seq (server continues)
        async with market_feed_route.client(timeout=15) as ws:
            await ws.recv_json(timeout=10)  # hello
            msg = await ws.drain_until("book_delta", timeout=10)
            new_seq = msg["seq"]
            assert new_seq >= last_seq, f"Expected seq >= {last_seq} after reconnect, got {new_seq}"

    async def test_rapid_reconnect_succeeds(self, market_feed_route: MarketFeedRoute) -> None:
        """Rapid disconnect-reconnect (no delay) still establishes a valid session."""
        # First connection
        async with market_feed_route.client(timeout=10) as ws:
            hello = await ws.recv_json(timeout=10)
            assert hello["type"] == "hello"

        # Immediately reconnect (no sleep)
        async with market_feed_route.client(timeout=10) as ws:
            hello = await ws.recv_json(timeout=10)
            assert hello["type"] == "hello"
            assert hello["marketId"] == "BTC-PERP"
