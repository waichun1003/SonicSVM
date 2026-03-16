"""Base route class for POM Route Model."""

from __future__ import annotations

from typing import Any

import httpx

from smfs_qa.client import SMFSClient


class BaseRoute:
    """Base class for REST API route models."""

    path: str = ""

    def __init__(self, client: SMFSClient) -> None:
        self.client = client

    async def get(self, **kwargs: Any) -> httpx.Response:
        return await self.client.get(self.path, **kwargs)

    async def post(self, **kwargs: Any) -> httpx.Response:
        return await self.client.post(self.path, **kwargs)

    async def request(self, method: str, **kwargs: Any) -> httpx.Response:
        return await self.client.request(method, self.path, **kwargs)
