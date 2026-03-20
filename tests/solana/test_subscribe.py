"""Tests for Solana stream subscribe behavior.

Validates that subscribing to the Solana transaction stream delivers
transaction data for various filter configurations, and that the server
provides appropriate acknowledgments.
"""

from __future__ import annotations

import pytest

import allure
from smfs_qa.ws_routes import SolanaStreamRoute

pytestmark = [pytest.mark.solana]

SUBSCRIBE_WAIT_SECONDS = 10


@allure.feature("Solana Transaction Stream")
@allure.story("Subscribe Data Delivery")
class TestSubscribe:
    """Subscribe data delivery tests."""

    @pytest.mark.xfail(
        reason="F-SOL-001: Solana stream subscribe does not deliver data",
        strict=False,
    )
    @pytest.mark.finding
    async def test_subscribe_bare_receives_data(
        self, solana_stream_route: SolanaStreamRoute
    ) -> None:
        """Bare subscribe (no filters) receives transaction data."""
        async with solana_stream_route.client(timeout=SUBSCRIBE_WAIT_SECONDS + 10) as ws:
            hello = await ws.recv_json(timeout=10)
            assert hello["type"] == "stream_hello"
            await ws.send_json(SolanaStreamRoute.build_subscribe_all())
            messages = await ws.collect_messages(count=1, timeout=SUBSCRIBE_WAIT_SECONDS)
            non_hello = [m for m in messages if m.get("type") != "stream_hello"]
            assert len(non_hello) > 0, (
                f"No transaction data received after {SUBSCRIBE_WAIT_SECONDS}s wait"
            )

    @pytest.mark.xfail(
        reason="F-SOL-001: Solana stream subscribe does not deliver data",
        strict=False,
    )
    @pytest.mark.finding
    async def test_subscribe_system_program_receives_data(
        self, solana_stream_route: SolanaStreamRoute
    ) -> None:
        """Subscribe with System Program filter receives transactions."""
        async with solana_stream_route.client(timeout=SUBSCRIBE_WAIT_SECONDS + 10) as ws:
            hello = await ws.recv_json(timeout=10)
            assert hello["type"] == "stream_hello"
            await ws.send_json(SolanaStreamRoute.build_subscribe_system_program())
            messages = await ws.collect_messages(count=1, timeout=SUBSCRIBE_WAIT_SECONDS)
            non_hello = [m for m in messages if m.get("type") != "stream_hello"]
            assert len(non_hello) > 0, "No System Program transactions after subscribe"

    @pytest.mark.xfail(
        reason="F-SOL-001: Solana stream subscribe does not deliver data",
        strict=False,
    )
    @pytest.mark.finding
    async def test_subscribe_spl_token_receives_data(
        self, solana_stream_route: SolanaStreamRoute
    ) -> None:
        """Subscribe with SPL Token filter receives transactions."""
        async with solana_stream_route.client(timeout=SUBSCRIBE_WAIT_SECONDS + 10) as ws:
            hello = await ws.recv_json(timeout=10)
            assert hello["type"] == "stream_hello"
            await ws.send_json(SolanaStreamRoute.build_subscribe_spl_token())
            messages = await ws.collect_messages(count=1, timeout=SUBSCRIBE_WAIT_SECONDS)
            non_hello = [m for m in messages if m.get("type") != "stream_hello"]
            assert len(non_hello) > 0, "No SPL Token transactions after subscribe"

    @pytest.mark.xfail(
        reason="Server does not echo a subscribe acknowledgment message",
        strict=True,
    )
    @pytest.mark.finding
    async def test_subscribe_receives_acknowledgment(
        self, solana_stream_route: SolanaStreamRoute
    ) -> None:
        """Server should echo a subscribe_ack or similar confirmation."""
        async with solana_stream_route.client(timeout=20) as ws:
            hello = await ws.recv_json(timeout=10)
            assert hello["type"] == "stream_hello"
            await ws.send_json(SolanaStreamRoute.build_subscribe_all())
            messages = await ws.collect_messages(count=5, timeout=10)
            ack_types = {"subscribe_ack", "subscribed", "subscribe"}
            has_ack = any(m.get("type") in ack_types for m in messages)
            assert has_ack, (
                f"No subscribe acknowledgment. Got types: {[m.get('type') for m in messages]}"
            )

    @pytest.mark.xfail(
        reason="F-SOL-001: Solana stream subscribe does not deliver data",
        strict=False,
    )
    @pytest.mark.finding
    async def test_subscribe_reproduction_rate(
        self, solana_stream_route: SolanaStreamRoute
    ) -> None:
        """Data delivery should be reliable across multiple attempts."""
        successes = 0
        attempts = 5
        for _ in range(attempts):
            async with solana_stream_route.client(timeout=20) as ws:
                hello = await ws.recv_json(timeout=10)
                assert hello["type"] == "stream_hello"
                await ws.send_json(SolanaStreamRoute.build_subscribe_all())
                messages = await ws.collect_messages(count=1, timeout=10)
                non_hello = [m for m in messages if m.get("type") != "stream_hello"]
                if len(non_hello) > 0:
                    successes += 1
        assert successes > 0, (
            f"Data delivery rate: {successes}/{attempts} (0%). "
            f"Stream subscribe appears non-functional."
        )
