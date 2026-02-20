from __future__ import annotations

import asyncio

import pytest

from pystackquery import QueryClient, QueryOptions, QueryState


@pytest.mark.asyncio
async def test_fetch_query_basic(client: QueryClient) -> None:
    """Test basic fetching and caching."""
    count = 0
    async def fetcher() -> str:
        nonlocal count
        count += 1
        return "data"

    opts = QueryOptions(("test",), fetcher)

    # First fetch
    data1 = await client.fetch_query(opts)
    assert data1 == "data"
    assert count == 1

    # Second fetch (cached)
    data2 = await client.fetch_query(opts)
    assert data2 == "data"
    assert count == 1  # Should not increment

@pytest.mark.asyncio
async def test_stale_while_revalidate(client: QueryClient) -> None:
    """Test stale-while-revalidate behavior."""
    count = 0
    async def fetcher() -> str:
        nonlocal count
        count += 1
        return f"data_{count}"

    # Stale time 0 means immediately stale
    opts = QueryOptions(("swr",), fetcher, stale_time=0.0)

    # 1. Initial fetch
    res1 = await client.fetch_query(opts)
    assert res1 == "data_1"

    # 2. Second fetch - returns stale data_1 immediately, triggers bg refetch
    res2 = await client.fetch_query(opts)
    assert res2 == "data_1"

    # Allow background task to complete
    await asyncio.sleep(0.1)

    # 3. Third fetch - should have fresh data_2
    state: QueryState[str, Exception] | None = client.get_query_state(("swr",))
    assert state is not None
    assert state.data == "data_2"

@pytest.mark.asyncio
async def test_deduplication(client: QueryClient) -> None:
    """Test request deduplication."""
    count = 0
    async def slow_fetcher() -> str:
        nonlocal count
        count += 1
        await asyncio.sleep(0.1)
        return "done"

    opts = QueryOptions(("dedup",), slow_fetcher)

    # Fire multiple requests
    results: list[str] = list(await asyncio.gather(
        client.fetch_query(opts),
        client.fetch_query(opts),
        client.fetch_query(opts)
    ))

    assert results == ["done", "done", "done"]
    assert count == 1  # Only one actual fetch

@pytest.mark.asyncio
async def test_invalidation(client: QueryClient) -> None:
    """Test query invalidation."""
    async def fetcher() -> str:
        return "alice"

    opts = QueryOptions(("users", "1"), fetcher)
    await client.fetch_query(opts)

    assert client.get_query_data(("users", "1")) == "alice"

    # Invalidate
    await client.invalidate_queries(("users",))

    # Data remains until refetched or GC, but marked stale
    state: QueryState[str, Exception] | None = client.get_query_state(("users", "1"))
    assert state is not None
    assert state.data_updated_at == 0.0  # Invalidated timestamp
