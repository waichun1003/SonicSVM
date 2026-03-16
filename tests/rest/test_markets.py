"""Tests for GET /markets endpoint.

Validates market listing response structure, schema compliance,
non-empty results, and BTC-PERP market attributes.
"""

from __future__ import annotations

import pytest

import allure
from smfs_qa.schemas import MarketsResponse

pytestmark = [pytest.mark.rest]


@allure.feature("REST API")
@allure.story("Markets Listing")
class TestMarkets:
    """GET /markets endpoint tests."""

    async def test_markets_returns_200(self, api_client) -> None:
        """Markets endpoint returns HTTP 200 OK."""
        resp = await api_client.get("/markets")
        assert resp.status_code == 200

    async def test_markets_schema_validates(self, api_client) -> None:
        """Response body conforms to MarketsResponse Pydantic model."""
        resp = await api_client.get("/markets")
        data = MarketsResponse.model_validate(resp.json())
        assert isinstance(data, MarketsResponse)

    async def test_markets_array_non_empty(self, markets_route) -> None:
        """markets array contains at least one market."""
        data = await markets_route.get_markets()
        assert len(data.markets) > 0, "Expected at least one market"

    async def test_btc_perp_base_quote(self, markets_route) -> None:
        """BTC-PERP market has base=BTC and quote=USDT."""
        data = await markets_route.get_markets()
        btc_perp = next((m for m in data.markets if m.marketId == "BTC-PERP"), None)
        assert btc_perp is not None, "BTC-PERP not found in markets list"
        assert btc_perp.base == "BTC", f"Expected base='BTC', got '{btc_perp.base}'"
        assert btc_perp.quote == "USDT", f"Expected quote='USDT', got '{btc_perp.quote}'"

    async def test_markets_content_type_json(self, api_client) -> None:
        """Response Content-Type header is application/json."""
        resp = await api_client.get("/markets")
        content_type = resp.headers.get("content-type", "")
        assert "application/json" in content_type, (
            f"Expected application/json, got '{content_type}'"
        )
