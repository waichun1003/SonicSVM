"""REST API latency benchmarks with SLA thresholds.

Measures p50/p95/p99 response times for each REST endpoint.
/stats has known bimodal latency (F-PERF-001): p95/p99 xfail.

SLA thresholds account for ~190ms network RTT to the server.
"""

from __future__ import annotations

import time

import pytest

import allure
from smfs_qa.client import SMFSClient
from smfs_qa.perf import LatencyTracker

pytestmark = [pytest.mark.perf]

SAMPLE_SIZE = 50

FAST_ENDPOINTS = ["/health", "/markets", "/markets/BTC-PERP/snapshot"]
FAST_SLA = {
    "/health": {"p50": 300, "p95": 600, "p99": 1000},
    "/markets": {"p50": 300, "p95": 600, "p99": 1000},
    "/markets/BTC-PERP/snapshot": {"p50": 400, "p95": 800, "p99": 1500},
}
STATS_SLA = {"p50": 300, "p95": 1000, "p99": 2000}


async def _measure(client: SMFSClient, path: str, n: int) -> LatencyTracker:
    tracker = LatencyTracker()
    for _ in range(n):
        start = time.perf_counter()
        await client.get(path)
        tracker.record((time.perf_counter() - start) * 1000)
    return tracker


@allure.feature("Performance")
@allure.story("REST Latency SLA")
class TestFastEndpointLatency:
    """p50/p95/p99 SLA checks for fast REST endpoints."""

    @pytest.mark.parametrize("path", FAST_ENDPOINTS)
    async def test_p50(self, warmed_client: SMFSClient, path: str) -> None:
        t = await _measure(warmed_client, path, SAMPLE_SIZE)
        assert t.p50 < FAST_SLA[path]["p50"], f"{path} p50={t.p50:.0f}ms"

    @pytest.mark.parametrize("path", FAST_ENDPOINTS)
    async def test_p95(self, warmed_client: SMFSClient, path: str) -> None:
        t = await _measure(warmed_client, path, SAMPLE_SIZE)
        assert t.p95 < FAST_SLA[path]["p95"], f"{path} p95={t.p95:.0f}ms"

    @pytest.mark.parametrize("path", FAST_ENDPOINTS)
    async def test_p99(self, warmed_client: SMFSClient, path: str) -> None:
        t = await _measure(warmed_client, path, SAMPLE_SIZE)
        assert t.p99 < FAST_SLA[path]["p99"], f"{path} p99={t.p99:.0f}ms"


@allure.feature("Performance")
@allure.story("REST Latency SLA")
class TestStatsLatency:
    """/stats has bimodal latency: ~90% fast, ~10% slow (F-PERF-001)."""

    async def test_p50(self, warmed_client: SMFSClient) -> None:
        t = await _measure(warmed_client, "/stats", SAMPLE_SIZE)
        assert t.p50 < STATS_SLA["p50"], f"/stats p50={t.p50:.0f}ms"

    @pytest.mark.xfail(
        reason="F-PERF-001: /stats p95 bimodal aggregation latency",
        strict=True,
    )
    @pytest.mark.finding
    async def test_p95(self, warmed_client: SMFSClient) -> None:
        t = await _measure(warmed_client, "/stats", SAMPLE_SIZE)
        assert t.p95 < STATS_SLA["p95"], (
            f"/stats p95={t.p95:.0f}ms (p50={t.p50:.0f}ms, bimodal)"
        )

    @pytest.mark.xfail(
        reason="F-PERF-001: /stats p99 bimodal aggregation latency",
        strict=True,
    )
    @pytest.mark.finding
    async def test_p99(self, warmed_client: SMFSClient) -> None:
        t = await _measure(warmed_client, "/stats", SAMPLE_SIZE)
        assert t.p99 < STATS_SLA["p99"], (
            f"/stats p99={t.p99:.0f}ms (p50={t.p50:.0f}ms, bimodal)"
        )
