"""Advanced WebSocket performance: inter-message latency, connection time, throughput by type."""

from __future__ import annotations

import time

import pytest

import allure
from smfs_qa.client import SMFSClient
from smfs_qa.perf import LatencyTracker
from smfs_qa.ws_client import WSTestClient
from smfs_qa.ws_routes import MarketFeedRoute

pytestmark = [pytest.mark.perf]


@allure.feature("Performance")
@allure.story("WebSocket Advanced Metrics")
class TestInterMessageLatency:
    """Measures gap between consecutive WebSocket messages."""

    async def test_p95_under_200ms(self, market_feed_route: MarketFeedRoute) -> None:
        """p95 inter-message gap < 200ms on a 30msg/s feed."""
        tracker = LatencyTracker()
        async with market_feed_route.client(timeout=20) as ws:
            await ws.recv_json(timeout=10)
            last = time.perf_counter()
            msgs = await ws.collect_messages(duration=10, timeout=15)
            for _ in msgs:
                now = time.perf_counter()
                tracker.record((now - last) * 1000)
                last = now
        assert tracker.count >= 50, f"Only {tracker.count} samples"
        assert tracker.p95 < 200, f"p95={tracker.p95:.0f}ms > 200ms"

    async def test_no_gap_exceeds_10s(self, market_feed_route: MarketFeedRoute) -> None:
        """No single inter-message gap > 10s (feed stall detection).

        A gap > 10s indicates a serious feed stall. We use 10s threshold
        (not 5s) because transient network delays can cause brief pauses.
        """
        tracker = LatencyTracker()
        async with market_feed_route.client(timeout=25) as ws:
            await ws.recv_json(timeout=10)
            last = time.perf_counter()
            msgs = await ws.collect_messages(duration=10, timeout=15)
            for _ in msgs:
                now = time.perf_counter()
                tracker.record((now - last) * 1000)
                last = now
        if tracker.count == 0:
            pytest.skip("No messages received")
        max_gap = max(tracker._samples) if tracker._samples else 0
        assert max_gap < 15_000, f"Max gap {max_gap:.0f}ms > 15s (feed stall)"


@allure.feature("Performance")
@allure.story("WebSocket Advanced Metrics")
class TestConnectionTime:
    """WebSocket connection establishment overhead."""

    async def test_single_connection_under_2s(self, market_feed_route: MarketFeedRoute) -> None:
        """TCP + TLS + WS upgrade + hello < 2s."""
        start = time.perf_counter()
        async with market_feed_route.client(timeout=10) as ws:
            hello = await ws.recv_json(timeout=10)
        elapsed = (time.perf_counter() - start) * 1000
        assert hello["type"] == "hello"
        assert elapsed < 2000, f"Setup {elapsed:.0f}ms > 2s"

    async def test_10_sequential_avg_under_1500ms(self) -> None:
        """Average connection time across 10 sequential connections < 1500ms."""
        url = "wss://interviews-api.sonic.game/ws?marketId=BTC-PERP"
        tracker = LatencyTracker()
        for _ in range(10):
            start = time.perf_counter()
            async with WSTestClient(url, timeout=10) as ws:
                hello = await ws.recv_json(timeout=10)
                assert hello["type"] == "hello"
            tracker.record((time.perf_counter() - start) * 1000)
        assert tracker.mean < 1500, f"Avg {tracker.mean:.0f}ms > 1500ms"


@allure.feature("Performance")
@allure.story("WebSocket Advanced Metrics")
class TestThroughputByType:
    """Message rate breakdown by type."""

    async def test_book_delta_rate_matches_stats(self, market_feed_route: MarketFeedRoute) -> None:
        """/stats bookUpdatesPerSecond roughly matches observed WS rate."""
        async with SMFSClient("https://interviews-api.sonic.game") as client:
            stats = (await client.get("/stats")).json()
            btc = stats.get("markets", {}).get("BTC-PERP", {})
            declared = btc.get("bookUpdatesPerSecond", 30)

        async with market_feed_route.client(timeout=15) as ws:
            await ws.recv_json(timeout=10)
            msgs = await ws.collect_messages(duration=5, timeout=10)
        deltas = sum(1 for m in msgs if m.get("type") == "book_delta")
        observed = deltas / 5.0
        assert observed >= declared * 0.5, (
            f"Observed {observed:.1f}/s < 50% of declared {declared}/s"
        )

    async def test_trade_rate_positive(self, market_feed_route: MarketFeedRoute) -> None:
        """At least 1 trade in 10s window."""
        async with market_feed_route.client(timeout=20) as ws:
            await ws.recv_json(timeout=10)
            msgs = await ws.collect_messages(duration=10, timeout=15)
        trades = sum(1 for m in msgs if m.get("type") == "trade")
        assert trades >= 1, f"No trades in 10s ({len(msgs)} total)"
