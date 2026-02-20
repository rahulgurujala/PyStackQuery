"""
Type definitions for PyStackQuery.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Protocol

# ─────────────────────────────────────────────────────────────
# Type Aliases (Python 3.12+)
# ─────────────────────────────────────────────────────────────

type QueryKey = tuple[str, ...]
"""
Tuple-based unique identifier for queries.

Examples:
    ("users",)
    ("users", "123")
    ("posts", "user", "42", "page", "1")
"""

type QueryFn[T] = Callable[[], Awaitable[T]]
"""Async function that fetches data."""

type RetryDelayFn = Callable[[int], float]
"""Function that returns delay in seconds for a given retry attempt."""

type SuccessCallback[T] = Callable[[T], object]
"""Callback invoked on successful fetch."""

type ErrorCallback = Callable[[Exception], object]
"""Callback invoked on fetch error."""

type SettledCallback[T] = Callable[[T | None, Exception | None], object]
"""Callback invoked when fetch completes (success or error)."""

type MutationFn[TInput, TData] = Callable[[TInput], Awaitable[TData]]
"""Async function that performs a mutation."""

type MutationSuccessCallback[TData, TInput] = Callable[[TData, TInput], object]
"""Callback invoked on successful mutation."""

type MutationErrorCallback[TInput] = Callable[[Exception, TInput], object]
"""Callback invoked on mutation error."""

type MutationSettledCallback[TData, TInput] = Callable[
    [TData | None, Exception | None, TInput], object
]
"""Callback invoked when mutation completes."""

type SelectFn[T] = Callable[[T], object]
"""Function to transform query data before returning to observers."""


# ─────────────────────────────────────────────────────────────
# Storage Protocols
# ─────────────────────────────────────────────────────────────


class StorageBackend(Protocol):
    """
    Interface for external caching tools (Redis, aiocache, diskcache, etc.).

    Any class that implements these methods can be used as a persistent
    L2 cache for PyStackQuery.
    """

    async def get(self, key: str) -> str | None:
        """Get serialized data for a key."""
        ...

    async def set(self, key: str, value: str, ttl: float | None = None) -> None:
        """Set serialized data for a key with optional TTL."""
        ...

    async def delete(self, key: str) -> None:
        """Delete data for a key."""
        ...
