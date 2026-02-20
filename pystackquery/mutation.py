"""
Mutation - handles side effects and state transitions for data-changing operations.
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Callable
from typing import TYPE_CHECKING, cast

from .options import MutationOptions
from .state import MutationState, MutationStatus

if TYPE_CHECKING:
    from .client import QueryClient


class Mutation[TInput, TData]:
    """
    State manager for POST/PUT/DELETE style operations.
    Supports optimistic updates via 'on_mutate' and automatic retries.
    """

    __slots__ = ("options", "_client", "_state", "_listeners")

    def __init__(
        self,
        options: MutationOptions[TInput, TData],
        client: QueryClient | None = None,
    ) -> None:
        self.options: MutationOptions[TInput, TData] = options
        self._client: QueryClient | None = client
        self._state: MutationState[TData, Exception] = MutationState()
        self._listeners: list[Callable[[MutationState[TData, Exception]], object]] = []

    @property
    def state(self) -> MutationState[TData, Exception]:
        return self._state

    def subscribe(
        self,
        listener: Callable[[MutationState[TData, Exception]], object],
    ) -> Callable[[], None]:
        self._listeners.append(listener)

        def unsubscribe() -> None:
            if listener in self._listeners:
                self._listeners.remove(listener)

        return unsubscribe

    def _dispatch(self, **updates: object) -> None:
        """Synchronously notify all listeners of state change."""
        current = self._state
        self._state = MutationState(
            status=cast(MutationStatus, updates.get("status", current.status)),
            data=cast(TData, updates.get("data", current.data)),
            error=cast(Exception, updates.get("error", current.error)),
            submitted_at=cast(float, updates.get("submitted_at", current.submitted_at)),
            settled_at=cast(float, updates.get("settled_at", current.settled_at)),
        )
        for listener in self._listeners:
            listener(self._state)

    async def mutate(self, input_data: TInput) -> TData:
        """
        Executes the mutation. Note that unlike Query, mutations are never
        automatically cached or persisted to L2.
        """
        self._dispatch(
            status=MutationStatus.PENDING,
            submitted_at=time.time(),
            error=None,
        )

        # Trigger optimistic update before actual execution
        if self.options.on_mutate:
            result = self.options.on_mutate(input_data)
            if asyncio.iscoroutine(result):
                await result

        last_error: Exception | None = None

        for attempt in range(self.options.retry + 1):
            try:
                data = await self.options.mutation_fn(input_data)

                self._dispatch(
                    status=MutationStatus.SUCCESS,
                    data=data,
                    error=None,
                    settled_at=time.time(),
                )

                if self.options.on_success:
                    self.options.on_success(data, input_data)
                if self.options.on_settled:
                    self.options.on_settled(data, None, input_data)

                return data

            except Exception as e:
                last_error = e
                if attempt < self.options.retry:
                    await asyncio.sleep(self.options.retry_delay(attempt))

        assert last_error is not None
        self._dispatch(
            status=MutationStatus.ERROR,
            error=last_error,
            settled_at=time.time(),
        )

        if self.options.on_error:
            self.options.on_error(last_error, input_data)
        if self.options.on_settled:
            self.options.on_settled(None, last_error, input_data)

        raise last_error

    def reset(self) -> None:
        """Resets state to IDLE."""
        self._state = MutationState()
