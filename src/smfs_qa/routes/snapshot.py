"""Snapshot endpoint route."""

from __future__ import annotations

import httpx

from smfs_qa.routes.base import BaseRoute
from smfs_qa.schemas import SnapshotResponse


class SnapshotRoute(BaseRoute):
    path = "/markets/{market_id}/snapshot"

    async def get_snapshot(self, market_id: str = "BTC-PERP") -> httpx.Response:
        return await self.client.get(f"/markets/{market_id}/snapshot")

    async def get_snapshot_parsed(self, market_id: str = "BTC-PERP") -> SnapshotResponse:
        resp = await self.get_snapshot(market_id)
        resp.raise_for_status()
        return SnapshotResponse.model_validate(resp.json())
