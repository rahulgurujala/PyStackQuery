"""
Query state management.
"""

from __future__ import annotations

from enum import Enum, auto
from typing import Generic

from .types import T, TError


class QueryStatus(Enum):
    """Primary status of a query."""

    IDLE = auto()
    """Query has not been triggered yet."""

    PENDING = auto()
    """First fetch in progress, no data available yet."""

    SUCCESS = auto()
    """Data fetched successfully."""

    ERROR = auto()
    """Fetch resulted in an error."""


class FetchStatus(Enum):
    """Whether a query is currently fetching (orthogonal to QueryStatus)."""

    IDLE = auto()
    """Not currently fetching."""

    FETCHING = auto()
    """Currently fetching data."""

    PAUSED = auto()
    """Fetch paused (e.g., offline)."""


class QueryState(Generic[T, TError]):
    """
    Query state container with optimized attribute access.

    Uses __slots__ for memory efficiency and fast attribute access.

    Type Parameters:
        T: The type of data this query returns.
        TError: The type of error (defaults to Exception).
    """

    __slots__ = (
        "status",
        "fetch_status",
        "data",
        "error",
        "data_updated_at",
        "error_updated_at",
        "fetch_failure_count",
        "fetch_failure_reason",
    )

    def __init__(
        self,
        status: QueryStatus = QueryStatus.IDLE,
        fetch_status: FetchStatus = FetchStatus.IDLE,
        data: T | None = None,
        error: TError | None = None,
        data_updated_at: float | None = None,
        error_updated_at: float | None = None,
        fetch_failure_count: int = 0,
        fetch_failure_reason: TError | None = None,
    ) -> None:
        self.status: QueryStatus = status
        self.fetch_status: FetchStatus = fetch_status
        self.data: T | None = data
        self.error: TError | None = error
        self.data_updated_at: float | None = data_updated_at
        self.error_updated_at: float | None = error_updated_at
        self.fetch_failure_count: int = fetch_failure_count
        self.fetch_failure_reason: TError | None = fetch_failure_reason

    @property
    def is_idle(self) -> bool:
        """True if query has not been triggered."""
        return self.status == QueryStatus.IDLE

    @property
    def is_pending(self) -> bool:
        """True if query is pending (first fetch, no data yet)."""
        return self.status == QueryStatus.PENDING

    @property
    def is_success(self) -> bool:
        """True if query completed successfully."""
        return self.status == QueryStatus.SUCCESS

    @property
    def is_error(self) -> bool:
        """True if query resulted in an error."""
        return self.status == QueryStatus.ERROR

    @property
    def is_fetching(self) -> bool:
        """True if query is currently fetching."""
        return self.fetch_status == FetchStatus.FETCHING

    @property
    def is_loading(self) -> bool:
        """True when fetching for the first time (no data yet)."""
        return self.is_pending and self.is_fetching

    @property
    def has_data(self) -> bool:
        """True if data is available."""
        return self.data is not None

    def __repr__(self) -> str:
        return (
            f"QueryState(status={self.status.name}, "
            f"fetch_status={self.fetch_status.name}, "
            f"has_data={self.has_data})"
        )


class MutationStatus(Enum):
    """Status of a mutation."""

    IDLE = auto()
    """Mutation has not been triggered."""

    PENDING = auto()
    """Mutation in progress."""

    SUCCESS = auto()
    """Mutation completed successfully."""

    ERROR = auto()
    """Mutation resulted in an error."""


class MutationState(Generic[T, TError]):
    """
    Mutation state container with optimized attribute access.

    Type Parameters:
        T: The type of data this mutation returns.
        TError: The type of error (defaults to Exception).
    """

    __slots__ = ("status", "data", "error", "submitted_at", "settled_at")

    def __init__(
        self,
        status: MutationStatus = MutationStatus.IDLE,
        data: T | None = None,
        error: TError | None = None,
        submitted_at: float | None = None,
        settled_at: float | None = None,
    ) -> None:
        self.status: MutationStatus = status
        self.data: T | None = data
        self.error: TError | None = error
        self.submitted_at: float | None = submitted_at
        self.settled_at: float | None = settled_at

    @property
    def is_idle(self) -> bool:
        return self.status == MutationStatus.IDLE

    @property
    def is_pending(self) -> bool:
        return self.status == MutationStatus.PENDING

    @property
    def is_success(self) -> bool:
        return self.status == MutationStatus.SUCCESS

    @property
    def is_error(self) -> bool:
        return self.status == MutationStatus.ERROR

    def __repr__(self) -> str:
        return f"MutationState(status={self.status.name})"
