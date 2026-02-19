"""
Query cache with LRU eviction.
"""

from __future__ import annotations

import logging
from collections import OrderedDict
from typing import TYPE_CHECKING, Any

from .helpers import partial_match
from .types import QueryKey

if TYPE_CHECKING:
    from .query import Query

logger = logging.getLogger("pystackquery")


class QueryCache:
    """
    In-memory cache for Query instances.

    Features:
        - O(1) lookup and insertion
        - LRU eviction when max_size is reached
        - Partial key matching for bulk invalidation

    Attributes:
        max_size: Maximum number of queries to cache.
    """

    __slots__ = ("_queries", "_max_size")

    def __init__(self, max_size: int = 1000) -> None:
        """
        Initialize the cache.

        Args:
            max_size: Maximum number of queries to store.
        """
        self._queries: OrderedDict[str, Query[Any]] = OrderedDict()
        self._max_size: int = max_size

    def get(self, key_hash: str) -> Query[Any] | None:
        """
        Get a query by its key hash.

        Moves the query to the end (most recently used).

        Args:
            key_hash: The hash of the query key.

        Returns:
            The Query if found, None otherwise.
        """
        if key_hash in self._queries:
            self._queries.move_to_end(key_hash)
            return self._queries[key_hash]
        return None

    def add(self, query: Query[Any]) -> None:
        """
        Add a query to the cache.

        Evicts the least recently used query if cache is full.

        Args:
            query: The Query to add.
        """
        if len(self._queries) >= self._max_size:
            _, evicted = self._queries.popitem(last=False)
            evicted.destroy()
            if logger.isEnabledFor(logging.DEBUG):
                logger.debug("LRU eviction: %s", evicted.key)

        self._queries[query.key_hash] = query

        # Wire up GC removal callback
        def gc_ready() -> None:
            self.remove(query.key_hash)

        query._notify_gc_ready = gc_ready

    def remove(self, key_hash: str) -> None:
        """
        Remove a query from the cache.

        Args:
            key_hash: The hash of the query key.
        """
        if key_hash in self._queries:
            query = self._queries.pop(key_hash)
            query.destroy()
            if logger.isEnabledFor(logging.DEBUG):
                logger.debug("Removed query %s from cache", query.key)

    def find_all(self, filter_key: QueryKey | None = None) -> list[Query[Any]]:
        """
        Find all queries matching the filter.

        Args:
            filter_key: If provided, only return queries where filter_key
                       is a prefix of the query key. If None, return all.

        Returns:
            List of matching queries.
        """
        if filter_key is None:
            return list(self._queries.values())
        return [q for q in self._queries.values() if partial_match(filter_key, q.key)]

    def clear(self) -> None:
        """Remove all queries from the cache."""
        for query in self._queries.values():
            query.destroy()
        self._queries.clear()

    def __len__(self) -> int:
        """Return the number of cached queries."""
        return len(self._queries)

    def __contains__(self, key_hash: str) -> bool:
        """Check if a query is in the cache."""
        return key_hash in self._queries
