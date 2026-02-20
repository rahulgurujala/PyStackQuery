import asyncio

import pytest

from pystackquery import Query, QueryOptions


@pytest.mark.asyncio
async def test_query_lifecycle() -> None:
    """Test query lifecycle states."""
    async def fetcher() -> str:
        await asyncio.sleep(0.05)
        return "result"

    opts = QueryOptions(("lifecycle",), fetcher)
    query = Query(opts)

    assert query.state.is_idle
    assert not query.state.is_fetching

    task = asyncio.create_task(query.fetch())

    # Allow task to start and update state
    await asyncio.sleep(0.01)

    assert query.state.is_pending
    assert query.state.is_fetching

    result = await task

    assert result == "result"
    assert query.state.is_success
    assert not query.state.is_fetching
    assert query.state.data == "result"

@pytest.mark.asyncio
async def test_query_retry() -> None:
    """Test query retry logic."""
    attempts = 0
    async def failing_fetcher() -> str:
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            raise ValueError("Fail")
        return "success"

    opts = QueryOptions(
        ("retry",),
        failing_fetcher,
        retry=3,
        retry_delay=lambda _: 0.01
    )
    query = Query(opts)

    result = await query.fetch()

    assert result == "success"
    assert attempts == 3
    assert query.state.is_success
    assert query.state.fetch_failure_count == 0  # Resets on success

@pytest.mark.asyncio
async def test_query_pause_resume() -> None:
    """Test pausing and resuming queries."""
    async def fetcher() -> str:
        return "data"

    query = Query(QueryOptions(("pause",), fetcher, refetch_interval=0.1))

    query.pause()
    assert query.is_paused

    query.resume(refetch=False)
    assert not query.is_paused
