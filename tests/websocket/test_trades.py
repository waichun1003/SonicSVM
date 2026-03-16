"""Tests for WebSocket trade messages.

Validates trade message schema, side field values, tradeId format,
and documents floating-point price artifacts in trades (F-WS-003).
"""

from __future__ import annotations

import pytest

import allure
from smfs_qa.schemas import WsTrade
from smfs_qa.validators import has_float_artifact
from smfs_qa.ws_routes import MarketFeedRoute

pytestmark = [pytest.mark.websocket]


@allure.feature("WebSocket Market Feed")
@allure.story("Trade Messages")
class TestTradeSchema:
    """trade message structure and schema tests."""

    async def test_trade_schema_validates(self, market_feed_route: MarketFeedRoute) -> None:
        """trade messages conform to WsTrade Pydantic model."""
        async with market_feed_route.client(timeout=20) as ws:
            await ws.recv_json(timeout=10)  # hello
            msg = await ws.drain_until("trade", timeout=15)
            parsed = WsTrade.model_validate(msg)
            assert isinstance(parsed, WsTrade)
            assert parsed.type == "trade"

    async def test_trade_has_required_fields(self, market_feed_route: MarketFeedRoute) -> None:
        """trade messages contain tradeId, ts, price, size, and side fields."""
        async with market_feed_route.client(timeout=20) as ws:
            await ws.recv_json(timeout=10)  # hello
            msg = await ws.drain_until("trade", timeout=15)
            parsed = WsTrade.model_validate(msg)
            assert parsed.tradeId, "tradeId must be non-empty"
            assert isinstance(parsed.ts, (int, float)), "ts must be numeric"
            assert isinstance(parsed.price, (int, float)), "price must be numeric"
            assert isinstance(parsed.size, (int, float)), "size must be numeric"
            assert parsed.side in ("buy", "sell"), f"side must be buy or sell, got {parsed.side}"

    async def test_trade_side_is_buy_or_sell(self, market_feed_route: MarketFeedRoute) -> None:
        """All trade.side values are either buy or sell across multiple samples.

        Collects multiple trades and verifies side field is always valid.
        """
        async with market_feed_route.client(timeout=30) as ws:
            await ws.recv_json(timeout=10)  # hello
            messages = await ws.collect_messages(count=50, timeout=20)
            trades = [m for m in messages if m.get("type") == "trade"]
            assert len(trades) >= 2, f"Expected at least 2 trades, got {len(trades)}"

            for trade in trades:
                parsed = WsTrade.model_validate(trade)
                assert parsed.side in ("buy", "sell"), (
                    f"Invalid side '{parsed.side}' in trade {parsed.tradeId}"
                )

    async def test_trade_ids_are_unique(self, market_feed_route: MarketFeedRoute) -> None:
        """tradeId values are unique across a sample of trade messages."""
        async with market_feed_route.client(timeout=30) as ws:
            await ws.recv_json(timeout=10)  # hello
            messages = await ws.collect_messages(count=50, timeout=20)
            trades = [m for m in messages if m.get("type") == "trade"]
            assert len(trades) >= 2, f"Expected at least 2 trades, got {len(trades)}"

            trade_ids = [t["tradeId"] for t in trades]
            assert len(trade_ids) == len(set(trade_ids)), (
                "Duplicate tradeIds found: "
                f"{[tid for tid in trade_ids if trade_ids.count(tid) > 1]}"
            )

    async def test_trade_size_is_positive(self, market_feed_route: MarketFeedRoute) -> None:
        """All trade.size values are positive across a sample of trade messages."""
        async with market_feed_route.client(timeout=30) as ws:
            await ws.recv_json(timeout=10)  # hello
            messages = await ws.collect_messages(count=50, timeout=20)
            trades = [m for m in messages if m.get("type") == "trade"]
            assert len(trades) >= 1, "No trades received"

            for trade in trades:
                parsed = WsTrade.model_validate(trade)
                assert parsed.size > 0, (
                    f"Trade {parsed.tradeId} has non-positive size {parsed.size}"
                )

    @pytest.mark.xfail(
        reason="F-WS-003: Floating-point price artifacts in trade messages -- "
        "prices like 65921.90000000001 instead of clean decimals",
        strict=True,
    )
    @pytest.mark.finding
    async def test_trade_prices_clean_decimals(self, market_feed_route: MarketFeedRoute) -> None:
        """All trade prices should be clean decimal values without IEEE 754 artifacts.

        Checks that trade prices do not exhibit floating-point representation
        artifacts (e.g., 65921.90000000001 instead of 65921.9).
        Uses a large sample (100+ messages) to reliably detect intermittent artifacts.
        """
        async with market_feed_route.client(timeout=30) as ws:
            await ws.recv_json(timeout=10)  # hello
            messages = await ws.collect_messages(count=100, timeout=20)
            trades = [m for m in messages if m.get("type") == "trade"]
            if len(trades) == 0:
                pytest.skip("No trades received -- market may be inactive")

            artifacts = []
            for trade in trades:
                parsed = WsTrade.model_validate(trade)
                if has_float_artifact(parsed.price):
                    artifacts.append(parsed.price)

            assert len(artifacts) == 0, (
                f"Found {len(artifacts)} trade prices with floating-point artifacts "
                f"in {len(trades)} trades: {artifacts[:5]}"
            )
