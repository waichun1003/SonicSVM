"""Tests for WebSocket connection lifecycle.

Validates initial connection handshake, hello message schema,
server time accuracy, and behavior with invalid/missing marketId.
Documents finding F-WS-001: invalid marketId is silently accepted.
"""

from __future__ import annotations

import time

import pytest
import websockets

import allure
from smfs_qa.schemas import WsHello
from smfs_qa.ws_client import WSTestClient
from smfs_qa.ws_routes import MarketFeedRoute

pytestmark = [pytest.mark.websocket]


@allure.feature("WebSocket Market Feed")
@allure.story("Connection Lifecycle")
class TestConnectionHandshake:
    """WebSocket connection and initial hello message tests."""

    async def test_connect_receives_hello(self, market_feed_route: MarketFeedRoute) -> None:
        """Connecting to /ws?marketId=BTC-PERP yields a hello message as the first message."""
        async with market_feed_route.client(timeout=10) as ws:
            msg = await ws.recv_json(timeout=10)
            assert msg["type"] == "hello", f"Expected hello, got type={msg.get('type')}"

    async def test_hello_schema_validates(self, market_feed_route: MarketFeedRoute) -> None:
        """hello message conforms to WsHello Pydantic model (type, serverTime, marketId)."""
        async with market_feed_route.client(timeout=10) as ws:
            msg = await ws.recv_json(timeout=10)
            parsed = WsHello.model_validate(msg)
            assert isinstance(parsed, WsHello)

    async def test_hello_market_id_matches_request(
        self, market_feed_route: MarketFeedRoute
    ) -> None:
        """hello.marketId matches the marketId query parameter (BTC-PERP)."""
        async with market_feed_route.client(timeout=10) as ws:
            msg = await ws.recv_json(timeout=10)
            parsed = WsHello.model_validate(msg)
            assert parsed.marketId == "BTC-PERP"

    async def test_hello_server_time_within_30s(self, market_feed_route: MarketFeedRoute) -> None:
        """hello.serverTime is within 30 seconds of local clock (milliseconds epoch)."""
        async with market_feed_route.client(timeout=10) as ws:
            msg = await ws.recv_json(timeout=10)
            parsed = WsHello.model_validate(msg)
            now_ms = time.time() * 1000
            drift = abs(now_ms - parsed.serverTime)
            assert drift < 30_000, f"Server time drift {drift:.0f}ms exceeds 30s threshold"

    async def test_hello_type_field_is_hello(self, market_feed_route: MarketFeedRoute) -> None:
        """hello message has type field set to exactly hello."""
        async with market_feed_route.client(timeout=10) as ws:
            msg = await ws.recv_json(timeout=10)
            assert msg["type"] == "hello"

    async def test_data_flows_after_hello(self, market_feed_route: MarketFeedRoute) -> None:
        """After hello, subsequent messages arrive (book_delta or trade)."""
        async with market_feed_route.client(timeout=10) as ws:
            hello = await ws.recv_json(timeout=10)
            assert hello["type"] == "hello"
            msg = await ws.recv_json(timeout=10)
            assert msg["type"] in ("book_delta", "trade"), (
                f"Expected data message after hello, got {msg.get('type')}"
            )


@allure.feature("WebSocket Market Feed")
@allure.story("Connection Lifecycle")
class TestConnectionEdgeCases:
    """Edge case tests for WebSocket connection parameters."""

    @pytest.mark.xfail(
        reason="F-WS-001: Invalid marketId silently accepted -- server returns hello "
        "with the invalid marketId and streams BTC-PERP data instead of rejecting",
        strict=True,
    )
    @pytest.mark.finding
    async def test_invalid_market_id_rejected(self, ws_base_url: str) -> None:
        """Connecting with an invalid marketId should be rejected or return an error.

        The server should either close the connection, refuse the upgrade,
        or send an error message for non-existent markets.
        """
        route = MarketFeedRoute(ws_base_url, market_id="INVALID-NONEXISTENT")
        async with route.client(timeout=10) as ws:
            msg = await ws.recv_json(timeout=10)
            # Correct behavior: the message should indicate an error
            assert msg.get("type") == "error" or msg.get("error"), (
                f"Expected error for invalid marketId, got hello with "
                f"marketId={msg.get('marketId')}"
            )

    async def test_no_market_id_defaults_to_btc_perp(self, ws_base_url: str) -> None:
        """Connecting without marketId query parameter defaults to BTC-PERP."""
        client = WSTestClient(f"{ws_base_url}/ws", timeout=10)
        async with client as ws:
            msg = await ws.recv_json(timeout=10)
            parsed = WsHello.model_validate(msg)
            assert parsed.marketId == "BTC-PERP"

    async def test_empty_market_id_handled(self, ws_base_url: str) -> None:
        """Connecting with empty marketId parameter does not crash the server.

        Acceptable outcomes: server sends a hello (defaulting to a market),
        sends an error message, or rejects the WebSocket upgrade.
        """
        client = WSTestClient(f"{ws_base_url}/ws?marketId=", timeout=10)
        try:
            async with client as ws:
                msg = await ws.recv_json(timeout=10)
                assert "type" in msg, "Expected a typed message response"
                assert msg["type"] in ("hello", "error"), (
                    f"Expected hello or error for empty marketId, got type={msg['type']}"
                )
        except (
            websockets.exceptions.InvalidStatusCode,
            websockets.exceptions.InvalidHandshake,
            ConnectionRefusedError,
            TimeoutError,
        ):
            pass  # WebSocket upgrade rejection is acceptable
