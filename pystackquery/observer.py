"""
QueryObserver - Reactive interface for subscribing to query state changes.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from typing import TYPE_CHECKING, cast

from .options import QueryOptions
from .state import QueryState

if TYPE_CHECKING:
    from .client import QueryClient
    from .query import Query

logger = logging.getLogger("pystackquery")


class QueryObserver[T]:
    """
    Handles the binding between a QueryClient and a specific listener.
    Supports data selection/transformation at the subscription level.
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
        self._client: QueryClient = client
        self._options: QueryOptions[T] = options
        self._query: Query[T] | None = None
        self._listeners: list[Callable[[QueryState[T, Exception]], object]] = []
        self._current_result: QueryState[T, Exception] = QueryState()

    @property
    def result(self) -> QueryState[T, Exception]:
        """
        Returns the current state. If a 'select' transform is defined in options,
        it is applied to the data before returning.
        """
        state = self._current_result
        if self._options.select and state.data is not None:
            try:
                transformed = cast(T, self._options.select(state.data))
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
            except Exception as e:
                logger.error("Select transform failed: %s", e)
                return state
        return state

    @property
    def options(self) -> QueryOptions[T]:
        """Get the query options."""
        return self._options

    def subscribe(
        self,
        listener: Callable[[QueryState[T, Exception]], object],
    ) -> Callable[[], None]:
        """
        Registers a callback. The listener is invoked immediately with the
        current state (from memory or placeholder).

        Example:
            observer = client.watch(opts)
            unsub = observer.subscribe(lambda state: handle_update(state))
        """
        self._listeners.append(listener)

        if self._query is None:
            # First subscriber connects the observer to the actual Query engine
            self._query = self._client._get_or_create_query(self._options)
            self._query.add_observer(self)
            self._current_result = self._query.state

            # Trigger initial fetch if enabled and stale
            if self._options.enabled and self._query.is_stale():
                asyncio.create_task(self._query.fetch())

            self._query.start_refetch_interval()

        # Immediate sync push
        listener(self.result)

        def unsubscribe() -> None:
            if listener in self._listeners:
                self._listeners.remove(listener)
            if not self._listeners and self._query is not None:
                self._query.remove_observer(self)

        return unsubscribe

    def _on_query_update(self, state: QueryState[T, Exception]) -> None:
        """Internal callback triggered by the Query instance."""
        self._current_result = state
        for listener in self._listeners:
            try:
                listener(self.result)
            except Exception as e:
                logger.error("Observer listener error: %s", e)

    async def refetch(self) -> QueryState[T, Exception]:
        """Force an immediate network fetch regardless of staleness."""
        if self._query is not None:
            await self._query.fetch()
        return self.result
