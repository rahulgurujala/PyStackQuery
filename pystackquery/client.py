"""
QueryClient - Central orchestrator for state management and caching.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from dataclasses import dataclass, field
from typing import cast

from .cache import QueryCache
from .helpers import default_retry_delay, hash_key
from .mutation import Mutation
from .observer import QueryObserver
from .options import MutationOptions, QueryOptions
from .query import Query
from .state import FetchStatus, QueryState, QueryStatus
from .types import QueryKey, RetryDelayFn, StorageBackend

logger = logging.getLogger("pystackquery")


@dataclass
class QueryClientConfig:
    """
    Global defaults for the client instance. Individual queries can override these.
    """
    stale_time: float = 0.0
    gc_time: float = 300.0
    retry: int = 3
    retry_delay: RetryDelayFn = field(default_factory=lambda: default_retry_delay)
    cache_max_size: int = 1000
    storage: StorageBackend | None = None


class QueryClient:
    """
    Main entry point for PyStackQuery.
    Manages the dual-tier cache (L1 memory, L2 persistent).
    """

    __slots__ = ("_config", "_cache")

    def __init__(self, config: QueryClientConfig | None = None) -> None:
        self._config: QueryClientConfig = config or QueryClientConfig()
        self._cache: QueryCache = QueryCache(
            max_size=self._config.cache_max_size, storage=self._config.storage
        )

    @property
    def cache(self) -> QueryCache:
        return self._cache

    def _get_or_create_query[T](self, options: QueryOptions[T]) -> Query[T]:
        """
        Retrieves a query from L1 or creates it fresh.
        If L2 storage exists, a background hydration task is kicked off immediately.
        """
        key_hash = options.get_key_hash()

        # L1 Hit (Fastest)
        existing: Query[T] | None = self._cache.get(key_hash)
        if existing is not None:
            return existing

        # Cache Miss - Setup new instance and start hydration
        query: Query[T] = self._create_query_instance(options)
        self._cache.add(query)

        if self._cache.storage:
            try:
                loop = asyncio.get_running_loop()
                loop.create_task(query.hydrate())
            except RuntimeError:
                pass # Sync context or loop shutting down

        return query

    def _create_query_instance[T](self, options: QueryOptions[T]) -> Query[T]:
        """Inherits client-level defaults for query instances."""
        if options.stale_time == 0.0 and self._config.stale_time != 0.0:
            options.stale_time = self._config.stale_time
        if options.gc_time == 300.0 and self._config.gc_time != 300.0:
            options.gc_time = self._config.gc_time
        if options.retry == 3 and self._config.retry != 3:
            options.retry = self._config.retry

        return Query(options, storage=self._cache.storage)

    async def fetch_query[T](self, options: QueryOptions[T]) -> T:
        """
        Implementation of the Stale-While-Revalidate (SWR) pattern.
        Ensures L2 hydration is settled before checking data availability.
        """
        query: Query[T] = self._get_or_create_query(options)

        # Ensure L2 hydration settles so we don't double-fetch cold data
        await asyncio.sleep(0)
        await query.wait_for_hydration()

        if query.state.data is not None:
            if not query.is_stale():
                return query.state.data

            # Data exists but is stale - return it and trigger background refresh
            asyncio.create_task(query.fetch())
            return query.state.data

        # Cold fetch (Miss)
        return await query.fetch()

    async def prefetch_query[T](self, options: QueryOptions[T]) -> None:
        """Warms up the cache for a key without blocking for the result."""
        query: Query[T] = self._get_or_create_query(options)
        await query.wait_for_hydration()
        if query.state.data is None or query.is_stale():
            try:
                await query.fetch()
            except Exception:
                pass # Prefetches fail silently

    async def get_query_data_async[T](self, key: QueryKey) -> T | None:
        """Checks both memory and persistence for data."""
        key_hash = hash_key(key)
        existing: Query[object] | None = self._cache.get(key_hash)
        if existing:
            return cast(T, existing.state.data)

        if self._cache.storage:
            try:
                serialized = await self._cache.storage.get(key_hash)
                if serialized:
                    state_dict = cast(dict[str, object], json.loads(serialized))
                    return cast(T, state_dict.get("data"))
            except Exception:
                pass
        return None

    def get_query_data[T](self, key: QueryKey) -> T | None:
        """Memory-only data retrieval."""
        query: Query[object] | None = self._cache.get(hash_key(key))
        return cast(T, query.state.data) if query else None

    def set_query_data[T](self, key: QueryKey, data: T) -> None:
        """Manual cache injection. Triggers persistence to L2."""
        query: Query[object] | None = self._cache.get(hash_key(key))
        if query:
            query._dispatch(
                status=QueryStatus.SUCCESS,
                data=data,
                data_updated_at=time.time(),
            )

    def get_query_state[
        T, TError: Exception
    ](self, key: QueryKey) -> QueryState[T, TError] | None:
        query: Query[object] | None = self._cache.get(hash_key(key))
        return cast(QueryState[T, TError], query.state) if query else None

    async def invalidate_queries(
        self,
        filter_key: QueryKey | None = None,
        *,
        refetch: bool = True,
    ) -> None:
        """
        Marks matching queries as stale (data_updated_at=0).
        Active observers will trigger an immediate refetch.
        """
        queries = self._cache.find_all(filter_key)
        tasks: list[asyncio.Task[object]] = []

        for query in queries:
            query._dispatch(data_updated_at=0.0) # Mark stale in L1/L2
            if refetch and query.observer_count > 0:
                tasks.append(asyncio.create_task(query.fetch()))

        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    def remove_queries(self, filter_key: QueryKey | None = None) -> None:
        """Hard removal from L1 cache."""
        queries = self._cache.find_all(filter_key)
        for q in queries:
            self._cache.remove(q.key_hash)

    def reset_queries(self, filter_key: QueryKey | None = None) -> None:
        """Reverts queries to IDLE state."""
        queries = self._cache.find_all(filter_key)
        for q in queries:
            q._dispatch(
                status=QueryStatus.IDLE,
                fetch_status=FetchStatus.IDLE,
                data=None,
                error=None,
                data_updated_at=None,
                error_updated_at=None,
                fetch_failure_count=0,
                fetch_failure_reason=None,
            )

    def watch[T](self, options: QueryOptions[T]) -> QueryObserver[T]:
        """Creates a reactive observer for the given options."""
        return QueryObserver(client=self, options=options)

    def mutation[TInput, TData](
        self,
        options: MutationOptions[TInput, TData],
    ) -> Mutation[TInput, TData]:
        return Mutation(options=options, client=self)

    def clear(self) -> None:
        """Wipe memory cache."""
        self._cache.clear()


