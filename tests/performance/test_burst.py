"""Burst traffic resilience tests."""

from __future__ import annotations

import asyncio
import time

import pytest

import allure
from smfs_qa.client import SMFSClient

pytestmark = [pytest.mark.perf]

BASE_URL = "https://interviews-api.sonic.game"


@allure.feature("Performance")
@allure.story("Burst Traffic")
class TestBurst:
    """REST burst traffic tolerance."""

    async def test_20_burst_100_percent(self) -> None:
        """20 concurrent /health requests all return 200."""
        async with SMFSClient(BASE_URL, timeout=10) as client:
            for _ in range(3):
                await client.get("/health")
            tasks = [client.get("/health") for _ in range(20)]
            resps = await asyncio.gather(*tasks, return_exceptions=True)
            ok = sum(1 for r in resps if not isinstance(r, Exception) and r.status_code == 200)
            assert ok == 20, f"Burst: {ok}/20 succeeded"

    async def test_50_burst_95_percent(self) -> None:
        """50 concurrent requests >= 95% success."""
        async with SMFSClient(BASE_URL, timeout=15) as client:
            for _ in range(3):
                await client.get("/health")
            tasks = [client.get("/health") for _ in range(50)]
            resps = await asyncio.gather(*tasks, return_exceptions=True)
            ok = sum(1 for r in resps if not isinstance(r, Exception) and r.status_code == 200)
            assert ok / 50 >= 0.95, f"Burst: {ok}/50 = {ok / 50:.0%}"

    async def test_recovery_under_2s(self) -> None:
        """After 20-request burst, next request succeeds within 2s."""
        async with SMFSClient(BASE_URL, timeout=10) as client:
            tasks = [client.get("/health") for _ in range(20)]
            await asyncio.gather(*tasks, return_exceptions=True)
            start = time.perf_counter()
            resp = await client.get("/health")
            elapsed = time.perf_counter() - start
            assert resp.status_code == 200
            assert elapsed < 2.0, f"Recovery {elapsed:.1f}s > 2s"
