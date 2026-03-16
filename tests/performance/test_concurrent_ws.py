"""Concurrent WebSocket connection scaling tests."""

from __future__ import annotations

import asyncio

import pytest

import allure
from smfs_qa.ws_client import WSTestClient

pytestmark = [pytest.mark.perf]

WS_URL = "wss://interviews-api.sonic.game/ws?marketId=BTC-PERP"


async def _connect_and_verify(url: str, timeout: float) -> bool:
    try:
        async with WSTestClient(url, timeout=timeout) as ws:
            msg = await ws.recv_json(timeout=timeout)
            return msg.get("type") == "hello"
    except Exception:
        return False


@allure.feature("Performance")
@allure.story("Concurrent Connections")
class TestConcurrentWs:
    """WebSocket concurrent connection scaling."""

    async def test_5_connections(self) -> None:
        """5 concurrent connections all receive hello."""
        results = await asyncio.gather(*[_connect_and_verify(WS_URL, 10) for _ in range(5)])
        assert all(results), f"{sum(results)}/5 succeeded"

    async def test_10_connections(self) -> None:
        """10 concurrent connections >= 90% success."""
        results = await asyncio.gather(*[_connect_and_verify(WS_URL, 15) for _ in range(10)])
        rate = sum(results) / len(results)
        assert rate >= 0.9, f"{sum(results)}/10 = {rate:.0%} (need 90%)"
