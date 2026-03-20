"""Performance test fixtures."""

from __future__ import annotations

import pytest
import pytest_asyncio

from smfs_qa.client import SMFSClient

WARMUP_REQUESTS = 5


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    """Apply a 300s timeout to all performance tests in this directory."""
    marker = pytest.mark.timeout(300)
    for item in items:
        if "/performance/" in str(item.fspath):
            item.add_marker(marker)


@pytest_asyncio.fixture
async def warmed_client(base_url: str):
    """API client with warm-up requests already completed."""
    async with SMFSClient(base_url) as client:
        for _ in range(WARMUP_REQUESTS):
            await client.get("/health")
        yield client
