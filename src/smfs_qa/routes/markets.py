"""Markets endpoint route."""

from __future__ import annotations

from smfs_qa.routes.base import BaseRoute
from smfs_qa.schemas import MarketsResponse


class MarketsRoute(BaseRoute):
    path = "/markets"

    async def get_markets(self) -> MarketsResponse:
        resp = await self.get()
        resp.raise_for_status()
        return MarketsResponse.model_validate(resp.json())
