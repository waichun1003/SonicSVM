"""Tests for WebSocket sequence number ordering.

Validates that book_delta seq numbers are monotonically increasing
with no gaps, and that only book_delta messages carry seq numbers.
"""

from __future__ import annotations

import pytest

import allure
from smfs_qa.ws_routes import MarketFeedRoute

pytestmark = [pytest.mark.websocket]


@allure.feature("WebSocket Market Feed")
@allure.story("Sequence Integrity")
class TestSequenceOrdering:
    """Sequence number monotonicity and gap detection tests."""

    async def test_seq_monotonically_increasing(self, market_feed_route: MarketFeedRoute) -> None:
        """book_delta seq numbers are strictly monotonically increasing."""
        async with market_feed_route.client(timeout=20) as ws:
            await ws.recv_json(timeout=10)  # hello
            messages = await ws.collect_messages(count=30, timeout=15)
            deltas = [m for m in messages if m.get("type") == "book_delta"]
            assert len(deltas) >= 5, f"Expected at least 5 book_deltas, got {len(deltas)}"

            seqs = [d["seq"] for d in deltas]
            for i in range(len(seqs) - 1):
                assert seqs[i] < seqs[i + 1], (
                    f"Sequence not monotonically increasing at index {i}: "
                    f"{seqs[i]} >= {seqs[i + 1]}"
                )

    async def test_seq_no_gaps(self, market_feed_route: MarketFeedRoute) -> None:
        """book_delta seq numbers have no gaps (each increments by exactly 1)."""
        async with market_feed_route.client(timeout=20) as ws:
            await ws.recv_json(timeout=10)  # hello
            messages = await ws.collect_messages(count=30, timeout=15)
            deltas = [m for m in messages if m.get("type") == "book_delta"]
            assert len(deltas) >= 5, f"Expected at least 5 book_deltas, got {len(deltas)}"

            seqs = [d["seq"] for d in deltas]
            gaps = []
            for i in range(len(seqs) - 1):
                if seqs[i + 1] != seqs[i] + 1:
                    gaps.append((seqs[i], seqs[i + 1], seqs[i + 1] - seqs[i]))

            assert len(gaps) == 0, (
                f"Found {len(gaps)} sequence gaps: "
                f"{[(g[0], g[1], f'gap={g[2]}') for g in gaps[:5]]}"
            )

    async def test_seq_only_on_book_delta(self, market_feed_route: MarketFeedRoute) -> None:
        """Only book_delta messages carry the seq field; trade messages do not."""
        async with market_feed_route.client(timeout=20) as ws:
            await ws.recv_json(timeout=10)  # hello
            messages = await ws.collect_messages(count=30, timeout=15)

            for msg in messages:
                if msg.get("type") == "trade":
                    assert "seq" not in msg, f"Trade message should not have seq field: {msg}"
                elif msg.get("type") == "book_delta":
                    assert "seq" in msg, f"book_delta message missing seq field: {msg}"

    async def test_seq_are_positive_integers(self, market_feed_route: MarketFeedRoute) -> None:
        """All seq values are positive integers (not floats)."""
        async with market_feed_route.client(timeout=20) as ws:
            await ws.recv_json(timeout=10)  # hello
            messages = await ws.collect_messages(count=20, timeout=15)
            deltas = [m for m in messages if m.get("type") == "book_delta"]
            assert len(deltas) >= 3, f"Expected at least 3 book_deltas, got {len(deltas)}"

            for delta in deltas:
                seq = delta["seq"]
                assert isinstance(seq, int), (
                    f"seq must be int, got {type(seq).__name__} (value={seq})"
                )
                assert seq > 0, f"seq must be positive, got {seq}"

    async def test_timestamps_monotonically_non_decreasing(
        self, market_feed_route: MarketFeedRoute
    ) -> None:
        """Message timestamps (ts) are monotonically non-decreasing across all message types."""
        async with market_feed_route.client(timeout=20) as ws:
            await ws.recv_json(timeout=10)  # hello
            messages = await ws.collect_messages(count=30, timeout=15)
            ts_values = [m["ts"] for m in messages if "ts" in m]
            assert len(ts_values) >= 5, (
                f"Expected at least 5 timestamped messages, got {len(ts_values)}"
            )

            for i in range(len(ts_values) - 1):
                assert ts_values[i] <= ts_values[i + 1], (
                    f"Timestamps not monotonic at index {i}: {ts_values[i]} > {ts_values[i + 1]}"
                )
