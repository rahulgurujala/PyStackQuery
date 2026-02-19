"""
Helper utilities for PyStackQuery.
"""

from __future__ import annotations

from .types import QueryKey


def hash_key(key: QueryKey) -> str:
    """
    Create a string hash for a query key.

    Uses simple string conversion for speed.
    Tuples are hashable and their string representation is stable.

    Args:
        key: The query key tuple.

    Returns:
        String representation of the key for cache lookup.
    """
    return str(key)


def partial_match(filter_key: QueryKey, target_key: QueryKey) -> bool:
    """
    Check if filter_key is a prefix of target_key.

    Enables invalidating groups of related queries.

    Args:
        filter_key: The prefix to match.
        target_key: The full key to check against.

    Returns:
        True if filter_key is a prefix of target_key.

    Examples:
        >>> partial_match(("todos",), ("todos", "active"))
        True
        >>> partial_match(("todos",), ("users",))
        False
        >>> partial_match(("todos", "active"), ("todos",))
        False
    """
    if len(filter_key) > len(target_key):
        return False
    return target_key[: len(filter_key)] == filter_key


def default_retry_delay(attempt: int) -> float:
    """
    Default exponential backoff retry delay.

    Args:
        attempt: Zero-indexed retry attempt number.

    Returns:
        Delay in seconds, capped at 30 seconds.
    """
    delay = 1.0 * (2**attempt)
    return delay if delay < 30.0 else 30.0
