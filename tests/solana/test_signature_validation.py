"""Unit tests for Solana signature and pubkey validation utilities.

Uses solders (Rust-backed) for cryptographically correct validation:
signatures must be valid Base58 that decodes to exactly 64 bytes (Ed25519).
"""

from __future__ import annotations

import pytest

import allure
from smfs_qa.solana import (
    BASE58_ALPHABET,
    WELL_KNOWN_PROGRAMS,
    is_valid_pubkey,
    is_valid_solana_signature,
)

pytestmark = [pytest.mark.solana]

VALID_SIG_87 = (
    "5VERv8NMhJZCpMBzYv8oXsK9VxFDJWtqWoG8cUmKcKJP"
    "EqfvGnAkaQnRe3sz2TBPguC6rA6F3YAFn8TfXxd3rvg"
)

VALID_SIG_88 = (
    "2297c4pup8s2D1n6pVFBWg3TMpmsDThCCGW17xZ1dSFA"
    "7HZvqUGVRoLZNJMPUabmqCid9vwaHnfVCxCXyjxuzkgN"
)


@allure.feature("Solana Transaction Stream")
@allure.story("Signature Validation")
class TestSignatureValidation:
    """Solana signature format validation tests (solders-backed)."""

    def test_valid_87_char_signature_accepted(self) -> None:
        """Known-good 87-char Base58 signature decodes to 64 bytes."""
        assert len(VALID_SIG_87) == 87
        assert is_valid_solana_signature(VALID_SIG_87) is True

    def test_valid_88_char_signature_accepted(self) -> None:
        """Known-good 88-char Base58 signature decodes to 64 bytes."""
        assert len(VALID_SIG_88) == 88
        assert is_valid_solana_signature(VALID_SIG_88) is True

    def test_arbitrary_43_chars_rejected_by_solders(self) -> None:
        """43 repeated chars are valid Base58 but don't decode to 64 bytes.

        With solders cryptographic validation, length alone is not sufficient.
        The string must decode to exactly 64 bytes.
        """
        sig_43 = "A" * 43
        assert is_valid_solana_signature(sig_43) is False

    def test_42_char_below_minimum_rejected(self) -> None:
        """42-character string is rejected (below minimum length)."""
        assert is_valid_solana_signature("A" * 42) is False

    def test_short_signature_rejected(self) -> None:
        """Signature shorter than 43 chars is invalid."""
        assert is_valid_solana_signature("abc123") is False

    def test_non_base58_chars_rejected(self) -> None:
        """Signature containing non-Base58 chars (0, O, I, l) is invalid."""
        assert is_valid_solana_signature("0" * 88) is False

    def test_empty_string_rejected(self) -> None:
        """Empty string is not a valid signature."""
        assert is_valid_solana_signature("") is False

    def test_base58_alphabet_excludes_ambiguous_chars(self) -> None:
        """Base58 alphabet excludes 0, O, I, l to avoid visual ambiguity."""
        assert "0" not in BASE58_ALPHABET
        assert "O" not in BASE58_ALPHABET
        assert "I" not in BASE58_ALPHABET
        assert "l" not in BASE58_ALPHABET

    def test_89_char_overlong_signature_rejected(self) -> None:
        """89-character string exceeds maximum valid length."""
        overlong = VALID_SIG_87 + "AB"
        assert len(overlong) == 89
        assert is_valid_solana_signature(overlong) is False

    def test_solders_validates_byte_length(self) -> None:
        """solders rejects Base58 strings that don't decode to 64 bytes.

        This proves we're doing cryptographic validation, not just
        charset + length checks.
        """
        valid_base58_wrong_bytes = "1" * 60
        assert is_valid_solana_signature(valid_base58_wrong_bytes) is False


@allure.feature("Solana Transaction Stream")
@allure.story("Signature Validation")
class TestPubkeyValidation:
    """Solana public key validation tests (solders-backed)."""

    def test_system_program_is_valid_pubkey(self) -> None:
        """System Program address (32 bytes of zeros) is a valid pubkey."""
        assert is_valid_pubkey(WELL_KNOWN_PROGRAMS["SYSTEM_PROGRAM"]) is True

    def test_spl_token_is_valid_pubkey(self) -> None:
        """SPL Token Program address is a valid pubkey."""
        assert is_valid_pubkey(WELL_KNOWN_PROGRAMS["SPL_TOKEN"]) is True

    def test_invalid_pubkey_rejected(self) -> None:
        """Invalid Base58 pubkey is rejected."""
        assert is_valid_pubkey("INVALID0ADDRESS") is False

    def test_empty_pubkey_rejected(self) -> None:
        """Empty string is not a valid pubkey."""
        assert is_valid_pubkey("") is False
