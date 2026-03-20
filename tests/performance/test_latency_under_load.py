"""Latency degradation and error rate under concurrent load.

Tests whether latency degrades with concurrent requests,
and verifies the /snapshot 500 error rate (F-PERF-003).
"""

from __future__ import annotations

import asyncio
import time

import pytest

import allure
from smfs_qa.client import SMFSClient
from smfs_qa.perf import LatencyTracker

pytestmark = [pytest.mark.perf]


async def _concurrent_latency(
    url: str, path: str, concurrency: int, per_client: int = 5
) -> tuple[LatencyTracker, int]:
    tracker = LatencyTracker()
    errors = 0

    async def _worker() -> None:
        nonlocal errors
        async with SMFSClient(url, timeout=15) as client:
            for _ in range(per_client):
                start = time.perf_counter()
                try:
                    resp = await client.get(path)
                    tracker.record((time.perf_counter() - start) * 1000)
                    if resp.status_code >= 500:
                        errors += 1
                except Exception:
                    errors += 1

    await asyncio.gather(*[_worker() for _ in range(concurrency)])
    return tracker, errors


@allure.feature("Performance")
@allure.story("Latency Under Load")
class TestLatencyUnderLoad:
    """REST latency degradation under concurrent load."""

    async def test_health_5_concurrent(self, base_url: str) -> None:
        """GET /health p95 < 1000ms under 5 concurrent clients."""
        t, errs = await _concurrent_latency(base_url, "/health", 5, 10)
        assert errs == 0, f"{errs} errors"
        assert t.p95 < 1000, f"p95={t.p95:.0f}ms > 1000ms"

    async def test_health_10_concurrent(self, base_url: str) -> None:
        """GET /health p95 < 2000ms under 10 concurrent clients."""
        t, errs = await _concurrent_latency(base_url, "/health", 10, 5)
        assert errs == 0, f"{errs} errors"
        assert t.p95 < 2000, f"p95={t.p95:.0f}ms > 2000ms"

    async def test_snapshot_error_rate(self, base_url: str) -> None:
        """GET /snapshot error rate < 20% under 10 concurrent.

        F-PERF-003: Locust found ~10% HTTP 500 on /snapshot under load.
        """
        t, errs = await _concurrent_latency(base_url, "/markets/BTC-PERP/snapshot", 10, 5)
        total = t.count + errs
        rate = errs / total if total > 0 else 0
        assert rate < 0.20, f"Error rate {rate:.0%} ({errs}/{total}) > 20%"

    async def test_stats_bimodal(self, base_url: str) -> None:
        """GET /stats shows bimodal latency (fast p50, slow p95)."""
        t, _ = await _concurrent_latency(base_url, "/stats", 3, 20)
        assert t.p50 < 500, f"p50={t.p50:.0f}ms > 500ms"
        assert t.p95 < 5000, f"p95={t.p95:.0f}ms > 5000ms"


@allure.feature("Performance")
@allure.story("Latency Under Load")
class TestBurstMultiEndpoint:
    """Burst traffic on non-/health endpoints."""

    async def test_burst_markets(self, base_url: str) -> None:
        """20 concurrent GET /markets all succeed."""
        async with SMFSClient(base_url, timeout=10) as client:
            tasks = [client.get("/markets") for _ in range(20)]
            resps = await asyncio.gather(*tasks, return_exceptions=True)
            ok = sum(1 for r in resps if not isinstance(r, Exception) and r.status_code == 200)
            assert ok == 20, f"{ok}/20"

    async def test_burst_stats(self, base_url: str) -> None:
        """20 concurrent GET /stats >= 90% success."""
        async with SMFSClient(base_url, timeout=15) as client:
            tasks = [client.get("/stats") for _ in range(20)]
            resps = await asyncio.gather(*tasks, return_exceptions=True)
            ok = sum(1 for r in resps if not isinstance(r, Exception) and r.status_code == 200)
            assert ok / 20 >= 0.90, f"{ok}/20 = {ok / 20:.0%}"

    async def test_burst_snapshot_errors(self, base_url: str) -> None:
        """20 concurrent GET /snapshot error rate < 25%."""
        async with SMFSClient(base_url, timeout=15) as client:
            tasks = [client.get("/markets/BTC-PERP/snapshot") for _ in range(20)]
            resps = await asyncio.gather(*tasks, return_exceptions=True)
            errs = sum(1 for r in resps if isinstance(r, Exception) or r.status_code >= 500)
            assert errs / 20 < 0.25, f"Error rate {errs}/20 = {errs / 20:.0%}"
