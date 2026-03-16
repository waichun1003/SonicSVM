"""Health endpoint route."""

from __future__ import annotations

from smfs_qa.routes.base import BaseRoute
from smfs_qa.schemas import HealthResponse


class HealthRoute(BaseRoute):
    path = "/health"

    async def get_health(self) -> HealthResponse:
        resp = await self.get()
        resp.raise_for_status()
        return HealthResponse.model_validate(resp.json())
