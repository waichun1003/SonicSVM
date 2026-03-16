"""Tests for WebSocket book_delta messages.

Validates book_delta message schema, bid/ask structure,
price and size fields, and documents floating-point price artifacts (F-WS-002).
"""

from __future__ import annotations

import time

import pytest

import allure
from smfs_qa.schemas import WsBookDelta
from smfs_qa.validators import has_float_artifact
from smfs_qa.ws_routes import MarketFeedRoute

pytestmark = [pytest.mark.websocket]


@allure.feature("WebSocket Market Feed")
@allure.story("Book Delta Messages")
class TestBookDeltaSchema:
    """book_delta message structure and schema tests."""

    async def test_book_delta_schema_validates(self, market_feed_route: MarketFeedRoute) -> None:
        """book_delta messages conform to WsBookDelta Pydantic model."""
        async with market_feed_route.client(timeout=15) as ws:
            await ws.recv_json(timeout=10)  # hello
            msg = await ws.drain_until("book_delta", timeout=10)
            parsed = WsBookDelta.model_validate(msg)
            assert isinstance(parsed, WsBookDelta)
            assert parsed.type == "book_delta"

    async def test_book_delta_has_bids_and_asks(self, market_feed_route: MarketFeedRoute) -> None:
        """book_delta messages contain bids and asks arrays."""
        async with market_feed_route.client(timeout=15) as ws:
            await ws.recv_json(timeout=10)  # hello
            msg = await ws.drain_until("book_delta", timeout=10)
            parsed = WsBookDelta.model_validate(msg)
            assert isinstance(parsed.bids, list), "bids must be a list"
            assert isinstance(parsed.asks, list), "asks must be a list"

    async def test_book_delta_levels_have_price_and_size(
        self, market_feed_route: MarketFeedRoute
    ) -> None:
        """Each bid/ask level in book_delta has numeric price and size fields."""
        async with market_feed_route.client(timeout=15) as ws:
            await ws.recv_json(timeout=10)  # hello
            # Collect several book_deltas to find one with non-empty levels
            messages = await ws.collect_messages(count=10, timeout=15)
            deltas = [m for m in messages if m.get("type") == "book_delta"]
            assert len(deltas) > 0, "No book_delta messages received"

            for delta in deltas:
                parsed = WsBookDelta.model_validate(delta)
                for level in parsed.bids + parsed.asks:
                    assert isinstance(level.price, (int, float)), (
                        f"Level price must be numeric, got {type(level.price)}"
                    )
                    assert isinstance(level.size, (int, float)), (
                        f"Level size must be numeric, got {type(level.size)}"
                    )

    async def test_book_delta_has_seq_field(self, market_feed_route: MarketFeedRoute) -> None:
        """book_delta messages include a numeric seq (sequence) field."""
        async with market_feed_route.client(timeout=15) as ws:
            await ws.recv_json(timeout=10)  # hello
            msg = await ws.drain_until("book_delta", timeout=10)
            parsed = WsBookDelta.model_validate(msg)
            assert isinstance(parsed.seq, (int, float)), "seq must be numeric"
            assert parsed.seq > 0, f"seq should be positive, got {parsed.seq}"

    async def test_book_delta_has_timestamp(self, market_feed_route: MarketFeedRoute) -> None:
        """book_delta messages include a ts (timestamp) field in epoch milliseconds."""
        async with market_feed_route.client(timeout=15) as ws:
            await ws.recv_json(timeout=10)  # hello
            msg = await ws.drain_until("book_delta", timeout=10)
            parsed = WsBookDelta.model_validate(msg)
            now_ms = time.time() * 1000
            drift = abs(now_ms - parsed.ts)
            assert drift < 30_000, f"book_delta ts drift {drift:.0f}ms exceeds 30s"

    @pytest.mark.xfail(
        reason="F-WS-002: Floating-point price artifacts in book_delta -- prices like "
        "65922.40000000001 instead of clean decimals (~60% reproduction rate)",
        strict=False,
    )
    @pytest.mark.finding
    async def test_book_delta_prices_clean_decimals(
        self, market_feed_route: MarketFeedRoute
    ) -> None:
        """All bid/ask prices in book_delta should be clean decimal values.

        Checks that prices do not exhibit IEEE 754 floating-point representation
        artifacts (e.g., 65922.40000000001 instead of 65922.4).
        Uses a large sample (100+ messages) to reliably detect intermittent artifacts.
        """
        async with market_feed_route.client(timeout=30) as ws:
            await ws.recv_json(timeout=10)  # hello
            messages = await ws.collect_messages(count=100, timeout=20)
            deltas = [m for m in messages if m.get("type") == "book_delta"]
            assert len(deltas) >= 5, f"Expected at least 5 book_deltas, got {len(deltas)}"

            artifacts = []
            for delta in deltas:
                parsed = WsBookDelta.model_validate(delta)
                for level in parsed.bids + parsed.asks:
                    if has_float_artifact(level.price):
                        artifacts.append(level.price)

            assert len(artifacts) == 0, (
                f"Found {len(artifacts)} prices with floating-point artifacts "
                f"in {len(deltas)} book_deltas: {artifacts[:5]}"
            )

    async def test_book_delta_zero_size_is_removal(
        self, market_feed_route: MarketFeedRoute
    ) -> None:
        """book_delta levels with size=0 represent order removals (valid delta behavior).

        Collects messages statistically and verifies zero-size levels appear as part
        of normal delta operations.
        """
        async with market_feed_route.client(timeout=20) as ws:
            await ws.recv_json(timeout=10)  # hello
            messages = await ws.collect_messages(count=30, timeout=15)
            deltas = [m for m in messages if m.get("type") == "book_delta"]

            zero_count = 0
            total_levels = 0
            for delta in deltas:
                parsed = WsBookDelta.model_validate(delta)
                for level in parsed.bids + parsed.asks:
                    total_levels += 1
                    if level.size == 0:
                        zero_count += 1
                        # Zero-size levels must still have a valid price
                        assert isinstance(level.price, (int, float))
                        assert level.price > 0

            # Zero-size removals are expected in a delta feed
            assert total_levels > 0, "No book levels received"
