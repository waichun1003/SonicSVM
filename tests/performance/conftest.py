"""Performance test fixtures."""

from __future__ import annotations

import pytest_asyncio

from smfs_qa.client import SMFSClient

BASE_URL = "https://interviews-api.sonic.game"
WARMUP_REQUESTS = 5


@pytest_asyncio.fixture
async def warmed_client():
    """API client with warm-up requests already completed."""
    async with SMFSClient(BASE_URL) as client:
        for _ in range(WARMUP_REQUESTS):
            await client.get("/health")
        yield client
