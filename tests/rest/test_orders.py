"""Tests for POST /orders endpoint.

Validates order submission for limit and market orders, error handling
for invalid inputs, and boundary value testing.
"""

from __future__ import annotations

import pytest

import allure
from smfs_qa.schemas import OrderRequest, OrderResponse

pytestmark = [pytest.mark.rest]


@allure.feature("REST API")
@allure.story("Order Submission")
class TestOrders:
    """POST /orders endpoint tests."""

    async def test_post_limit_order_accepted(self, orders_route) -> None:
        """Valid limit order is accepted with accepted=true."""
        order = OrderRequest(
            marketId="BTC-PERP",
            side="buy",
            type="limit",
            size=0.01,
            price=50000.0,
        )
        resp = await orders_route.post_order(order)
        assert resp.status_code == 200
        data = OrderResponse.model_validate(resp.json())
        assert data.accepted is True
        assert data.orderId, "orderId must be non-empty"

    async def test_post_market_order_accepted(self, orders_route) -> None:
        """Valid market order is accepted with HTTP 200."""
        order = OrderRequest(
            marketId="BTC-PERP",
            side="sell",
            type="market",
            size=0.01,
        )
        resp = await orders_route.post_order(order)
        assert resp.status_code == 200
        data = OrderResponse.model_validate(resp.json())
        assert data.accepted is True

    async def test_post_order_invalid_market_id(self, api_client) -> None:
        """Order with non-existent marketId returns an error (not 5xx)."""
        payload = {
            "marketId": "INVALID-MARKET",
            "side": "buy",
            "type": "limit",
            "size": 0.01,
            "price": 50000.0,
        }
        resp = await api_client.post("/orders", json=payload)
        assert resp.status_code < 500, f"Expected client error, got {resp.status_code}"

    async def test_post_order_missing_required_fields(self, api_client) -> None:
        """Order with missing required fields returns an error (not 5xx)."""
        payload = {"marketId": "BTC-PERP"}  # missing side, type, size
        resp = await api_client.post("/orders", json=payload)
        assert resp.status_code < 500, f"Expected client error, got {resp.status_code}"

    async def test_post_order_negative_size(self, api_client) -> None:
        """Order with negative size returns an error (not 5xx)."""
        payload = {
            "marketId": "BTC-PERP",
            "side": "buy",
            "type": "limit",
            "size": -1.0,
            "price": 50000.0,
        }
        resp = await api_client.post("/orders", json=payload)
        assert resp.status_code < 500, f"Expected client error, got {resp.status_code}"

    async def test_get_orders_returns_404(self, orders_route) -> None:
        """GET /orders returns 404 — only POST is documented in the API spec."""
        resp = await orders_route.get_orders()
        assert resp.status_code == 404

    async def test_post_order_zero_size(self, api_client) -> None:
        """Order with zero size returns an error (not 5xx)."""
        payload = {
            "marketId": "BTC-PERP",
            "side": "buy",
            "type": "limit",
            "size": 0,
            "price": 50000.0,
        }
        resp = await api_client.post("/orders", json=payload)
        assert resp.status_code < 500, f"Expected client error, got {resp.status_code}"

    async def test_post_order_invalid_side(self, api_client) -> None:
        """Order with invalid side value returns an error (not 5xx)."""
        payload = {
            "marketId": "BTC-PERP",
            "side": "INVALID",
            "type": "limit",
            "size": 0.01,
            "price": 50000.0,
        }
        resp = await api_client.post("/orders", json=payload)
        assert resp.status_code < 500, f"Expected client error, got {resp.status_code}"

    async def test_post_order_invalid_type(self, api_client) -> None:
        """Order with invalid type value returns an error (not 5xx)."""
        payload = {
            "marketId": "BTC-PERP",
            "side": "buy",
            "type": "INVALID_TYPE",
            "size": 0.01,
            "price": 50000.0,
        }
        resp = await api_client.post("/orders", json=payload)
        assert resp.status_code < 500, f"Expected client error, got {resp.status_code}"

    async def test_post_limit_order_without_price(self, api_client) -> None:
        """Limit order without price — server should handle gracefully."""
        payload = {
            "marketId": "BTC-PERP",
            "side": "buy",
            "type": "limit",
            "size": 0.01,
        }
        resp = await api_client.post("/orders", json=payload)
        assert resp.status_code < 500, f"Expected client error, got {resp.status_code}"

    async def test_post_order_invalid_market_returns_4xx(self, api_client) -> None:
        """Order with non-existent marketId should return 400, not just 'not 5xx'."""
        payload = {
            "marketId": "INVALID-MARKET",
            "side": "buy",
            "type": "limit",
            "size": 0.01,
            "price": 50000.0,
        }
        resp = await api_client.post("/orders", json=payload)
        assert 400 <= resp.status_code < 500, (
            f"Expected 4xx for invalid marketId, got {resp.status_code}"
        )

    async def test_post_order_error_body_has_error_field(self, api_client) -> None:
        """Error responses should contain an 'error' field in JSON body."""
        payload = {"marketId": "BTC-PERP"}
        resp = await api_client.post("/orders", json=payload)
        if resp.status_code >= 400:
            body = resp.json()
            assert "error" in body, (
                f"Expected 'error' field in error response, got keys: {list(body.keys())}"
            )


@allure.feature("REST API")
@allure.story("Order Submission")
class TestOrderIdempotency:
    """Idempotency and concurrency tests for POST /orders."""

    async def test_duplicate_orders_get_different_ids(self, orders_route) -> None:
        """Two identical orders should receive different orderIds (no dedup without key)."""
        order = OrderRequest(
            marketId="BTC-PERP",
            side="buy",
            type="limit",
            size=0.01,
            price=50000.0,
        )
        resp1 = await orders_route.post_order(order)
        resp2 = await orders_route.post_order(order)

        assert resp1.status_code == 200
        assert resp2.status_code == 200

        data1 = OrderResponse.model_validate(resp1.json())
        data2 = OrderResponse.model_validate(resp2.json())

        assert data1.orderId != data2.orderId, (
            f"Duplicate orders got same orderId: {data1.orderId}"
        )

    async def test_concurrent_orders_all_accepted(self, api_client) -> None:
        """Multiple concurrent orders should all be processed without 5xx."""
        import asyncio

        payload = {
            "marketId": "BTC-PERP",
            "side": "buy",
            "type": "limit",
            "size": 0.01,
            "price": 50000.0,
        }

        tasks = [api_client.post("/orders", json=payload) for _ in range(5)]
        responses = await asyncio.gather(*tasks)

        for i, resp in enumerate(responses):
            assert resp.status_code < 500, (
                f"Concurrent order {i} returned {resp.status_code}"
            )

        success_count = sum(1 for r in responses if r.status_code == 200)
        assert success_count >= 1, "At least one concurrent order should succeed"

    async def test_concurrent_orders_unique_ids(self, api_client) -> None:
        """Concurrent orders should each receive a unique orderId."""
        import asyncio

        payload = {
            "marketId": "BTC-PERP",
            "side": "buy",
            "type": "limit",
            "size": 0.01,
            "price": 50000.0,
        }

        tasks = [api_client.post("/orders", json=payload) for _ in range(5)]
        responses = await asyncio.gather(*tasks)

        order_ids = []
        for resp in responses:
            if resp.status_code == 200:
                data = resp.json()
                order_ids.append(data.get("orderId"))

        unique_ids = set(order_ids)
        assert len(unique_ids) == len(order_ids), (
            f"Expected all unique orderIds, got {len(unique_ids)} unique "
            f"out of {len(order_ids)}: {order_ids}"
        )
