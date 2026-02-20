"""
Query class - handles the lifecycle of a single data-fetching operation.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
import weakref
from collections.abc import Callable
from typing import TYPE_CHECKING, cast

from .options import QueryOptions
from .state import FetchStatus, QueryState, QueryStatus
from .types import StorageBackend

if TYPE_CHECKING:
    from .observer import QueryObserver

logger = logging.getLogger("pystackquery")


class Query[T]:
    """
    Core state machine for data fetching.

    Manages concurrent request deduplication, exponential backoff retries,
    and automatic GC via weakref observers.
    """

    __slots__ = (
        "options",
        "key",
        "key_hash",
        "storage",
        "_state",
        "_observers",
        "_current_fetch",
        "_gc_task",
        "_refetch_task",
        "_lock",
        "_notify_gc_ready",
        "_is_hydrating",
    )

    def __init__(
        self, options: QueryOptions[T], storage: StorageBackend | None = None
    ) -> None:
        self.options: QueryOptions[T] = options
        self.key: tuple[str, ...] = options.query_key
        self.key_hash: str = options.get_key_hash()
        self.storage: StorageBackend | None = storage

        # Placeholder data allows UI to show "something" while cold-fetching.
        self._state: QueryState[T, Exception] = QueryState(
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
        self._notify_gc_ready: Callable[[], None] = lambda: None
        self._is_hydrating: bool = False

    @property
    def state(self) -> QueryState[T, Exception]:
        return self._state

    @property
    def observer_count(self) -> int:
        self._cleanup_observers()
        return len(self._observers)

    def is_stale(self) -> bool:
        """
        Calculates staleness using wall-clock time (time.time()) to remain
        consistent across L2 hydration and process restarts.
        """
        if self._state.data_updated_at is None:
            return True
        elapsed = time.time() - self._state.data_updated_at
        return elapsed > self.options.stale_time

    def _dispatch(self, **updates: object) -> None:
        """
        Updates internal state and notifies L1 observers.
        Successful results trigger a background L2 persistence task.
        """
        current = self._state
        self._state = QueryState(
            status=cast(QueryStatus, updates.get("status", current.status)),
            fetch_status=cast(
                FetchStatus, updates.get("fetch_status", current.fetch_status)
            ),
            data=cast(T, updates.get("data", current.data)),
            error=cast(Exception, updates.get("error", current.error)),
            data_updated_at=cast(
                float, updates.get("data_updated_at", current.data_updated_at)
            ),
            error_updated_at=cast(
                float, updates.get("error_updated_at", current.error_updated_at)
            ),
            fetch_failure_count=cast(
                int, updates.get("fetch_failure_count", current.fetch_failure_count)
            ),
            fetch_failure_reason=cast(
                Exception,
                updates.get("fetch_failure_reason", current.fetch_failure_reason),
            ),
        )

        self._notify_observers()

        if self.storage and self._state.status == QueryStatus.SUCCESS:
            try:
                loop = asyncio.get_running_loop()
                loop.create_task(self._persist_state())
            except RuntimeError:
                pass # Event loop is stopping

    async def _persist_state(self) -> None:
        """Background L2 synchronization."""
        if self.storage:
            try:
                serialized = json.dumps(self._state.to_dict())
                await self.storage.set(
                    self.key_hash, serialized, ttl=self.options.gc_time
                )
            except Exception as e:
                logger.error("L2 Persistence failure for %s: %s", self.key, e)

    async def hydrate(self) -> bool:
        """
        Attempts to pull state from L2. Returns True if hydration succeeded.
        This is typically called by the client in the background.
        """
        if not self.storage or self._is_hydrating:
            return False

        self._is_hydrating = True
        try:
            serialized = await self.storage.get(self.key_hash)
            if serialized:
                state_dict = cast(dict[str, object], json.loads(serialized))
                new_state = QueryState[T, Exception].from_dict(state_dict)
                self._state = new_state
                self._notify_observers()
                return True
        except Exception as e:
            logger.error("L2 Hydration failure for %s: %s", self.key, e)
        finally:
            self._is_hydrating = False
        return False

    def _notify_observers(self) -> None:
        self._cleanup_observers()
        for ref in self._observers:
            obs = ref()
            if obs is not None:
                obs._on_query_update(self._state)

    def _cleanup_observers(self) -> None:
        self._observers = [r for r in self._observers if r() is not None]

    def add_observer(self, observer: QueryObserver[T]) -> None:
        self._observers.append(weakref.ref(observer))
        self._cancel_gc()

    def remove_observer(self, observer: QueryObserver[T]) -> None:
        self._observers = [
            r for r in self._observers if r() is not None and r() is not observer
        ]
        if self.observer_count == 0:
            self._schedule_gc()

    async def wait_for_hydration(self) -> None:
        """
        Blocks until background L2 hydration finishes.
        Crucial for ensuring SWR logic sees the persisted data.
        """
        if self._is_hydrating:
            while self._is_hydrating:
                await asyncio.sleep(0.01)

    async def fetch(self) -> T:
        """
        Primary entry point for fetching data.
        Uses internal lock to deduplicate concurrent calls to the same key.
        """
        async with self._lock:
            if self._current_fetch is not None and not self._current_fetch.done():
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
        """Internal implementation of fetch with retry logic."""
        if self._is_hydrating:
            await self.wait_for_hydration()

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
                    data_updated_at=time.time(),
                    fetch_failure_count=0,
                    fetch_failure_reason=None,
                )

                if self.options.on_success:
                    self.options.on_success(data)
                if self.options.on_settled:
                    self.options.on_settled(data, None)

                return data

            except Exception as e:
                last_error = e
                self._dispatch(
                    fetch_failure_count=attempt + 1,
                    fetch_failure_reason=e,
                )
                if attempt < self.options.retry:
                    delay_val = self.options.retry_delay(attempt)
                    await asyncio.sleep(delay_val)

        assert last_error is not None
        self._dispatch(
            status=QueryStatus.ERROR,
            fetch_status=FetchStatus.IDLE,
            error=last_error,
            error_updated_at=time.time(),
        )

        if self.options.on_error:
            self.options.on_error(last_error)
        if self.options.on_settled:
            self.options.on_settled(self._state.data, last_error)

        raise last_error

    def _schedule_gc(self) -> None:
        if self._gc_task is not None:
            return
        self._gc_task = asyncio.create_task(self._gc_timer())

    async def _gc_timer(self) -> None:
        """Wait for gc_time then notify cache for removal."""
        try:
            await asyncio.sleep(self.options.gc_time)
            if self.observer_count == 0:
                self._notify_gc_ready()
        except asyncio.CancelledError:
            pass

    def _cancel_gc(self) -> None:
        if self._gc_task is not None:
            return
        if self._gc_task is not None:
            self._gc_task.cancel()
            self._gc_task = None

    def start_refetch_interval(self) -> None:
        if self.options.refetch_interval is None or self._refetch_task is not None:
            return
        self._refetch_task = asyncio.create_task(self._refetch_loop())

    async def _refetch_loop(self) -> None:
        """Periodic background refetch while observers exist."""
        try:
            while True:
                interval = self.options.refetch_interval
                if interval is None:
                    break
                await asyncio.sleep(interval)
                if self.observer_count > 0:
                    await self.fetch()
        except asyncio.CancelledError:
            pass

    def stop_refetch_interval(self) -> None:
        if self._refetch_task is not None:
            self._refetch_task.cancel()
            self._refetch_task = None

    def pause(self) -> None:
        """Stops background work and marks status as PAUSED."""
        self._dispatch(fetch_status=FetchStatus.PAUSED)
        self.stop_refetch_interval()

    def resume(self, *, refetch: bool = False) -> None:
        """Resumes background polling and optionally triggers a fresh fetch."""
        if self._state.fetch_status == FetchStatus.PAUSED:
            self._dispatch(fetch_status=FetchStatus.IDLE)
            self.start_refetch_interval()
            if refetch:
                asyncio.create_task(self.fetch())

    @property
    def is_paused(self) -> bool:
        return self._state.fetch_status == FetchStatus.PAUSED

    def destroy(self) -> None:
        """Force cleanup of all async tasks."""
        self._cancel_gc()
        self.stop_refetch_interval()
        if self._current_fetch and not self._current_fetch.done():
            self._current_fetch.cancel()
