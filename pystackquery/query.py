"""
Query class - the core unit of data fetching.
"""

from __future__ import annotations

import asyncio
import logging
import time
import weakref
from typing import TYPE_CHECKING, Any, Generic

from .options import QueryOptions
from .state import FetchStatus, QueryState, QueryStatus
from .types import T

if TYPE_CHECKING:
    from .observer import QueryObserver

logger = logging.getLogger("pystackquery")


class Query(Generic[T]):
    """
    A single query instance managing fetch state, caching, and observers.

    Features:
        - Request deduplication (concurrent requests share one fetch)
        - Automatic retry with exponential backoff
        - Observer pattern for reactive updates
        - Garbage collection when no observers remain
    """

    __slots__ = (
        "options",
        "key",
        "key_hash",
        "_state",
        "_observers",
        "_current_fetch",
        "_gc_task",
        "_refetch_task",
        "_lock",
        "_notify_gc_ready",
    )

    def __init__(self, options: QueryOptions[T]) -> None:
        """
        Initialize a query.

        Args:
            options: Query configuration.
        """
        self.options: QueryOptions[T] = options
        self.key: tuple[str, ...] = options.query_key
        self.key_hash: str = options.get_key_hash()

        self._state: QueryState[T] = QueryState(
            data=options.placeholder_data,
            status=(
                QueryStatus.SUCCESS
                if options.placeholder_data is not None
                else QueryStatus.IDLE
            ),
        )

        self._observers: list[weakref.ref[QueryObserver[T]]] = []
        self._current_fetch: asyncio.Task[T] | None = None
        self._gc_task: asyncio.Task[None] | None = None
        self._refetch_task: asyncio.Task[None] | None = None
        self._lock: asyncio.Lock = asyncio.Lock()
        self._notify_gc_ready: Any = lambda: None

    @property
    def state(self) -> QueryState[T]:
        """Current query state."""
        return self._state

    @property
    def observer_count(self) -> int:
        """Number of active observers."""
        self._cleanup_observers()
        return len(self._observers)

    def is_stale(self) -> bool:
        """
        Check if the query's data is stale.

        Returns:
            True if data is stale or doesn't exist.
        """
        if self._state.data_updated_at is None:
            return True
        elapsed = time.monotonic() - self._state.data_updated_at
        return elapsed > self.options.stale_time

    def _dispatch(self, **updates: Any) -> None:
        """
        Update state and notify observers.

        Args:
            **updates: State fields to update.
        """
        current = self._state
        self._state = QueryState(
            status=updates.get("status", current.status),
            fetch_status=updates.get("fetch_status", current.fetch_status),
            data=updates.get("data", current.data),
            error=updates.get("error", current.error),
            data_updated_at=updates.get("data_updated_at", current.data_updated_at),
            error_updated_at=updates.get("error_updated_at", current.error_updated_at),
            fetch_failure_count=updates.get(
                "fetch_failure_count", current.fetch_failure_count
            ),
            fetch_failure_reason=updates.get(
                "fetch_failure_reason", current.fetch_failure_reason
            ),
        )
        self._notify_observers()

    def _notify_observers(self) -> None:
        """Notify all active observers about state change."""
        self._cleanup_observers()
        for ref in self._observers:
            obs = ref()
            if obs is not None:
                obs._on_query_update(self._state)

    def _cleanup_observers(self) -> None:
        """Remove dead weak references."""
        self._observers = [r for r in self._observers if r() is not None]

    def add_observer(self, observer: QueryObserver[T]) -> None:
        """
        Add an observer to this query.

        Args:
            observer: The observer to add.
        """
        self._observers.append(weakref.ref(observer))
        self._cancel_gc()
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug(
                "Observer added to %s, count=%d", self.key, self.observer_count
            )

    def remove_observer(self, observer: QueryObserver[T]) -> None:
        """
        Remove an observer from this query.

        Args:
            observer: The observer to remove.
        """
        self._observers = [
            r for r in self._observers if r() is not None and r() is not observer
        ]
        if self.observer_count == 0:
            self._schedule_gc()
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug(
                "Observer removed from %s, count=%d", self.key, self.observer_count
            )

    async def fetch(self) -> T:
        """
        Fetch data with deduplication and retry.

        If a fetch is already in progress, piggybacks on that request.
        Uses a lock to prevent race conditions between check and task creation.

        Returns:
            The fetched data.

        Raises:
            Exception: If all retry attempts fail.
        """
        async with self._lock:
            if self._current_fetch is not None and not self._current_fetch.done():
                if logger.isEnabledFor(logging.DEBUG):
                    logger.debug("Deduplicating fetch for %s", self.key)
                fetch_task = self._current_fetch
            else:
                self._current_fetch = asyncio.create_task(self._do_fetch())
                fetch_task = self._current_fetch

        try:
            return await fetch_task
        finally:
            async with self._lock:
                if self._current_fetch is fetch_task:
                    self._current_fetch = None

    async def _do_fetch(self) -> T:
        """Internal fetch with retry logic."""
        is_first_fetch = self._state.data is None

        self._dispatch(
            status=QueryStatus.PENDING if is_first_fetch else self._state.status,
            fetch_status=FetchStatus.FETCHING,
        )

        last_error: Exception | None = None

        for attempt in range(self.options.retry + 1):
            try:
                data = await self.options.query_fn()

                self._dispatch(
                    status=QueryStatus.SUCCESS,
                    fetch_status=FetchStatus.IDLE,
                    data=data,
                    error=None,
                    data_updated_at=time.monotonic(),
                    fetch_failure_count=0,
                    fetch_failure_reason=None,
                )

                if self.options.on_success:
                    self.options.on_success(data)
                if self.options.on_settled:
                    self.options.on_settled(data, None)

                if logger.isEnabledFor(logging.DEBUG):
                    logger.debug("Fetch success for %s", self.key)
                return data

            except Exception as e:
                last_error = e
                self._dispatch(
                    fetch_failure_count=attempt + 1,
                    fetch_failure_reason=e,
                )
                if logger.isEnabledFor(logging.WARNING):
                    logger.warning(
                        "Fetch attempt %d/%d failed for %s: %s",
                        attempt + 1,
                        self.options.retry + 1,
                        self.key,
                        e,
                    )

                if attempt < self.options.retry:
                    delay = self.options.retry_delay(attempt)
                    await asyncio.sleep(delay)

        assert last_error is not None
        self._dispatch(
            status=QueryStatus.ERROR,
            fetch_status=FetchStatus.IDLE,
            error=last_error,
            error_updated_at=time.monotonic(),
        )

        if self.options.on_error:
            self.options.on_error(last_error)
        if self.options.on_settled:
            self.options.on_settled(self._state.data, last_error)

        raise last_error

    def _schedule_gc(self) -> None:
        """Schedule garbage collection when no observers remain."""
        if self._gc_task is not None:
            return
        self._gc_task = asyncio.create_task(self._gc_timer())

    async def _gc_timer(self) -> None:
        """Wait for gc_time then notify cache for removal."""
        try:
            await asyncio.sleep(self.options.gc_time)
            if self.observer_count == 0:
                if logger.isEnabledFor(logging.DEBUG):
                    logger.debug("GC collecting query %s", self.key)
                self._notify_gc_ready()
        except asyncio.CancelledError:
            pass

    def _cancel_gc(self) -> None:
        """Cancel scheduled garbage collection."""
        if self._gc_task is not None:
            self._gc_task.cancel()
            self._gc_task = None

    def start_refetch_interval(self) -> None:
        """Start automatic refetching at configured interval."""
        if self.options.refetch_interval is None:
            return
        if self._refetch_task is not None:
            return
        self._refetch_task = asyncio.create_task(self._refetch_loop())

    async def _refetch_loop(self) -> None:
        """Periodically refetch while observers exist."""
        assert self.options.refetch_interval is not None
        try:
            while True:
                await asyncio.sleep(self.options.refetch_interval)
                if self.observer_count > 0:
                    if logger.isEnabledFor(logging.DEBUG):
                        logger.debug("Interval refetch for %s", self.key)
                    await self.fetch()
        except asyncio.CancelledError:
            pass

    def stop_refetch_interval(self) -> None:
        """Stop automatic refetching."""
        if self._refetch_task is not None:
            self._refetch_task.cancel()
            self._refetch_task = None

    def pause(self) -> None:
        """
        Pause the query, stopping any automatic refetching.

        Useful for offline mode or rate limiting scenarios.
        The query can be resumed with resume().
        """
        self._dispatch(fetch_status=FetchStatus.PAUSED)
        self.stop_refetch_interval()
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug("Query paused: %s", self.key)

    def resume(self, *, refetch: bool = False) -> None:
        """
        Resume a paused query.

        Args:
            refetch: If True, immediately trigger a refetch.
        """
        if self._state.fetch_status == FetchStatus.PAUSED:
            self._dispatch(fetch_status=FetchStatus.IDLE)
            self.start_refetch_interval()
            if refetch:
                asyncio.create_task(self.fetch())
            if logger.isEnabledFor(logging.DEBUG):
                logger.debug("Query resumed: %s", self.key)

    @property
    def is_paused(self) -> bool:
        """Check if the query is currently paused."""
        return self._state.fetch_status == FetchStatus.PAUSED

    def destroy(self) -> None:
        """Clean up all async resources."""
        self._cancel_gc()
        self.stop_refetch_interval()
        if self._current_fetch and not self._current_fetch.done():
            self._current_fetch.cancel()
