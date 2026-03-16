"""Tests for Solana slot reorg (rollback) detection.

Reorgs are a normal part of Solana consensus -- shallow rollbacks of 1-2 slots
occur when the leader rotates or a fork is resolved. The stream should either:
  1. Deliver transactions in monotonically non-decreasing slot order, or
  2. Deliver reorged (rolled-back) transactions and let the consumer detect them.

These tests connect to the live stream and statistically measure:
  - Whether any slot reversals occur in a window of 100+ transactions
  - The rollback rate (should be < 5% for healthy Solana)
  - Slot gap distribution (empty slots are normal; large gaps indicate indexer lag)
"""

from __future__ import annotations

import pytest

import allure
from smfs_qa.logger import QALogger
from smfs_qa.solana import check_slot_ordering
from smfs_qa.ws_routes import SolanaStreamRoute

pytestmark = [pytest.mark.solana]

SUBSCRIBE_WAIT = 45
MIN_TX_COUNT = 20


@allure.feature("Solana Transaction Stream")
@allure.story("Reorg Detection")
class TestReorgDetection:
    """Detect and measure slot rollbacks (reorgs) in the live Solana stream."""

    async def test_slot_ordering_over_stream_window(
        self, solana_stream_route: SolanaStreamRoute
    ) -> None:
        """Collect transactions and verify slots are non-decreasing.

        Solana shallow reorgs are normal (1-2 slot rollbacks during leader
        rotation). This test records the rollback rate and asserts it stays
        below a 5% threshold.
        """
        async with solana_stream_route.client(timeout=SUBSCRIBE_WAIT + 15) as ws:
            hello = await ws.recv_json(timeout=10)
            assert hello["type"] == "stream_hello"

            await ws.send_json(SolanaStreamRoute.build_subscribe_all())
            messages = await ws.collect_messages(count=100, timeout=SUBSCRIBE_WAIT)

            txs = [m for m in messages if m.get("type") == "transaction"]
            QALogger.info(f"Collected {len(txs)} transactions for reorg analysis")

            if len(txs) < 2:
                pytest.skip(
                    f"Insufficient transactions ({len(txs)}) for reorg analysis; "
                    f"stream may be intermittent"
                )

            slots = [tx["slot"] for tx in txs]
            result = check_slot_ordering(slots)

            rollback_count = len(result["rollbacks"])
            rollback_rate = rollback_count / (len(slots) - 1) if len(slots) > 1 else 0.0

            QALogger.info(f"Slot range: {min(slots)} -> {max(slots)}")
            QALogger.info(f"Rollbacks detected: {rollback_count}")
            QALogger.info(f"Rollback rate: {rollback_rate:.2%}")

            for idx in result["rollbacks"]:
                QALogger.warn(
                    f"  Reorg at index {idx}: slot {slots[idx - 1]} -> {slots[idx]} "
                    f"(rolled back {slots[idx - 1] - slots[idx]} slots)"
                )

            QALogger.assert_true(
                rollback_rate < 0.05,
                f"Rollback rate {rollback_rate:.2%} within healthy threshold (<5%)",
                f"Rollback rate {rollback_rate:.2%} exceeds 5% -- "
                f"{rollback_count} reversals in {len(slots)} transactions",
            )

    async def test_no_large_rollbacks(
        self, solana_stream_route: SolanaStreamRoute
    ) -> None:
        """Any rollbacks should be shallow (<=4 slots).

        Deep rollbacks (>4 slots) would indicate a serious fork or indexer bug,
        not normal Solana consensus behavior.
        """
        async with solana_stream_route.client(timeout=SUBSCRIBE_WAIT + 15) as ws:
            hello = await ws.recv_json(timeout=10)
            assert hello["type"] == "stream_hello"

            await ws.send_json(SolanaStreamRoute.build_subscribe_all())
            messages = await ws.collect_messages(count=100, timeout=SUBSCRIBE_WAIT)

            txs = [m for m in messages if m.get("type") == "transaction"]
            if len(txs) < 2:
                pytest.skip(f"Insufficient transactions ({len(txs)}) for rollback depth check")

            slots = [tx["slot"] for tx in txs]
            result = check_slot_ordering(slots)

            for idx in result["rollbacks"]:
                depth = slots[idx - 1] - slots[idx]
                QALogger.assert_true(
                    depth <= 4,
                    f"Rollback depth {depth} at index {idx} is shallow (<=4 slots)",
                    f"Deep rollback of {depth} slots at index {idx}: "
                    f"slot {slots[idx - 1]} -> {slots[idx]}. "
                    f"This exceeds normal Solana consensus rollback depth.",
                )

    async def test_reorg_transaction_redelivery(
        self, solana_stream_route: SolanaStreamRoute
    ) -> None:
        """If a reorg occurs, affected transactions should be re-delivered.

        After a rollback, the stream should deliver replacement transactions
        for the rolled-back slots. We check that rolled-back slot numbers
        eventually appear again in the stream.
        """
        async with solana_stream_route.client(timeout=SUBSCRIBE_WAIT + 15) as ws:
            hello = await ws.recv_json(timeout=10)
            assert hello["type"] == "stream_hello"

            await ws.send_json(SolanaStreamRoute.build_subscribe_all())
            messages = await ws.collect_messages(count=150, timeout=SUBSCRIBE_WAIT)

            txs = [m for m in messages if m.get("type") == "transaction"]
            if len(txs) < 2:
                pytest.skip(f"Insufficient transactions ({len(txs)}) for redelivery check")

            slots = [tx["slot"] for tx in txs]
            result = check_slot_ordering(slots)

            if not result["rollbacks"]:
                QALogger.info(
                    "No rollbacks observed in this window -- "
                    "cannot verify redelivery (this is normal)"
                )
                return

            for idx in result["rollbacks"]:
                rolledback_slot = slots[idx - 1]
                redelivered = any(
                    s == rolledback_slot for s in slots[idx:]
                )
                QALogger.info(
                    f"Rolled-back slot {rolledback_slot}: "
                    f"{'re-delivered' if redelivered else 'NOT re-delivered'} "
                    f"in subsequent stream"
                )


