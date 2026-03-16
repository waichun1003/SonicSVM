"""Tests for GET /markets/{marketId}/snapshot endpoint.

Validates order book snapshot structure, schema compliance,
and documents known findings: floating-point price artifacts (F-REST-001)
and crossed order book (F-REST-002).
"""

from __future__ import annotations

import pytest

import allure
from smfs_qa.schemas import SnapshotResponse

pytestmark = [pytest.mark.rest]


@allure.feature("REST API")
@allure.story("Order Book Snapshot")
class TestSnapshot:
    """GET /markets/BTC-PERP/snapshot endpoint tests."""

    async def test_snapshot_returns_200(self, api_client) -> None:
        """Snapshot endpoint returns HTTP 200 OK for BTC-PERP."""
        resp = await api_client.get("/markets/BTC-PERP/snapshot")
        assert resp.status_code == 200

    async def test_snapshot_schema_validates(self, api_client) -> None:
        """Response body conforms to SnapshotResponse Pydantic model."""
        resp = await api_client.get("/markets/BTC-PERP/snapshot")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
        data = SnapshotResponse.model_validate(resp.json())
        assert isinstance(data, SnapshotResponse)

    async def test_snapshot_has_bids_and_asks(self, snapshot_route) -> None:
        """Snapshot contains non-empty bids and asks arrays."""
        data = await snapshot_route.get_snapshot_parsed()
        assert len(data.bids) > 0, "Expected non-empty bids array"
        assert len(data.asks) > 0, "Expected non-empty asks array"

    @pytest.mark.xfail(
        reason="F-REST-001: Floating-point price artifacts — prices like 66013.90000000001 "
        "instead of clean decimals (~70% reproduction rate)",
        strict=False,
    )
    @pytest.mark.finding
    async def test_snapshot_prices_clean_decimals(self, snapshot_route) -> None:
        """Across 3 snapshots, all bid/ask prices should be clean decimals.

        Samples multiple snapshots to account for non-deterministic price data.
        Uses shared has_float_artifact validator.
        """
        from smfs_qa.validators import has_float_artifact

        artifacts = []
        for _ in range(3):
            data = await snapshot_route.get_snapshot_parsed()
            for level in data.bids + data.asks:
                if has_float_artifact(level.price):
                    artifacts.append(level.price)
        assert len(artifacts) == 0, (
            f"Found {len(artifacts)} prices with floating-point artifacts "
            f"across 3 snapshots: {artifacts[:5]}"
        )

    @pytest.mark.xfail(
        reason="F-REST-002: Crossed order book — best bid sometimes exceeds best ask (~30-50%)",
        strict=False,
    )
    @pytest.mark.finding
    async def test_snapshot_book_not_crossed(self, snapshot_route) -> None:
        """Best bid price must be strictly less than best ask price.

        A crossed book (bid >= ask) indicates a data integrity issue in the
        order book aggregation.
        """
        data = await snapshot_route.get_snapshot_parsed()
        if not data.bids or not data.asks:
            pytest.skip("Empty bids or asks — cannot check for crossed book")
        best_bid = max(level.price for level in data.bids)
        best_ask = min(level.price for level in data.asks)
        assert best_bid < best_ask, f"Crossed book: best bid {best_bid} >= best ask {best_ask}"

    async def test_snapshot_invalid_market_returns_4xx(self, api_client) -> None:
        """Snapshot with non-existent marketId returns a 4xx client error."""
        resp = await api_client.get("/markets/NONEXISTENT-MARKET/snapshot")
        assert 400 <= resp.status_code < 500, (
            f"Expected 4xx for invalid marketId, got {resp.status_code}"
        )

    async def test_snapshot_has_timestamp(self, snapshot_route) -> None:
        """Snapshot response includes a timestamp field."""
        data = await snapshot_route.get_snapshot_parsed()
        assert data.ts > 0, "Snapshot timestamp should be positive"

    async def test_snapshot_content_type_json(self, api_client) -> None:
        """Response Content-Type header is application/json."""
        resp = await api_client.get("/markets/BTC-PERP/snapshot")
        content_type = resp.headers.get("content-type", "")
        assert "application/json" in content_type, (
            f"Expected application/json, got '{content_type}'"
        )

    async def test_snapshot_bid_ask_prices_positive(self, snapshot_route) -> None:
        """All bid and ask prices are positive values."""
        data = await snapshot_route.get_snapshot_parsed()
        for level in data.bids:
            assert level.price > 0, f"Bid price must be positive, got {level.price}"
        for level in data.asks:
            assert level.price > 0, f"Ask price must be positive, got {level.price}"
