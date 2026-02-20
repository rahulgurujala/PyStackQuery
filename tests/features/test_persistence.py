from __future__ import annotations

import asyncio
import json
import time
from typing import Any

import pytest

from pystackquery import QueryClient, QueryOptions


@pytest.mark.asyncio
async def test_persistence_hydration(
    persistent_client: QueryClient,
    mock_storage: Any,
) -> None:
    """Test rehydrating state from L2 storage."""
    # Pre-populate storage with an old timestamp (relative to time.time())
    state_dict = {
        "status": "SUCCESS",
        "fetch_status": "IDLE",
        "data": "persisted_data",
        "data_updated_at": time.time() - 1000.0, # 1000 seconds ago
        "error": None,
        "error_updated_at": None,
        "fetch_failure_count": 0,
        "fetch_failure_reason": None
    }
    await mock_storage.set("('persist',)", json.dumps(state_dict))

    async def fetcher() -> str:
        return "new_data"

    # stale_time=0 -> returns stale persisted data, triggers refetch
    opts = QueryOptions(("persist",), fetcher, stale_time=0.0)

    data = await persistent_client.fetch_query(opts)
    assert data == "persisted_data"

    # Allow background refetch to happen
    await asyncio.sleep(0.2)

    # Should now be updated in memory
    assert persistent_client.get_query_data(("persist",)) == "new_data"

@pytest.mark.asyncio
async def test_persistence_write(
    persistent_client: QueryClient,
    mock_storage: Any,
) -> None:
    """Test that successful fetches write to L2."""
    async def fetcher() -> str:
        return "fresh_write"

    opts = QueryOptions(("write",), fetcher)

    await persistent_client.fetch_query(opts)
    await asyncio.sleep(0.1) # Allow background persistence

    # Check storage
    raw = await mock_storage.get("('write',)")
    assert raw is not None
    data = json.loads(raw)
    assert data["data"] == "fresh_write"
    assert data["status"] == "SUCCESS"

@pytest.mark.asyncio
async def test_persistence_invalidation(
    persistent_client: QueryClient,
    mock_storage: Any,
) -> None:
    """Test that invalidation updates L2 with stale timestamp."""
    async def fetcher() -> str:
        return "val"

    # Populate
    await persistent_client.fetch_query(QueryOptions(("del",), fetcher))
    await asyncio.sleep(0.1)

    # Invalidate
    await persistent_client.invalidate_queries(("del",))
    await asyncio.sleep(0.1) # Allow background persistence

    val_after = await mock_storage.get("('del',)")
    assert val_after is not None

    # Verify it is marked as stale (timestamp 0.0)
    data = json.loads(val_after)
    assert data["data_updated_at"] == 0.0
