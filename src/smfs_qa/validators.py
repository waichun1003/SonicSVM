"""Shared validation utilities for test assertions."""

from __future__ import annotations


def has_float_artifact(value: float, max_decimal_digits: int = 4) -> bool:
    """Check if a float has IEEE 754 representation artifacts.

    Returns True if repr(value) has more decimal digits than max_decimal_digits,
    indicating a floating-point artifact like 65922.40000000001.
    """
    r = repr(value)
    if "." not in r:
        return False
    _, dec_part = r.split(".")
    return len(dec_part) > max_decimal_digits
