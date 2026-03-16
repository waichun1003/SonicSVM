"""Orders endpoint route."""

from __future__ import annotations

import httpx

from smfs_qa.routes.base import BaseRoute
from smfs_qa.schemas import OrderRequest, OrderResponse


class OrdersRoute(BaseRoute):
    path = "/orders"

    async def post_order(self, order: OrderRequest) -> httpx.Response:
        return await self.client.post(self.path, json=order.model_dump(exclude_none=True))

    async def post_order_parsed(self, order: OrderRequest) -> OrderResponse:
        resp = await self.post_order(order)
        resp.raise_for_status()
        return OrderResponse.model_validate(resp.json())

    async def get_orders(self) -> httpx.Response:
        return await self.client.get(self.path)
