"""
Type definitions for PyStackQuery.
"""

from __future__ import annotations

from typing import Any, Awaitable, Callable

from typing_extensions import TypeVar

# ─────────────────────────────────────────────────────────────
# Type Variables
# ─────────────────────────────────────────────────────────────

T = TypeVar("T")
"""Generic type for query data."""

TData = TypeVar("TData")
"""Generic type for mutation return data."""

TInput = TypeVar("TInput")
"""Generic type for mutation input."""

TError = TypeVar("TError", bound=Exception, default=Exception)
"""Generic type for errors. Defaults to Exception if not specified."""

# ─────────────────────────────────────────────────────────────
# Type Aliases
# ─────────────────────────────────────────────────────────────

QueryKey = tuple[str, ...]
"""
Tuple-based unique identifier for queries.

Examples:
    ("users",)
    ("users", "123")
    ("posts", "user", "42", "page", "1")
"""

QueryFn = Callable[[], Awaitable[T]]
"""Async function that fetches data."""

RetryDelayFn = Callable[[int], float]
"""Function that returns delay in seconds for a given retry attempt."""

SuccessCallback = Callable[[T], Any]
"""Callback invoked on successful fetch."""

ErrorCallback = Callable[[Exception], Any]
"""Callback invoked on fetch error."""

SettledCallback = Callable[[T | None, Exception | None], Any]
"""Callback invoked when fetch completes (success or error)."""

MutationFn = Callable[[TInput], Awaitable[TData]]
"""Async function that performs a mutation."""

MutationSuccessCallback = Callable[[TData, TInput], Any]
"""Callback invoked on successful mutation."""

MutationErrorCallback = Callable[[Exception, TInput], Any]
"""Callback invoked on mutation error."""

MutationSettledCallback = Callable[[TData | None, Exception | None, TInput], Any]
"""Callback invoked when mutation completes."""

SelectFn = Callable[[T], Any]
"""Function to transform query data before returning to observers."""
