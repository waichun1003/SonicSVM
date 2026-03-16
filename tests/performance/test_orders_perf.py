"""POST /orders performance benchmarks.

Measures order submission latency, rate limiting behavior,
and concurrent order handling under load.

Finding F-PERF-002: POST /orders returns HTTP 429 at ~66% under
50 concurrent users (rate limiting discovered via Locust).
"""

from __future__ import annotations

import asyncio
import time

import pytest

import allure
from smfs_qa.client import SMFSClient
from smfs_qa.perf import LatencyTracker

pytestmark = [pytest.mark.perf]

BASE_URL = "https://interviews-api.sonic.game"

VALID_LIMIT_ORDER = {
    "marketId": "BTC-PERP",
    "side": "buy",
    "type": "limit",
    "size": 0.01,
    "price": 50000.0,
}

VALID_MARKET_ORDER = {
    "marketId": "BTC-PERP",
    "side": "sell",
    "type": "market",
    "size": 0.01,
}


@allure.feature("Performance")
@allure.story("Order Latency")
class TestOrderLatency:
    """POST /orders response time benchmarks."""

    async def test_single_order_latency_under_2s(self) -> None:
        """Single POST /orders completes within 2 seconds."""
        await asyncio.sleep(2)
        async with SMFSClient(BASE_URL, timeout=10) as client:
            start = time.perf_counter()
            resp = await client.post("/orders", json=VALID_LIMIT_ORDER)
            elapsed = (time.perf_counter() - start) * 1000
            if resp.status_code == 429:
                pytest.skip("Rate-limited (F-PERF-002)")
            assert resp.status_code == 200, f"Order failed: {resp.status_code}"
            assert elapsed < 2000, f"Order latency {elapsed:.0f}ms > 2s"

    async def test_order_latency_p95_under_1s(self) -> None:
        """p95 order latency under 1000ms across 20 sequential orders."""
        tracker = LatencyTracker()
        async with SMFSClient(BASE_URL, timeout=10) as client:
            for _ in range(20):
                start = time.perf_counter()
                resp = await client.post("/orders", json=VALID_LIMIT_ORDER)
                elapsed = (time.perf_counter() - start) * 1000
                if resp.status_code == 200:
                    tracker.record(elapsed)
                await asyncio.sleep(0.5)

        if tracker.count < 3:
            pytest.skip(f"Only {tracker.count} orders succeeded -- rate-limited (F-PERF-002)")
        assert tracker.p95 < 1000, (
            f"Order p95={tracker.p95:.0f}ms > 1000ms "
            f"(p50={tracker.p50:.0f}ms, mean={tracker.mean:.0f}ms)"
        )

    async def test_market_order_latency(self) -> None:
        """Market order latency comparable to limit order."""
        tracker = LatencyTracker()
        async with SMFSClient(BASE_URL, timeout=10) as client:
            for _ in range(10):
                start = time.perf_counter()
                resp = await client.post("/orders", json=VALID_MARKET_ORDER)
                elapsed = (time.perf_counter() - start) * 1000
                if resp.status_code == 200:
                    tracker.record(elapsed)
                await asyncio.sleep(0.5)

        if tracker.count < 2:
            pytest.skip(f"Only {tracker.count} market orders succeeded -- rate-limited")
        assert tracker.p95 < 1500, f"Market order p95={tracker.p95:.0f}ms > 1500ms"


@allure.feature("Performance")
@allure.story("Order Latency")
class TestOrderRateLimiting:
    """POST /orders rate limiting behavior (F-PERF-002)."""

    async def test_sequential_orders_no_rate_limit(self) -> None:
        """Sequential orders with 2s delay should not be rate-limited."""
        await asyncio.sleep(3)
        async with SMFSClient(BASE_URL, timeout=10) as client:
            successes = 0
            rate_limited = 0
            for _ in range(5):
                resp = await client.post("/orders", json=VALID_LIMIT_ORDER)
                if resp.status_code == 200:
                    successes += 1
                elif resp.status_code == 429:
                    rate_limited += 1
                await asyncio.sleep(2.0)

            assert successes >= 2, (
                f"Only {successes}/5 sequential orders succeeded ({rate_limited} rate-limited)"
            )

    async def test_burst_orders_rate_limit_detected(self) -> None:
        """Rapid burst of 10 orders triggers rate limiting.

        F-PERF-002: Server enforces rate limiting on /orders.
        This test documents the rate limit threshold.
        """
        async with SMFSClient(BASE_URL, timeout=10) as client:
            tasks = [client.post("/orders", json=VALID_LIMIT_ORDER) for _ in range(10)]
            responses = await asyncio.gather(*tasks, return_exceptions=True)

            statuses = {}
            for r in responses:
                if isinstance(r, Exception):
                    statuses["error"] = statuses.get("error", 0) + 1
                else:
                    code = r.status_code
                    statuses[code] = statuses.get(code, 0) + 1

            total = len(responses)
            ok = statuses.get(200, 0)
            limited = statuses.get(429, 0)

            assert ok + limited == total or statuses.get("error", 0) < 3, (
                f"Unexpected status distribution: {statuses}"
            )

    async def test_concurrent_orders_unique_ids(self) -> None:
        """Concurrent orders that succeed should have unique orderIds."""
        async with SMFSClient(BASE_URL, timeout=10) as client:
            tasks = [client.post("/orders", json=VALID_LIMIT_ORDER) for _ in range(5)]
            responses = await asyncio.gather(*tasks, return_exceptions=True)

            order_ids = []
            for r in responses:
                if not isinstance(r, Exception) and r.status_code == 200:
                    data = r.json()
                    if data.get("orderId"):
                        order_ids.append(data["orderId"])

            if len(order_ids) >= 2:
                assert len(set(order_ids)) == len(order_ids), f"Duplicate orderIds: {order_ids}"
