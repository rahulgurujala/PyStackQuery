from __future__ import annotations

import asyncio

import pytest

from pystackquery import QueryClient, QueryOptions, QueryState


@pytest.mark.asyncio
async def test_observer_basic(client: QueryClient) -> None:
    """Test observer subscription and updates."""
    updates: list[str] = []

    async def fetcher() -> str:
        return "hello"

    opts = QueryOptions(("obs",), fetcher)
    observer = client.watch(opts)

    def listener(state: QueryState[str, Exception]) -> None:
        updates.append(state.status.name)

    unsub = observer.subscribe(listener)

    # Wait for fetch
    await asyncio.sleep(0.1)

    unsub()

    assert "SUCCESS" in updates
    assert observer.result.data == "hello"

@pytest.mark.asyncio
async def test_observer_refetch_interval(client: QueryClient) -> None:
    """Test automatic refetching."""
    count = 0
    async def fetcher() -> int:
        nonlocal count
        count += 1
        return count

    # Refetch every 0.1s
    opts = QueryOptions(("interval",), fetcher, refetch_interval=0.1)
    observer = client.watch(opts)

    data_updates: list[int] = []
    unsub = observer.subscribe(
        lambda s: data_updates.append(s.data) if s.data is not None else None
    )

    await asyncio.sleep(0.35)
    unsub()

    # Should have initial fetch + at least 2 refetches
    assert len(data_updates) >= 3
    assert data_updates[-1] >= 3

@pytest.mark.asyncio
async def test_observer_multiple_subscribers(client: QueryClient) -> None:
    """Test multiple observers on same query."""
    call_count = 0
    async def fetcher() -> str:
        nonlocal call_count
        call_count += 1
        await asyncio.sleep(0.05)
        return "shared"

    opts = QueryOptions(("shared",), fetcher)

    obs1 = client.watch(opts)
    obs2 = client.watch(opts)

    res1: list[str | None] = []
    res2: list[str | None] = []

    obs1.subscribe(lambda s: res1.append(s.data))
    obs2.subscribe(lambda s: res2.append(s.data))

    await asyncio.sleep(0.1)

    assert "shared" in res1
    assert "shared" in res2
    assert call_count == 1  # Deduplicated
