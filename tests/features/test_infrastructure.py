from __future__ import annotations

import asyncio
from typing import Any

import pytest

from pystackquery import QueryClient, QueryClientConfig, QueryOptions

# ─────────────────────────────────────────────────────────────
# 1. FakeRedis Persistence Test
# ─────────────────────────────────────────────────────────────

class RedisStorage:
    """Internal adapter for testing."""
    def __init__(self, redis: Any) -> None:
        self.redis = redis
    async def get(self, key: str) -> str | None:
        val = await self.redis.get(key)
        return str(val) if val is not None else None
    async def set(self, key: str, value: str, ttl: float | None = None) -> None:
        await self.redis.set(key, value, ex=int(ttl) if ttl else None)
    async def delete(self, key: str) -> None:
        await self.redis.delete(key)

@pytest.mark.asyncio
async def test_redis_persistence_logic() -> None:
    """Prove that data persists through a fake Redis protocol."""
    fakeredis = pytest.importorskip("fakeredis")

    # Use FakeAsyncRedis for asyncio compatibility
    redis = fakeredis.FakeAsyncRedis(decode_responses=True)
    storage = RedisStorage(redis)

    # 1. First Client: Fetch and Save
    client1 = QueryClient(QueryClientConfig(storage=storage, stale_time=100))
    async def fetcher1() -> str:
        await asyncio.sleep(0)
        return "val"

    await client1.fetch_query(QueryOptions(("key",), fetcher1))
    await asyncio.sleep(0.1) # Background L2 sync

    # Verify data is actually IN redis
    raw = await redis.get("('key',)")
    assert raw is not None
    assert "val" in raw

    # 2. Second Client: Hydrate from same Redis
    client2 = QueryClient(QueryClientConfig(storage=storage, stale_time=100))
    async def fetcher2() -> str:
        return "NETWORK_FAIL"

    # This should load from redis immediately
    data = await client2.fetch_query(QueryOptions(("key",), fetcher2))
    assert data == "val" # Proves it didn't call the fallback lambda

# ─────────────────────────────────────────────────────────────
# 2. SQLite In-Memory Persistence Test
# ─────────────────────────────────────────────────────────────

class SQLiteStorage:
    """Internal adapter for testing using in-memory SQLite."""
    def __init__(self, db: Any) -> None:
        self.db = db
    async def get(self, key: str) -> str | None:
        async with self.db.execute("SELECT val FROM cache WHERE key=?", (key,)) as cur:
            row = await cur.fetchone()
            return str(row[0]) if row else None
    async def set(self, key: str, value: str, ttl: float | None = None) -> None:
        await self.db.execute("INSERT OR REPLACE INTO cache VALUES (?,?)", (key, value))
        await self.db.commit()
    async def delete(self, key: str) -> None:
        await self.db.execute("DELETE FROM cache WHERE key=?", (key,))
        await self.db.commit()

@pytest.mark.asyncio
async def test_sqlite_persistence_logic() -> None:
    """Prove that data persists through a real SQLite connection."""
    aiosqlite = pytest.importorskip("aiosqlite")

    async with aiosqlite.connect(":memory:") as db:
        await db.execute("CREATE TABLE cache (key TEXT PRIMARY KEY, val TEXT)")
        storage = SQLiteStorage(db)

        client1 = QueryClient(QueryClientConfig(storage=storage, stale_time=100))
        async def fetcher3() -> str:
            await asyncio.sleep(0)
            return "sql_data"

        await client1.fetch_query(
            QueryOptions(("db",), fetcher3)
        )
        await asyncio.sleep(0.1)

        # New client instance
        client2 = QueryClient(QueryClientConfig(storage=storage, stale_time=100))
        async def fetcher4() -> str:
            return "REFETCHED"

        res = await client2.fetch_query(QueryOptions(("db",), fetcher4))

        assert res == "sql_data" # Proves L2 hydration worked
