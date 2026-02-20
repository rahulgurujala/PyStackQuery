from __future__ import annotations

import pytest

from pystackquery import MutationOptions, QueryClient


@pytest.mark.asyncio
async def test_mutation_success(client: QueryClient) -> None:
    """Test successful mutation."""
    success_called = False

    async def mutator(data: dict[str, int]) -> int:
        return data["val"] * 2

    def on_success(data: int, inp: dict[str, int]) -> None:
        nonlocal success_called
        success_called = True
        assert data == 4
        assert inp["val"] == 2

    mutation = client.mutation(MutationOptions(
        mutation_fn=mutator,
        on_success=on_success
    ))

    result = await mutation.mutate({"val": 2})
    assert result == 4
    assert success_called

@pytest.mark.asyncio
async def test_mutation_optimistic(client: QueryClient) -> None:
    """Test optimistic updates via on_mutate."""
    on_mutate_called = False

    def on_mutate(inp: str) -> None:
        nonlocal on_mutate_called
        on_mutate_called = True

    async def identity(x: str) -> str:
        return x

    mutation = client.mutation(MutationOptions(
        mutation_fn=identity,
        on_mutate=on_mutate
    ))

    await mutation.mutate("test")
    assert on_mutate_called

@pytest.mark.asyncio
async def test_mutation_retry(client: QueryClient) -> None:
    """Test mutation retries."""
    attempts = 0

    async def flaky_mutator(x: str) -> str:
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            raise ValueError("Fail")
        return "success"

    mutation = client.mutation(MutationOptions(
        mutation_fn=flaky_mutator,
        retry=3,
        retry_delay=lambda _: 0.01
    ))

    res = await mutation.mutate("go")
    assert res == "success"
    assert attempts == 3
