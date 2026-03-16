"""Tests for GET /health endpoint.

Validates health check response structure, schema compliance,
server time accuracy, market listing, and WebSocket URL format.
"""

from __future__ import annotations

import time

import pytest

import allure
from smfs_qa.schemas import HealthResponse

pytestmark = [pytest.mark.rest]


@allure.feature("REST API")
@allure.story("Health Check")
class TestHealth:
    """GET /health endpoint tests."""

    async def test_health_returns_200(self, api_client) -> None:
        """Health endpoint returns HTTP 200 OK."""
        resp = await api_client.get("/health")
        assert resp.status_code == 200

    async def test_health_schema_validates(self, api_client) -> None:
        """Response body conforms to HealthResponse Pydantic model."""
        resp = await api_client.get("/health")
        data = HealthResponse.model_validate(resp.json())
        assert isinstance(data, HealthResponse)

    async def test_health_ok_is_true(self, health_route) -> None:
        """Health check reports ok=true when service is operational."""
        data = await health_route.get_health()
        assert data.ok is True

    async def test_health_server_time_within_30s(self, health_route) -> None:
        """serverTime is within 30 seconds of local clock (milliseconds epoch)."""
        data = await health_route.get_health()
        now_ms = time.time() * 1000
        drift = abs(now_ms - data.serverTime)
        assert drift < 30_000, f"Server time drift {drift:.0f}ms exceeds 30s threshold"

    async def test_health_markets_contains_btc_perp(self, health_route) -> None:
        """markets array includes BTC-PERP."""
        data = await health_route.get_health()
        assert "BTC-PERP" in data.markets

    async def test_health_ws_url_starts_with_wss(self, health_route) -> None:
        """wsUrl uses secure WebSocket protocol (wss://)."""
        data = await health_route.get_health()
        assert data.wsUrl.startswith("wss://"), f"wsUrl '{data.wsUrl}' does not start with wss://"

    async def test_health_content_type_json(self, api_client) -> None:
        """Response Content-Type header is application/json."""
        resp = await api_client.get("/health")
        content_type = resp.headers.get("content-type", "")
        assert "application/json" in content_type, (
            f"Expected application/json, got '{content_type}'"
        )
