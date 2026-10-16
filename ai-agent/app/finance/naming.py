"""Small helpers for labelling records in user-facing output."""
from __future__ import annotations


def suffixed(name: str, suffix: str) -> str:
    """'Home loan' + 'EMI' -> 'Home loan EMI', but 'iPhone EMI' + 'EMI'
    stays put.

    Users already name these things after what they are, and "iPhone EMI
    EMI" in a bill reminder reads like a bug because it is one.
    """
    name = (name or "").strip()
    if not suffix:
        return name
    return name if name.casefold().endswith(suffix.casefold()) else f"{name} {suffix}"