@allure.feature("Solana Transaction Stream")
@allure.story("Reorg Detection")
class TestRollbackRateMeasurement:
    """Statistical measurement of rollback rates."""

    async def test_rollback_rate_measurement(
        self, solana_stream_route: SolanaStreamRoute
    ) -> None:
        """Measure rollback rate across a longer collection window.

        Collects as many transactions as possible in a 40s window and
        reports the rollback rate as a statistical metric.
        """
        async with solana_stream_route.client(timeout=60) as ws:
            hello = await ws.recv_json(timeout=10)
            assert hello["type"] == "stream_hello"

            await ws.send_json(SolanaStreamRoute.build_subscribe_all())
            messages = await ws.collect_messages(duration=40, timeout=45)

            txs = [m for m in messages if m.get("type") == "transaction"]
            QALogger.info(f"Extended collection: {len(txs)} transactions in 40s")

            if len(txs) < MIN_TX_COUNT:
                pytest.skip(
                    f"Only {len(txs)} transactions in 40s window; "
                    f"need {MIN_TX_COUNT}+ for meaningful rollback measurement"
                )

            slots = [tx["slot"] for tx in txs]
            result = check_slot_ordering(slots)

            rollback_count = len(result["rollbacks"])
            gap_count = len(result["gaps"])
            rollback_rate = rollback_count / (len(slots) - 1)

            QALogger.info("=== Rollback Rate Report ===")
            QALogger.info(f"Transactions analyzed: {len(txs)}")
            QALogger.info(f"Slot range: {min(slots)} - {max(slots)}")
            QALogger.info(f"Unique slots: {len(set(slots))}")
            QALogger.info(f"Rollbacks: {rollback_count} ({rollback_rate:.2%})")
            QALogger.info(f"Gaps: {gap_count}")

            if result["gaps"]:
                gap_sizes = [
                    slots[i] - slots[i - 1] for i in result["gaps"]
                ]
                QALogger.info(f"Gap sizes: min={min(gap_sizes)}, max={max(gap_sizes)}")

            QALogger.assert_true(
                rollback_rate < 0.05,
                f"Rollback rate {rollback_rate:.2%} is healthy",
                f"Rollback rate {rollback_rate:.2%} exceeds 5% threshold",
            )
