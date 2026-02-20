# Storage Backends (L2 Persistence)

PyStackQuery features a two-tier caching architecture. While L1 (memory) is handled automatically, L2 (persistence) allows your data to survive process restarts and stay synchronized across multiple workers.

To enable L2 caching, implement the `StorageBackend` Protocol or use one of the recipes below.

---

## 1. Redis (Distributed Systems)

Use Redis when you have multiple API instances or workers that need to share the same cache.

**Requirements:** `pip install redis`

```python
import json
from redis.asyncio import Redis
from pystackquery import QueryClient, QueryClientConfig

class RedisStorage:
    def __init__(self, redis_url: str = "redis://localhost:6379"):
        self.redis = Redis.from_url(redis_url, decode_responses=True)

    async def get(self, key: str) -> str | None:
        return await self.redis.get(key)

    async def set(self, key: str, value: str, ttl: float | None = None) -> None:
        if ttl:
            await self.redis.set(key, value, ex=int(ttl))
        else:
            await self.redis.set(key, value)

    async def delete(self, key: str) -> None:
        await self.redis.delete(key)

# Usage
storage = RedisStorage()
client = QueryClient(QueryClientConfig(storage=storage))
```

---

## 2. SQLite (Local & Desktop Apps)

SQLite is the best choice for CLI tools, desktop applications (Tkinter/PySide), or single-node servers. It requires zero infrastructure and is extremely fast for local lookups.

**Requirements:** `pip install aiosqlite`

```python
import aiosqlite
import asyncio

class SQLiteStorage:
    def __init__(self, db_path: str = "cache.db"):
        self.db_path = db_path
        self._initialized = False

    async def _init_db(self):
        if self._initialized: return
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "CREATE TABLE IF NOT EXISTS cache (key TEXT PRIMARY KEY, value TEXT)"
            )
            await db.commit()
        self._initialized = True

    async def get(self, key: str) -> str | None:
        await self._init_db()
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute("SELECT value FROM cache WHERE key = ?", (key,)) as cursor:
                row = await cursor.fetchone()
                return row[0] if row else None

    async def set(self, key: str, value: str, ttl: float | None = None) -> None:
        await self._init_db()
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "INSERT OR REPLACE INTO cache (key, value) VALUES (?, ?)", (key, value)
            )
            await db.commit()

    async def delete(self, key: str) -> None:
        await self._init_db()
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("DELETE FROM cache WHERE key = ?", (key,))
            await db.commit()
```

---

## 3. DiskCache (Fastest Local Caching)

`diskcache` is a highly optimized Django-compatible cache that uses SQLite under the hood with significant performance tuning.

**Requirements:** `pip install diskcache`

```python
import asyncio
from diskcache import Cache

class DiskCacheStorage:
    def __init__(self, directory: str = ".cache"):
        self.cache = Cache(directory)

    async def get(self, key: str) -> str | None:
        # DiskCache is sync, we wrap in to_thread for async compatibility
        return await asyncio.to_thread(self.cache.get, key)

    async def set(self, key: str, value: str, ttl: float | None = None) -> None:
        await asyncio.to_thread(self.cache.set, key, value, expire=ttl)

    async def delete(self, key: str) -> None:
        await asyncio.to_thread(self.cache.delete, key)
```

---

## Performance Considerations

### Serialization
PyStackQuery passes a JSON-serialized string to the `set` method. Your backend only needs to store and retrieve these strings.

### Background Sync
Persistence operations happen in background tasks. This ensures that L2 overhead (usually ~10-50ms for Redis) never blocks your application's main logic or UI responsiveness.

### Error Handling
If your L2 storage fails (e.g., Redis goes down), PyStackQuery will log the error and fall back to L1-only mode automatically. Your application will keep running.
