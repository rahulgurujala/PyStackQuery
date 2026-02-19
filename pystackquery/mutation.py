"""
Mutation class for handling side effects.
"""

from __future__ import annotations

import asyncio
import time
from typing import TYPE_CHECKING, Any, Callable, Generic

from .options import MutationOptions
from .state import MutationState, MutationStatus
from .types import TData, TInput

if TYPE_CHECKING:
    from .client import QueryClient


class Mutation(Generic[TInput, TData]):
    """
    Handles side effects (POST, PUT, DELETE, etc.) with lifecycle callbacks.

    Features:
        - Lifecycle callbacks (onSuccess, onError, onSettled)
        - Optimistic updates via onMutate
        - Automatic retry with exponential backoff
        - State tracking

    Example:
        mutation = client.mutation(MutationOptions(
            mutation_fn=create_user,
            on_success=lambda data, inp: print(f"Created {data.id}"),
        ))
        result = await mutation.mutate({"name": "John"})
    """

    __slots__ = ("options", "_client", "_state", "_listeners")

    def __init__(
        self,
        options: MutationOptions[TInput, TData],
        client: QueryClient | None = None,
    ) -> None:
        """
        Initialize a mutation.

        Args:
            options: Mutation configuration.
            client: Optional QueryClient reference.
        """
        self.options: MutationOptions[TInput, TData] = options
        self._client: QueryClient | None = client
        self._state: MutationState[TData] = MutationState()
        self._listeners: list[Callable[[MutationState[TData]], None]] = []

    @property
    def state(self) -> MutationState[TData]:
        """Current mutation state."""
        return self._state

    def subscribe(
        self,
        listener: Callable[[MutationState[TData]], None],
    ) -> Callable[[], None]:
        """
        Subscribe to state changes.

        Args:
            listener: Callback to invoke on state changes.

        Returns:
            Unsubscribe function.
        """
        self._listeners.append(listener)

        def unsubscribe() -> None:
            self._listeners.remove(listener)

        return unsubscribe

    def _dispatch(self, **updates: Any) -> None:
        """Update state and notify listeners."""
        current = self._state
        self._state = MutationState(
            status=updates.get("status", current.status),
            data=updates.get("data", current.data),
            error=updates.get("error", current.error),
            submitted_at=updates.get("submitted_at", current.submitted_at),
            settled_at=updates.get("settled_at", current.settled_at),
        )
        for listener in self._listeners:
            listener(self._state)

    async def mutate(self, input_data: TInput) -> TData:
        """
        Execute the mutation.

        Args:
            input_data: Input to pass to the mutation function.

        Returns:
            The mutation result.

        Raises:
            Exception: If all retry attempts fail.
        """
        self._dispatch(
            status=MutationStatus.PENDING,
            submitted_at=time.monotonic(),
            error=None,
        )

        # Optimistic update callback
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
                    settled_at=time.monotonic(),
                )

                if self.options.on_success:
                    self.options.on_success(data, input_data)
                if self.options.on_settled:
                    self.options.on_settled(data, None, input_data)

                return data

            except Exception as e:
                last_error = e
                if attempt < self.options.retry:
                    delay = self.options.retry_delay(attempt)
                    await asyncio.sleep(delay)

        assert last_error is not None
        self._dispatch(
            status=MutationStatus.ERROR,
            error=last_error,
            settled_at=time.monotonic(),
        )

        if self.options.on_error:
            self.options.on_error(last_error, input_data)
        if self.options.on_settled:
            self.options.on_settled(None, last_error, input_data)

        raise last_error

    def reset(self) -> None:
        """Reset mutation to idle state."""
        self._state = MutationState()
