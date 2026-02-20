"""
Redis Persistence Integration Example

Demonstrates how to plug a real Redis cache into PyStackQuery for L2 persistence.
This enables data to survive process restarts and be shared across multiple workers.

Requires: pip install redis
Run: uv run --with redis python -m examples.redis_integration
"""

from __future__ import annotations

import asyncio
import time
from typing import Any, cast

try:
    from redis.asyncio import Redis
except ImportError:
    print("This example requires 'redis'. Run: pip install redis")
    exit(1)

from pystackquery import QueryClient, QueryClientConfig, QueryOptions

# ─────────────────────────────────────────────────────────────────────────────
# 1. Implement the StorageBackend Protocol
# ─────────────────────────────────────────────────────────────────────────────


class RedisBackend:
    """
    A production-ready StorageBackend using redis-py.
    """

    def __init__(self, redis_url: str = "redis://localhost:6379") -> None:
        self.redis: Redis = Redis.from_url(redis_url, decode_responses=True)

    async def get(self, key: str) -> str | None:
        """Get data from Redis."""
        val = await self.redis.get(key)
        return cast(str | None, val)

    async def set(self, key: str, value: str, ttl: float | None = None) -> None:
        """Set data in Redis with optional TTL."""
        if ttl:
            await self.redis.set(key, value, ex=int(ttl))
        else:
            await self.redis.set(key, value)

    async def delete(self, key: str) -> None:
        """Delete data from Redis."""
        await self.redis.delete(key)

    async def close(self) -> None:
        """Close Redis connection."""
        await self.redis.aclose()


# ─────────────────────────────────────────────────────────────────────────────
# 2. Example Application
# ─────────────────────────────────────────────────────────────────────────────


async def main() -> None:
    redis_storage = RedisBackend()

    try:
        await cast(Any, redis_storage.redis.ping())
        print("✅ Connected to Redis")
    except Exception:
        print("❌ Could not connect to Redis. Is it running on localhost:6379?")
        return

    client = QueryClient(
        QueryClientConfig(
            storage=redis_storage,
            stale_time=5.0,
            gc_time=60.0,
        )
    )

    async def expensive_fetch() -> dict[str, Any]:
        print("  🔄 Executing expensive operation (Network/DB call)...")
        await asyncio.sleep(0.5)
        return {"timestamp": time.time(), "value": "Expensive Data"}

    print("\n--- 1. First Fetch (Cold Cache) ---")
    start = time.perf_counter()
    data1 = await client.fetch_query(
        QueryOptions(query_key=("dashboard", "metrics"), query_fn=expensive_fetch)
    )
    print(f"  Result: {data1}")
    print(f"  Time: {(time.perf_counter() - start) * 1000:.2f}ms")

    print("\n--- 2. Second Fetch (L1 Memory Hit) ---")
    start = time.perf_counter()
    data2 = await client.fetch_query(
        QueryOptions(query_key=("dashboard", "metrics"), query_fn=expensive_fetch)
    )
    print(f"  Result: {data2}")
    print(f"  Time: {(time.perf_counter() - start) * 1000:.2f}ms")

    print("\n--- 3. Simulating Process Restart (Clear Memory) ---")
    client.cache.clear()
    print("  🗑️  L1 Cache cleared.")

    print("\n--- 4. Third Fetch (L2 Redis Hit - Hydration) ---")
    start = time.perf_counter()
    data3 = await client.fetch_query(
        QueryOptions(query_key=("dashboard", "metrics"), query_fn=expensive_fetch)
    )
    print(f"  Result: {data3}")
    elapsed = (time.perf_counter() - start) * 1000
    print(f"  Time: {elapsed:.2f}ms (Faster than fetch, slower than L1)")

    await redis_storage.close()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
