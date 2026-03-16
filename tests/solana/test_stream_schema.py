"""Unit tests for SolanaTransaction Pydantic model and slot ordering.

These are pure validation tests that don't require network access.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

import allure
from smfs_qa.schemas import SolanaTransaction
from smfs_qa.solana import check_slot_ordering

pytestmark = [pytest.mark.solana]

VALID_TX = {
    "type": "transaction",
    "slot": 290_000_000,
    "signature": (
        "5VERv8NMhJZCpMBzYv8oXsK9VxFDJWtqWoG8cUmKcKJPEqfvGnAkaQnRe3sz2TBPguC6rA6F3YAFn8TfXxd3rvg"
    ),
    "blockTime": 1_700_000_000,
    "fee": 5000,
    "programIds": ["11111111111111111111111111111111"],
}


@allure.feature("Solana Transaction Stream")
@allure.story("Schema Validation")
class TestSolanaTransactionSchema:
    """SolanaTransaction Pydantic model validation tests."""

    def test_valid_transaction_parses(self) -> None:
        """Valid transaction data parses without error."""
        tx = SolanaTransaction.model_validate(VALID_TX)
        assert tx.slot == 290_000_000
        assert tx.fee == 5000

    def test_negative_fee_rejected(self) -> None:
        """Negative fee value is rejected by the validator."""
        data = {**VALID_TX, "fee": -1}
        with pytest.raises(ValidationError, match="non-negative"):
            SolanaTransaction.model_validate(data)

    def test_null_block_time_accepted(self) -> None:
        """blockTime can be null for unconfirmed slots."""
        data = {**VALID_TX, "blockTime": None}
        tx = SolanaTransaction.model_validate(data)
        assert tx.blockTime is None

    def test_empty_program_ids_accepted(self) -> None:
        """Empty programIds list is valid (native SOL transfer)."""
        data = {**VALID_TX, "programIds": []}
        tx = SolanaTransaction.model_validate(data)
        assert tx.programIds == []

    def test_missing_signature_rejected(self) -> None:
        """Transaction without a signature field is rejected."""
        data = {k: v for k, v in VALID_TX.items() if k != "signature"}
        with pytest.raises(ValidationError, match="signature"):
            SolanaTransaction.model_validate(data)

    def test_missing_slot_rejected(self) -> None:
        """Transaction without a slot field is rejected."""
        data = {k: v for k, v in VALID_TX.items() if k != "slot"}
        with pytest.raises(ValidationError, match="slot"):
            SolanaTransaction.model_validate(data)

    def test_zero_fee_accepted(self) -> None:
        """Zero fee is technically valid (fee-exempt transactions)."""
        data = {**VALID_TX, "fee": 0}
        tx = SolanaTransaction.model_validate(data)
        assert tx.fee == 0

    def test_multiple_program_ids_accepted(self) -> None:
        """Multiple programIds are valid for multi-instruction transactions."""
        data = {
            **VALID_TX,
            "programIds": [
                "11111111111111111111111111111111",
                "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA",
            ],
        }
        tx = SolanaTransaction.model_validate(data)
        assert len(tx.programIds) == 2


@allure.feature("Solana Transaction Stream")
@allure.story("Schema Validation")
class TestSlotOrdering:
    """Slot ordering analysis tests."""

    def test_monotonic_slots_no_issues(self) -> None:
        """Strictly increasing slots produce no gaps or rollbacks."""
        result = check_slot_ordering([100, 101, 102, 103])
        assert result["gaps"] == []
        assert result["rollbacks"] == []

    def test_slot_gap_detected(self) -> None:
        """Gap between non-consecutive slots is detected."""
        result = check_slot_ordering([100, 101, 105, 106])
        assert len(result["gaps"]) == 1

    def test_slot_rollback_detected(self) -> None:
        """Decreasing slot value is detected as rollback."""
        result = check_slot_ordering([100, 101, 99, 102])
        assert len(result["rollbacks"]) == 1

    def test_single_slot_no_issues(self) -> None:
        """Single slot list produces no gaps or rollbacks."""
        result = check_slot_ordering([100])
        assert result["gaps"] == []
        assert result["rollbacks"] == []

    def test_empty_slot_list_no_issues(self) -> None:
        """Empty slot list produces no gaps or rollbacks."""
        result = check_slot_ordering([])
        assert result["gaps"] == []
        assert result["rollbacks"] == []

    def test_slot_gap_with_normal_solana_behavior(self) -> None:
        """Gaps of 1 slot are normal on Solana (empty slots are skipped).

        Solana slots are ~400ms. Empty slots produce gaps of 2+ which is
        expected behavior. Only large gaps (10+) would be concerning.
        """
        result = check_slot_ordering([100, 102, 104, 106])
        assert len(result["gaps"]) == 3
        assert result["rollbacks"] == []
