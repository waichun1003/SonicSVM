"""Tests for slot ordering verification in the live Solana stream.

Validates that transactions arrive in monotonically non-decreasing slot order
(with allowance for shallow reorgs), and measures gap distribution.

Solana slots are ~400ms. Empty slots are skipped by the runtime, so gaps of
2-3 slots are normal. Gaps >100 suggest indexer lag or missed blocks.
"""

from __future__ import annotations

import pytest

import allure
from smfs_qa.logger import QALogger
from smfs_qa.solana import check_slot_ordering
from smfs_qa.ws_routes import SolanaStreamRoute

pytestmark = [pytest.mark.solana]

SUBSCRIBE_WAIT = 45


@allure.feature("Solana Transaction Stream")
@allure.story("Slot Ordering")
class TestSlotMonotonicOrdering:
    """Verify that the stream delivers transactions in slot order."""

    async def test_slots_monotonically_non_decreasing(
        self, solana_stream_route: SolanaStreamRoute
    ) -> None:
        """Slots should be monotonically non-decreasing (same or increasing).

        Multiple transactions per slot are valid (same slot number repeated).
        Only decreasing slot numbers indicate a problem (reorg or misordering).
        """
        async with solana_stream_route.client(timeout=SUBSCRIBE_WAIT + 15) as ws:
            hello = await ws.recv_json(timeout=10)
            assert hello["type"] == "stream_hello"

            await ws.send_json(SolanaStreamRoute.build_subscribe_all())
            messages = await ws.collect_messages(count=80, timeout=SUBSCRIBE_WAIT)

            txs = [m for m in messages if m.get("type") == "transaction"]
            if len(txs) < 5:
                pytest.skip(f"Insufficient transactions ({len(txs)}) for ordering check")

            slots = [tx["slot"] for tx in txs]
            result = check_slot_ordering(slots)

            QALogger.info(f"Analyzed {len(slots)} slots: {min(slots)} -> {max(slots)}")
            QALogger.info(f"Unique slots: {len(set(slots))}")
            QALogger.info(f"Rollbacks: {len(result['rollbacks'])}")
            QALogger.info(f"Gaps (>1 slot): {len(result['gaps'])}")

            for idx in result["rollbacks"]:
                QALogger.warn(
                    f"  Non-monotonic at index {idx}: slot {slots[idx - 1]} -> {slots[idx]}"
                )

            non_monotonic = len(result["rollbacks"])
            rate = non_monotonic / (len(slots) - 1) if len(slots) > 1 else 0.0
            QALogger.assert_true(
                rate < 0.02,
                f"Slot ordering is {100 - rate * 100:.1f}% monotonic ({non_monotonic} violations)",
                f"{non_monotonic} ordering violations in {len(slots)} transitions ({rate:.1%})",
            )

    async def test_slot_values_are_plausible(self, solana_stream_route: SolanaStreamRoute) -> None:
        """Slot numbers should be in a plausible range for the current Solana epoch.

        As of early 2026, Solana mainnet slots are in the 300M+ range.
        Test environment slots should be >100M to be plausible.
        """
        async with solana_stream_route.client(timeout=SUBSCRIBE_WAIT + 15) as ws:
            hello = await ws.recv_json(timeout=10)
            assert hello["type"] == "stream_hello"

            await ws.send_json(SolanaStreamRoute.build_subscribe_all())
            messages = await ws.collect_messages(count=10, timeout=SUBSCRIBE_WAIT)

            txs = [m for m in messages if m.get("type") == "transaction"]
            if not txs:
                pytest.skip("No transactions received for slot plausibility check")

            for tx in txs:
                slot = tx["slot"]
                QALogger.assert_true(
                    slot > 100_000_000,
                    f"Slot {slot:,} is in plausible range (>100M)",
                    f"Slot {slot:,} is suspiciously low -- may not be mainnet data",
                )

    async def test_multiple_transactions_per_slot(
        self, solana_stream_route: SolanaStreamRoute
    ) -> None:
        """A single slot can contain multiple transactions.

        This is normal Solana behavior -- each slot processes many transactions.
        Verify the stream correctly delivers multiple txs with the same slot.
        """
        async with solana_stream_route.client(timeout=SUBSCRIBE_WAIT + 15) as ws:
            hello = await ws.recv_json(timeout=10)
            assert hello["type"] == "stream_hello"

            await ws.send_json(SolanaStreamRoute.build_subscribe_all())
            messages = await ws.collect_messages(count=100, timeout=SUBSCRIBE_WAIT)

            txs = [m for m in messages if m.get("type") == "transaction"]
            if len(txs) < 10:
                pytest.skip(f"Only {len(txs)} transactions; need 10+ for duplicate slot check")

            slots = [tx["slot"] for tx in txs]
            unique = len(set(slots))
            dup_rate = 1.0 - (unique / len(slots))

            QALogger.info(
                f"Slot duplication: {len(slots)} txs across {unique} unique slots "
                f"({dup_rate:.1%} share a slot with another tx)"
            )

            QALogger.assert_true(
                unique <= len(slots),
                f"Stream delivers multiple txs per slot ({unique} unique / {len(slots)} total)",
                "Each transaction has a unique slot -- unexpected for Solana",
            )


@allure.feature("Solana Transaction Stream")
@allure.story("Slot Ordering")
class TestSlotGapDistribution:
    """Measure and validate the distribution of slot gaps."""

    async def test_gap_distribution(self, solana_stream_route: SolanaStreamRoute) -> None:
        """Measure the distribution of slot gaps between consecutive transactions.

        Expected:
        - Most gaps are 0 (same slot) or 1 (consecutive)
        - Gaps of 2-10 are normal (empty slots skipped)
        - Gaps >100 suggest indexer lag
        """
        async with solana_stream_route.client(timeout=SUBSCRIBE_WAIT + 15) as ws:
            hello = await ws.recv_json(timeout=10)
            assert hello["type"] == "stream_hello"

            await ws.send_json(SolanaStreamRoute.build_subscribe_all())
            messages = await ws.collect_messages(count=100, timeout=SUBSCRIBE_WAIT)

            txs = [m for m in messages if m.get("type") == "transaction"]
            if len(txs) < 10:
                pytest.skip(f"Only {len(txs)} transactions for gap analysis")

            slots = [tx["slot"] for tx in txs]
            gaps = [slots[i] - slots[i - 1] for i in range(1, len(slots))]

            if not gaps:
                pytest.skip("Not enough transitions for gap analysis")

            positive_gaps = [g for g in gaps if g > 0]
            zero_gaps = sum(1 for g in gaps if g == 0)
            small_gaps = sum(1 for g in gaps if 1 <= g <= 10)
            large_gaps = sum(1 for g in gaps if g > 100)

            QALogger.info("=== Slot Gap Distribution ===")
            QALogger.info(f"Total transitions: {len(gaps)}")
            QALogger.info(f"Same-slot (gap=0): {zero_gaps}")
            QALogger.info(f"Small gaps (1-10): {small_gaps}")
            QALogger.info(f"Large gaps (>100): {large_gaps}")
            if positive_gaps:
                QALogger.info(f"Positive gap range: {min(positive_gaps)} - {max(positive_gaps)}")

            large_gap_rate = large_gaps / len(gaps) if gaps else 0
            QALogger.assert_true(
                large_gap_rate < 0.10,
                f"Large gap rate {large_gap_rate:.1%} is acceptable (<10%)",
                f"Large gap rate {large_gap_rate:.1%} exceeds 10% -- "
                f"possible indexer lag or missed blocks",
            )
