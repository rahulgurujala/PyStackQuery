"""
Query observer for reactive state updates.
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Callable, Generic

from .options import QueryOptions
from .state import QueryState
from .types import T

if TYPE_CHECKING:
    from .client import QueryClient
    from .query import Query

logger = logging.getLogger("pystackquery")


class QueryObserver(Generic[T]):
    """
    Subscribes to a Query and receives state updates.

    This is the reactive way to consume query data. Subscribe to receive
    notifications whenever the query state changes.

    Example:
        observer = client.watch(QueryOptions(("users",), fetch_users))
        unsubscribe = observer.subscribe(lambda state: print(state.data))
        # ... later
        unsubscribe()
    """

    __slots__ = (
        "_client",
        "_options",
        "_query",
        "_listeners",
        "_current_result",
        "__weakref__",
    )

    def __init__(
        self,
        client: QueryClient,
        options: QueryOptions[T],
    ) -> None:
        """
        Initialize an observer.

        Args:
            client: The QueryClient that created this observer.
            options: Query configuration.
        """
        self._client: QueryClient = client
        self._options: QueryOptions[T] = options
        self._query: Query[T] | None = None
        self._listeners: list[Callable[[QueryState[T]], None]] = []
        self._current_result: QueryState[T] = QueryState()

    @property
    def result(self) -> QueryState[T]:
        """
        Current query state with select transform applied.

        Returns:
            The current QueryState, transformed if select is configured.
        """
        state = self._current_result
        if self._options.select and state.data is not None:
            try:
                transformed = self._options.select(state.data)
                return QueryState(
                    status=state.status,
                    fetch_status=state.fetch_status,
                    data=transformed,
                    error=state.error,
                    data_updated_at=state.data_updated_at,
                    error_updated_at=state.error_updated_at,
                    fetch_failure_count=state.fetch_failure_count,
                    fetch_failure_reason=state.fetch_failure_reason,
                )
            except Exception:
                return state
        return state

    def subscribe(
        self,
        listener: Callable[[QueryState[T]], None],
    ) -> Callable[[], None]:
        """
        Subscribe to state changes.

        The listener will be called immediately with the current state,
        and again whenever the state changes.

        Args:
            listener: Callback to invoke on state changes.

        Returns:
            Unsubscribe function.
        """
        self._listeners.append(listener)

        if self._query is None:
            self._query = self._client._get_or_create_query(self._options)
            self._query.add_observer(self)
            self._current_result = self._query.state

            if self._options.enabled and self._query.is_stale():
                asyncio.create_task(self._query.fetch())

            self._query.start_refetch_interval()

        def unsubscribe() -> None:
            self._listeners.remove(listener)
            if not self._listeners and self._query is not None:
                self._query.remove_observer(self)

        return unsubscribe

    def _on_query_update(self, state: QueryState[T]) -> None:
        """
        Handle state update from query.

        Args:
            state: The new query state.
        """
        self._current_result = state
        for listener in self._listeners:
            try:
                listener(self.result)
            except Exception as e:
                logger.error("Observer listener error: %s", e)

    async def refetch(self) -> QueryState[T]:
        """
        Force a refetch regardless of stale state.

        Returns:
            The updated QueryState after refetch.
        """
        if self._query is not None:
            await self._query.fetch()
        return self.result
