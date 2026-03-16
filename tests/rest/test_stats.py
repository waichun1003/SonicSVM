"""Tests for GET /stats endpoint.

Validates the statistics response structure, schema compliance,
per-market metrics, and that sequence numbers increment over time.
The response uses a nested format with per-market stats under a
'markets' dictionary.
"""

from __future__ import annotations

import asyncio

import pytest

import allure
from smfs_qa.schemas import StatsResponse

pytestmark = [pytest.mark.rest]

MARKET_ID = "BTC-PERP"


@allure.feature("REST API")
@allure.story("Server Statistics")
class TestStats:
    """GET /stats endpoint tests."""

    async def test_stats_returns_200(self, api_client) -> None:
        """Stats endpoint returns HTTP 200 OK."""
        resp = await api_client.get("/stats")
        assert resp.status_code == 200

    async def test_stats_schema_validates(self, api_client) -> None:
        """Response body conforms to StatsResponse Pydantic model."""
        resp = await api_client.get("/stats")
        data = StatsResponse.model_validate(resp.json())
        assert isinstance(data, StatsResponse)

    async def test_stats_contains_btc_perp_market(self, stats_route) -> None:
        """Stats response contains BTC-PERP market."""
        data = await stats_route.get_stats()
        assert MARKET_ID in data.markets, (
            f"Expected '{MARKET_ID}' in markets, got {list(data.markets.keys())}"
        )

    async def test_stats_book_updates_positive(self, stats_route) -> None:
        """bookUpdatesPerSecond is greater than zero on an active market."""
        data = await stats_route.get_stats()
        market = data.markets[MARKET_ID]
        assert market.bookUpdatesPerSecond > 0, (
            f"Expected bookUpdatesPerSecond > 0, got {market.bookUpdatesPerSecond}"
        )

    async def test_stats_connected_clients_non_negative(self, stats_route) -> None:
        """connectedClients is zero or positive."""
        data = await stats_route.get_stats()
        assert data.connectedClients >= 0, (
            f"Expected connectedClients >= 0, got {data.connectedClients}"
        )

    async def test_stats_current_seq_increases(self, stats_route) -> None:
        """currentSeq increases between two calls separated by a short delay."""
        first = await stats_route.get_stats()
        await asyncio.sleep(2)
        second = await stats_route.get_stats()
        seq1 = first.markets[MARKET_ID].currentSeq
        seq2 = second.markets[MARKET_ID].currentSeq
        assert seq2 > seq1, f"Expected currentSeq to increase: {seq1} -> {seq2}"

    async def test_stats_trades_per_second_non_negative(self, stats_route) -> None:
        """tradesPerSecond is zero or positive."""
        data = await stats_route.get_stats()
        market = data.markets[MARKET_ID]
        assert market.tradesPerSecond >= 0, (
            f"Expected tradesPerSecond >= 0, got {market.tradesPerSecond}"
        )

    async def test_stats_current_seq_positive(self, stats_route) -> None:
        """currentSeq is a positive integer on an active market."""
        data = await stats_route.get_stats()
        market = data.markets[MARKET_ID]
        assert market.currentSeq > 0, (
            f"Expected currentSeq > 0, got {market.currentSeq}"
        )

    async def test_stats_content_type_json(self, api_client) -> None:
        """Response Content-Type header is application/json."""
        resp = await api_client.get("/stats")
        content_type = resp.headers.get("content-type", "")
        assert "application/json" in content_type, (
            f"Expected application/json, got '{content_type}'"
        )

    async def test_stats_multiple_markets_present(self, stats_route) -> None:
        """Stats response contains at least one market (BTC-PERP, SOL-PERP)."""
        data = await stats_route.get_stats()
        assert len(data.markets) >= 1, "Expected at least 1 market in stats"
