"""WebSocket message throughput and hello latency benchmarks."""

from __future__ import annotations

import time

import pytest

import allure
from smfs_qa.ws_routes import MarketFeedRoute

pytestmark = [pytest.mark.perf]

COLLECTION_SECONDS = 30


@allure.feature("Performance")
@allure.story("WebSocket Throughput")
class TestWsThroughput:
    """WebSocket message rate and connection setup time."""

    async def test_message_rate_above_1_per_second(
        self, market_feed_route: MarketFeedRoute
    ) -> None:
        """Feed delivers >= 1 data message/sec over 30s."""
        async with market_feed_route.client(timeout=COLLECTION_SECONDS + 10) as ws:
            hello = await ws.recv_json(timeout=10)
            assert hello["type"] == "hello"
            msgs = await ws.collect_messages(duration=COLLECTION_SECONDS)
            data = [m for m in msgs if m.get("type") in ("book_delta", "trade")]
            rate = len(data) / COLLECTION_SECONDS
            assert rate >= 1.0, f"Rate {rate:.1f}/s below 1.0/s ({len(data)} msgs)"

    async def test_hello_latency_under_2s(
        self, market_feed_route: MarketFeedRoute
    ) -> None:
        """Time from connect to hello message < 2000ms."""
        start = time.perf_counter()
        async with market_feed_route.client(timeout=10) as ws:
            hello = await ws.recv_json(timeout=10)
            elapsed = (time.perf_counter() - start) * 1000
            assert hello["type"] == "hello"
            assert elapsed < 2000, f"Hello latency {elapsed:.0f}ms > 2000ms"
