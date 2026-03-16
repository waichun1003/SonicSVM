"""Tests for Solana stream ping/pong keepalive.

Validates that the stream endpoint responds to ping messages with pong.
"""

from __future__ import annotations

import time

import pytest

import allure
from smfs_qa.schemas import WsPong
from smfs_qa.ws_routes import SolanaStreamRoute

pytestmark = [pytest.mark.solana]


@allure.feature("Solana Transaction Stream")
@allure.story("Stream Ping/Pong")
class TestStreamPing:
    """Solana stream ping/pong tests."""

    async def test_stream_ping_receives_pong(self, solana_stream_route: SolanaStreamRoute) -> None:
        """Sending ping on stream yields a pong response."""
        async with solana_stream_route.client(timeout=15) as ws:
            hello = await ws.recv_json(timeout=10)
            assert hello["type"] == "stream_hello"
            await ws.send_json({"type": "ping"})
            pong = await ws.drain_until("pong", timeout=10)
            assert pong["type"] == "pong"

    async def test_stream_pong_schema_validates(
        self, solana_stream_route: SolanaStreamRoute
    ) -> None:
        """Stream pong conforms to WsPong Pydantic model."""
        async with solana_stream_route.client(timeout=15) as ws:
            await ws.recv_json(timeout=10)
            await ws.send_json({"type": "ping"})
            pong = await ws.drain_until("pong", timeout=10)
            parsed = WsPong.model_validate(pong)
            assert isinstance(parsed, WsPong)

    async def test_stream_pong_timestamp_is_recent(
        self, solana_stream_route: SolanaStreamRoute
    ) -> None:
        """Stream pong.ts is within 30s of local clock."""
        async with solana_stream_route.client(timeout=15) as ws:
            await ws.recv_json(timeout=10)
            await ws.send_json({"type": "ping"})
            pong = await ws.drain_until("pong", timeout=10)
            parsed = WsPong.model_validate(pong)
            now_ms = time.time() * 1000
            drift = abs(now_ms - parsed.ts)
            assert drift < 30_000, f"Pong timestamp drift {drift:.0f}ms exceeds 30s"
