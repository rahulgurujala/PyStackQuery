"""
QueryClient - the main entry point for PyStackQuery.
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Any

from .cache import QueryCache
from .helpers import default_retry_delay, hash_key
from .mutation import Mutation
from .observer import QueryObserver
from .options import MutationOptions, QueryOptions
from .query import Query
from .state import FetchStatus, QueryState, QueryStatus
from .types import QueryKey, RetryDelayFn, T, TData, TInput

logger = logging.getLogger("pystackquery")


@dataclass
class QueryClientConfig:
    """
    Global defaults for all queries managed by a QueryClient.

    Attributes:
        stale_time: Default seconds before data is stale (default: 0).
        gc_time: Default seconds before inactive query is collected (default: 300).
        retry: Default retry attempts (default: 3).
        retry_delay: Default retry delay function.
        cache_max_size: Maximum queries to cache (default: 1000).
    """

    stale_time: float = 0.0
    gc_time: float = 300.0
    retry: int = 3
    retry_delay: RetryDelayFn = field(default_factory=lambda: default_retry_delay)
    cache_max_size: int = 1000


class QueryClient:
    """
    Central orchestrator for queries and mutations.

    Manages the query cache and provides the primary API for:
        - Fetching and caching data
        - Invalidating stale data
        - Creating mutations

    Example:
        client = QueryClient()
        data = await client.fetch_query(
            QueryOptions(query_key=("users",), query_fn=fetch_users)
        )
    """

    __slots__ = ("_config", "_cache")

    def __init__(self, config: QueryClientConfig | None = None) -> None:
        """
        Initialize a QueryClient.

        Args:
            config: Optional configuration with default values.
        """
        self._config: QueryClientConfig = config or QueryClientConfig()
        self._cache: QueryCache = QueryCache(max_size=self._config.cache_max_size)

    @property
    def cache(self) -> QueryCache:
        """The underlying query cache."""
        return self._cache

    def _get_or_create_query(self, options: QueryOptions[T]) -> Query[T]:
        """
        Get existing query from cache or create a new one.

        Args:
            options: Query configuration.

        Returns:
            The Query instance.
        """
        key_hash = options.get_key_hash()
        existing = self._cache.get(key_hash)
        if existing is not None:
            return existing

        # Apply client-level defaults
        if options.stale_time == 0.0 and self._config.stale_time != 0.0:
            options.stale_time = self._config.stale_time
        if options.gc_time == 300.0 and self._config.gc_time != 300.0:
            options.gc_time = self._config.gc_time
        if options.retry == 3 and self._config.retry != 3:
            options.retry = self._config.retry

        query: Query[T] = Query(options)
        self._cache.add(query)
        return query

    async def fetch_query(self, options: QueryOptions[T]) -> T:
        """
        Fetch query data with automatic caching.

        - If cached and fresh, returns immediately
        - If cached but stale, returns stale data and refetches in background
        - If not cached, fetches and caches

        Args:
            options: Query configuration.

        Returns:
            The query data.
        """
        query = self._get_or_create_query(options)

        # Fresh data available
        if query.state.data is not None and not query.is_stale():
            if logger.isEnabledFor(logging.DEBUG):
                logger.debug("Cache HIT (fresh) for %s", options.query_key)
            return query.state.data

        # Stale data available - return it, refetch in background
        if query.state.data is not None and query.is_stale():
            if logger.isEnabledFor(logging.DEBUG):
                logger.debug("Cache HIT (stale) for %s, bg refetch", options.query_key)
            asyncio.create_task(query.fetch())
            return query.state.data

        # No data - must fetch
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug("Cache MISS for %s", options.query_key)
        return await query.fetch()

    async def prefetch_query(self, options: QueryOptions[T]) -> None:
        """
        Prefetch and cache data without returning it.

        Useful for anticipating user navigation.

        Args:
            options: Query configuration.
        """
        query = self._get_or_create_query(options)
        if query.state.data is None or query.is_stale():
            try:
                await query.fetch()
            except Exception:
                pass  # Prefetch failures are silent

    def get_query_data(self, key: QueryKey) -> Any | None:
        """
        Get cached data for a query key.

        Args:
            key: The query key.

        Returns:
            Cached data or None.
        """
        query = self._cache.get(hash_key(key))
        return query.state.data if query else None

    def set_query_data(self, key: QueryKey, data: Any) -> None:
        """
        Manually update cached data for a query key.

        Args:
            key: The query key.
            data: The data to cache.
        """
        query = self._cache.get(hash_key(key))
        if query:
            query._dispatch(
                status=QueryStatus.SUCCESS,
                data=data,
                data_updated_at=time.monotonic(),
            )

    def get_query_state(self, key: QueryKey) -> QueryState[Any] | None:
        """
        Get the full state for a query key.

        Args:
            key: The query key.

        Returns:
            QueryState or None if not cached.
        """
        query = self._cache.get(hash_key(key))
        return query.state if query else None

    async def invalidate_queries(
        self,
        filter_key: QueryKey | None = None,
        *,
        refetch: bool = True,
    ) -> None:
        """
        Invalidate queries matching the filter key.

        Uses partial matching - invalidating ("users",) will also
        invalidate ("users", "123").

        Args:
            filter_key: Partial key to match. None invalidates all.
            refetch: Whether to refetch active queries (default: True).
        """
        queries = self._cache.find_all(filter_key)
        tasks: list[asyncio.Task[Any]] = []

        for query in queries:
            query._dispatch(data_updated_at=0.0)
            if refetch and query.observer_count > 0:
                tasks.append(asyncio.create_task(query.fetch()))

        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

        if logger.isEnabledFor(logging.DEBUG):
            logger.debug("Invalidated %d queries matching %s", len(queries), filter_key)

    def remove_queries(self, filter_key: QueryKey | None = None) -> None:
        """
        Remove queries from cache entirely.

        Args:
            filter_key: Partial key to match. None removes all.
        """
        queries = self._cache.find_all(filter_key)
        for q in queries:
            self._cache.remove(q.key_hash)

    def reset_queries(self, filter_key: QueryKey | None = None) -> None:
        """
        Reset queries to their initial state.

        Args:
            filter_key: Partial key to match. None resets all.
        """
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

    def watch(self, options: QueryOptions[T]) -> QueryObserver[T]:
        """
        Create an observer for reactive state updates.

        Args:
            options: Query configuration.

        Returns:
            QueryObserver to subscribe to.
        """
        return QueryObserver(client=self, options=options)

    def mutation(
        self,
        options: MutationOptions[TInput, TData],
    ) -> Mutation[TInput, TData]:
        """
        Create a mutation instance.

        Args:
            options: Mutation configuration.

        Returns:
            Mutation instance.
        """
        return Mutation(options=options, client=self)

    def clear(self) -> None:
        """Clear the entire cache and destroy all queries."""
        self._cache.clear()
