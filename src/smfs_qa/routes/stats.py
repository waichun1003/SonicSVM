"""Stats endpoint route."""

from __future__ import annotations

from smfs_qa.routes.base import BaseRoute
from smfs_qa.schemas import StatsResponse


class StatsRoute(BaseRoute):
    path = "/stats"

    async def get_stats(self) -> StatsResponse:
        resp = await self.get()
        resp.raise_for_status()
        return StatsResponse.model_validate(resp.json())
