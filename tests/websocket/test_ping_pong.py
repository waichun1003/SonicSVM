"""Tests for WebSocket ping/pong keepalive protocol.

Validates that the server responds to ping messages with pong,
verifies pong schema, and tests keepalive behavior.
"""

from __future__ import annotations

import time

import pytest

import allure
from smfs_qa.schemas import WsPong
from smfs_qa.ws_routes import MarketFeedRoute

pytestmark = [pytest.mark.websocket]


@allure.feature("WebSocket Market Feed")
@allure.story("Ping/Pong Keepalive")
class TestPingPong:
    """WebSocket ping/pong keepalive tests."""

    async def test_ping_receives_pong(self, market_feed_route: MarketFeedRoute) -> None:
        """Sending a ping message yields a pong response within the data stream."""
        async with market_feed_route.client(timeout=15) as ws:
            # Consume hello
            hello = await ws.recv_json(timeout=10)
            assert hello["type"] == "hello"

            # Send ping
            await ws.send_json({"type": "ping"})

            # Drain messages looking for pong (may be interleaved with data)
            pong = await ws.drain_until("pong", timeout=10)
            assert pong["type"] == "pong"

    async def test_pong_schema_validates(self, market_feed_route: MarketFeedRoute) -> None:
        """pong message conforms to WsPong Pydantic model (type, ts)."""
        async with market_feed_route.client(timeout=15) as ws:
            await ws.recv_json(timeout=10)  # hello
            await ws.send_json({"type": "ping"})
            pong = await ws.drain_until("pong", timeout=10)
            parsed = WsPong.model_validate(pong)
            assert isinstance(parsed, WsPong)
            assert parsed.type == "pong"

    async def test_pong_timestamp_is_recent(self, market_feed_route: MarketFeedRoute) -> None:
        """pong.ts is a recent epoch-millisecond timestamp (within 30s of now)."""
        async with market_feed_route.client(timeout=15) as ws:
            await ws.recv_json(timeout=10)  # hello
            await ws.send_json({"type": "ping"})
            pong = await ws.drain_until("pong", timeout=10)
            parsed = WsPong.model_validate(pong)
            now_ms = time.time() * 1000
            drift = abs(now_ms - parsed.ts)
            assert drift < 30_000, f"Pong timestamp drift {drift:.0f}ms exceeds 30s"

    async def test_multiple_pings_receive_pongs(self, market_feed_route: MarketFeedRoute) -> None:
        """Sending 3 sequential pings each receive a pong response."""
        async with market_feed_route.client(timeout=30) as ws:
            await ws.recv_json(timeout=10)  # hello

            pong_count = 0
            for _ in range(3):
                await ws.send_json({"type": "ping"})
                try:
                    pong = await ws.drain_until("pong", timeout=10)
                    if pong["type"] == "pong":
                        pong_count += 1
                except TimeoutError:
                    pass

            assert pong_count == 3, f"Expected 3 pong responses for 3 pings, got {pong_count}"
