"""
PyStackQuery - Async data fetching and caching library for Python.

A powerful library for managing server state in Python applications:
    - Automatic caching with configurable staleness
    - Request deduplication
    - Automatic retry with exponential backoff
    - Reactive state updates via observers
    - Partial key invalidation
    - Mutations with lifecycle callbacks

Example:
    from pystackquery import QueryClient, QueryOptions

    client = QueryClient()

    # Fetch with automatic caching
    users = await client.fetch_query(
        QueryOptions(query_key=("users",), query_fn=fetch_users)
    )

    # Reactive updates
    observer = client.watch(
        QueryOptions(query_key=("users",), query_fn=fetch_users)
    )
    unsubscribe = observer.subscribe(lambda state: print(state.data))
"""

from .cache import QueryCache
from .client import QueryClient, QueryClientConfig
from .convenience import CachedQuery, dependent_query, parallel_queries, query
from .helpers import default_retry_delay, hash_key, partial_match
from .mutation import Mutation
from .observer import QueryObserver
from .options import MutationOptions, QueryOptions
from .query import Query
from .state import (
    FetchStatus,
    MutationState,
    MutationStatus,
    QueryState,
    QueryStatus,
)
from .types import QueryKey

__version__ = "1.0.0"

__all__ = [
    # Client
    "QueryClient",
    "QueryClientConfig",
    # Query
    "Query",
    "QueryOptions",
    "QueryObserver",
    "QueryState",
    "QueryStatus",
    "FetchStatus",
    # Mutation
    "Mutation",
    "MutationOptions",
    "MutationState",
    "MutationStatus",
    # Cache
    "QueryCache",
    # Types
    "QueryKey",
    # Helpers
    "hash_key",
    "partial_match",
    "default_retry_delay",
    # Convenience
    "parallel_queries",
    "dependent_query",
    "query",
    "CachedQuery",
]
