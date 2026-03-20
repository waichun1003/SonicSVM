"""Solana-specific validation utilities.

Uses solders (Rust-backed) for cryptographically correct Base58 and
Ed25519 signature validation, not just charset/length checks.
"""

from __future__ import annotations

from solders.pubkey import Pubkey
from solders.signature import Signature

BASE58_ALPHABET = set("123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz")


def is_valid_base58(value: str) -> bool:
    """Check if a string contains only valid Base58 characters."""
    if not value:
        return False
    return all(c in BASE58_ALPHABET for c in value)


def is_valid_solana_signature(sig: str) -> bool:
    """Validate a Solana transaction signature using solders.

    Performs cryptographic validation: the string must be valid Base58
    that decodes to exactly 64 bytes (Ed25519 signature size).
    Returns False immediately if Base58 charset, length, or solders
    parsing fails -- there is no fallback.
    """
    if not is_valid_base58(sig):
        return False
    if not (43 <= len(sig) <= 88):
        return False
    try:
        parsed = Signature.from_string(sig)
        return len(bytes(parsed)) == 64
    except (ValueError, RuntimeError):
        return False


def is_valid_pubkey(key: str) -> bool:
    """Validate a Solana public key using solders.

    The string must be valid Base58 that decodes to exactly 32 bytes.
    """
    if not is_valid_base58(key):
        return False
    try:
        parsed = Pubkey.from_string(key)
        return len(bytes(parsed)) == 32
    except (ValueError, RuntimeError):
        return False


def check_slot_ordering(slots: list[int]) -> dict[str, list[int]]:
    """Analyze slot ordering for gaps and rollbacks.

    Returns dict with:
    - 'gaps': indices where slot jumped by more than 1
    - 'rollbacks': indices where slot decreased (reorg indicator)
    """
    gaps: list[int] = []
    rollbacks: list[int] = []

    for i in range(1, len(slots)):
        diff = slots[i] - slots[i - 1]
        if diff < 0:
            rollbacks.append(i)
        elif diff > 1:
            gaps.append(i)

    return {"gaps": gaps, "rollbacks": rollbacks}


WELL_KNOWN_PROGRAMS: dict[str, str] = {
    "SYSTEM_PROGRAM": "11111111111111111111111111111111",
    "SPL_TOKEN": "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA",
    "TOKEN_2022": "TokenzQdBNbLqP5VEhdkAS6EPFLC1PHnBqCXEpPxuEb",
    "MEMO": "MemoSq4gqABAXKb96qnH8TysNcWxMyWCqXgDLGmfcHr",
    "COMPUTE_BUDGET": "ComputeBudget111111111111111111111111111111",
}
