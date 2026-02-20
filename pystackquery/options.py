"""
Configuration options for queries and mutations.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field

from .helpers import default_retry_delay, hash_key
from .types import (
    ErrorCallback,
    MutationErrorCallback,
    MutationFn,
    MutationSettledCallback,
    MutationSuccessCallback,
    QueryFn,
    QueryKey,
    RetryDelayFn,
    SelectFn,
    SettledCallback,
    SuccessCallback,
)


@dataclass
class QueryOptions[T]:
    """
    Configuration for a query.

    Attributes:
        query_key: Unique identifier for this query.
        query_fn: Async function that fetches the data.
        stale_time: Seconds before data is considered stale (default: 0).
        gc_time: Seconds before inactive query is garbage collected (default: 300).
        refetch_interval: If set, automatically refetch every N seconds.
        retry: Number of retry attempts on failure (default: 3).
        retry_delay: Function returning delay for each retry attempt.
        enabled: If False, query will not automatically fetch.
        on_success: Callback invoked on successful fetch.
        on_error: Callback invoked on fetch error.
        on_settled: Callback invoked when fetch completes.
        select: Transform function applied to data before returning.
        placeholder_data: Data to use while first fetch is pending.
    """

    query_key: QueryKey
    query_fn: QueryFn[T]

    stale_time: float = 0.0
    gc_time: float = 300.0
    refetch_interval: float | None = None

    retry: int = 3
    retry_delay: RetryDelayFn = field(default_factory=lambda: default_retry_delay)

    enabled: bool = True

    on_success: SuccessCallback[T] | None = None
    on_error: ErrorCallback | None = None
    on_settled: SettledCallback[T] | None = None

    select: SelectFn[T] | None = None
    placeholder_data: T | None = None

    # Cached key hash (computed once at creation)
    _key_hash: str = field(default="", init=False, repr=False)

    def __post_init__(self) -> None:
        """Cache the key hash on creation."""
        self._key_hash = hash_key(self.query_key)

    def get_key_hash(self) -> str:
        """Get the cached key hash."""
        return self._key_hash


@dataclass
class MutationOptions[TInput, TData]:
    """
    Configuration for a mutation.

    Attributes:
        mutation_fn: Async function that performs the mutation.
        on_success: Callback invoked on successful mutation.
        on_error: Callback invoked on mutation error.
        on_settled: Callback invoked when mutation completes.
        on_mutate: Callback for optimistic updates (can return rollback context).
        retry: Number of retry attempts on failure (default: 0).
        retry_delay: Function returning delay for each retry attempt.
    """

    mutation_fn: MutationFn[TInput, TData]

    on_success: MutationSuccessCallback[TData, TInput] | None = None
    on_error: MutationErrorCallback[TInput] | None = None
    on_settled: MutationSettledCallback[TData, TInput] | None = None
    on_mutate: Callable[[TInput], Awaitable[object] | object] | None = None

    retry: int = 0
    retry_delay: RetryDelayFn = field(default_factory=lambda: default_retry_delay)
