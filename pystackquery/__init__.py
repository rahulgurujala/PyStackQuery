"""
PyStackQuery - Async state management and caching for Python.

Inspired by TanStack Query, this library provides a robust L1/L2 caching
architecture designed for async Python applications (FastAPI, CLI, GUI).

Core Features:
    - SWR (Stale-While-Revalidate) caching logic
    - Background L2 hydration (Redis, SQLite, etc.)
    - Request deduplication and exponential backoff retries
    - Reactive state observers with synchronous subscription
    - Mutations with optimistic update support

Example:
    from pystackquery import QueryClient, QueryOptions

    client = QueryClient()

    # Create a reactive observer
    observer = client.watch(
        QueryOptions(query_key=("users",), query_fn=fetch_users)
    )

    # Subscribe is synchronous
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
from .types import QueryKey, StorageBackend

__version__ = "1.0.1"

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
    "StorageBackend",
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
