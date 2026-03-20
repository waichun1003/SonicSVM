"""Tests for Solana stream subscribe filter behavior.

Validates that different program filter combinations produce the expected
data delivery, including multi-program filters, empty arrays, and
extended observation windows.
"""

from __future__ import annotations

import pytest

import allure
from smfs_qa.solana import WELL_KNOWN_PROGRAMS
from smfs_qa.ws_routes import SolanaStreamRoute

pytestmark = [pytest.mark.solana]


@allure.feature("Solana Transaction Stream")
@allure.story("Subscribe Filters")
class TestSubscribeFilters:
    """Subscribe filter variant tests."""

    @pytest.mark.xfail(
        reason="F-SOL-002: Solana stream subscribe filters do not deliver data",
        strict=False,
    )
    @pytest.mark.finding
    async def test_subscribe_multiple_programs(
        self, solana_stream_route: SolanaStreamRoute
    ) -> None:
        """Subscribe with multiple program IDs receives data."""
        programs = [
            WELL_KNOWN_PROGRAMS["SYSTEM_PROGRAM"],
            WELL_KNOWN_PROGRAMS["SPL_TOKEN"],
        ]
        async with solana_stream_route.client(timeout=20) as ws:
            hello = await ws.recv_json(timeout=10)
            assert hello["type"] == "stream_hello"
            await ws.send_json(SolanaStreamRoute.build_subscribe(programs=programs))
            messages = await ws.collect_messages(count=1, timeout=10)
            non_hello = [m for m in messages if m.get("type") != "stream_hello"]
            assert len(non_hello) > 0, "No data with multiple program filters"

    @pytest.mark.xfail(
        reason="F-SOL-002: Solana stream subscribe does not deliver data",
        strict=False,
    )
    @pytest.mark.finding
    async def test_any_non_hello_message_within_60s(
        self, solana_stream_route: SolanaStreamRoute
    ) -> None:
        """After subscribing, non-hello messages should arrive within 15s."""
        async with solana_stream_route.client(timeout=25) as ws:
            hello = await ws.recv_json(timeout=10)
            assert hello["type"] == "stream_hello"
            await ws.send_json(SolanaStreamRoute.build_subscribe_all())
            messages = await ws.collect_messages(duration=15, timeout=20)
            non_hello = [m for m in messages if m.get("type") != "stream_hello"]
            assert len(non_hello) > 0, f"Zero non-hello messages in 15s. Got {len(messages)} total."

    @pytest.mark.xfail(
        reason="F-SOL-002: Solana stream subscribe filters do not deliver data",
        strict=False,
    )
    @pytest.mark.finding
    async def test_subscribe_empty_programs_array(
        self, solana_stream_route: SolanaStreamRoute
    ) -> None:
        """Subscribe with empty programs array receives data (matches all)."""
        async with solana_stream_route.client(timeout=20) as ws:
            hello = await ws.recv_json(timeout=10)
            assert hello["type"] == "stream_hello"
            await ws.send_json(SolanaStreamRoute.build_subscribe(programs=[]))
            messages = await ws.collect_messages(count=1, timeout=10)
            non_hello = [m for m in messages if m.get("type") != "stream_hello"]
            assert len(non_hello) > 0, "No data with empty programs filter"
