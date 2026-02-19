"""
Convenience functions and decorators for common patterns.
"""

from __future__ import annotations

import asyncio
from typing import Any, Awaitable, Callable, Generic

from .client import QueryClient
from .options import QueryOptions
from .types import QueryKey, T


async def parallel_queries(
    client: QueryClient,
    *options_list: QueryOptions[Any],
) -> list[Any]:
    """
    Execute multiple queries in parallel.

    All queries are fetched concurrently, and results are returned
    in the same order as the options.

    Args:
        client: The QueryClient to use.
        *options_list: Query configurations to execute.

    Returns:
        List of results in the same order as inputs.

    Example:
        user, posts, stats = await parallel_queries(
            client,
            QueryOptions(("user", uid), get_user),
            QueryOptions(("posts", uid), get_posts),
            QueryOptions(("stats", uid), get_stats),
        )
    """
    return await asyncio.gather(*(client.fetch_query(opts) for opts in options_list))


async def dependent_query(
    client: QueryClient,
    depends_on: QueryOptions[T],
    then: Callable[[T], QueryOptions[Any]],
) -> Any:
    """
    Execute a query that depends on the result of another query.

    First fetches the parent query, then uses its result to construct
    and fetch the child query.

    Args:
        client: The QueryClient to use.
        depends_on: The parent query to fetch first.
        then: Function that takes parent data and returns child options.

    Returns:
        The child query result.

    Example:
        posts = await dependent_query(
            client,
            depends_on=QueryOptions(("user", uid), get_user),
            then=lambda user: QueryOptions(
                ("posts", user.id),
                lambda: get_posts(user.id)
            ),
        )
    """
    parent_data = await client.fetch_query(depends_on)
    child_options = then(parent_data)
    return await client.fetch_query(child_options)


class CachedQuery(Generic[T]):
    """
    A cached query wrapper that provides caching utilities.

    Created by the @query decorator.
    """

    __slots__ = ("_client", "_options")

    _client: QueryClient
    _options: QueryOptions[T]

    def __init__(
        self,
        client: QueryClient,
        options: QueryOptions[T],
    ) -> None:
        self._client = client
        self._options = options

    async def __call__(self) -> T:
        """Execute the cached query."""
        return await self._client.fetch_query(self._options)

    async def invalidate(self) -> None:
        """Invalidate the cache for this query."""
        await self._client.invalidate_queries(self._options.query_key)

    def get_data(self) -> T | None:
        """Get the currently cached data."""
        return self._client.get_query_data(self._options.query_key)

    @property
    def options(self) -> QueryOptions[T]:
        """Get the query options."""
        return self._options


def query(
    client: QueryClient,
    key: QueryKey,
    *,
    stale_time: float = 0.0,
    gc_time: float = 300.0,
    retry: int = 3,
) -> Callable[[Callable[[], Awaitable[T]]], CachedQuery[T]]:
    """
    Decorator that wraps an async function with caching.

    Provides a simple way to add caching to existing async functions.

    Args:
        client: The QueryClient to use.
        key: The query key for caching.
        stale_time: Seconds before data is stale (default: 0).
        gc_time: Seconds before cache entry is collected (default: 300).
        retry: Retry attempts on failure (default: 3).

    Returns:
        Decorator function.

    Example:
        @query(client, ("users",), stale_time=60)
        async def get_users():
            return await http_get("/api/users")

        # Now calling get_users() goes through the cache
        users = await get_users()

        # Access utilities
        await get_users.invalidate()  # Invalidate cache
        get_users.get_data()          # Get cached data
    """

    def decorator(fn: Callable[[], Awaitable[T]]) -> CachedQuery[T]:
        options = QueryOptions(
            query_key=key,
            query_fn=fn,
            stale_time=stale_time,
            gc_time=gc_time,
            retry=retry,
        )
        return CachedQuery(client, options)

    return decorator
