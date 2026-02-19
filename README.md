# PyStackQuery

Async data fetching and caching library for Python.

PyStackQuery handles the hard parts of working with async data: caching, deduplication, retries, and reactive state updates. You focus on *what* to fetch, the library handles *how*.

## Installation

```bash
pip install pystackquery
```

Requires Python 3.11+

## Quick Start

```python
import asyncio
from pystackquery import QueryClient, QueryOptions

client = QueryClient()

async def fetch_user(user_id: int) -> dict:
    # Your async fetch logic here
    async with aiohttp.ClientSession() as session:
        async with session.get(f"https://api.example.com/users/{user_id}") as resp:
            return await resp.json()

async def main():
    # Fetch with automatic caching
    user = await client.fetch_query(
        QueryOptions(
            query_key=("user", "123"),
            query_fn=lambda: fetch_user(123)
        )
    )

    # Second call returns cached data instantly
    user_again = await client.fetch_query(
        QueryOptions(
            query_key=("user", "123"),
            query_fn=lambda: fetch_user(123)
        )
    )

asyncio.run(main())
```

That's it. The first call fetches from the API. The second call returns instantly from cache.

## What Problems Does This Solve?

**Without PyStackQuery**, you write code like this over and over:

```python
cache = {}
pending = {}
lock = asyncio.Lock()

async def get_user(user_id):
    key = f"user_{user_id}"

    async with lock:
        if key in cache:
            return cache[key]
        if key in pending:
            return await pending[key]

        task = asyncio.create_task(fetch_user(user_id))
        pending[key] = task

    try:
        result = await task
        cache[key] = result
        return result
    finally:
        del pending[key]
```

**With PyStackQuery**, you write:

```python
user = await client.fetch_query(
    QueryOptions(("user", user_id), lambda: fetch_user(user_id))
)
```

The library handles:
- Caching
- Request deduplication (concurrent calls share one request)
- Automatic retries with backoff
- Stale-while-revalidate
- Cache invalidation
- Reactive updates

## Core Concepts

### Query Keys

Every query needs a unique key. Keys are tuples of strings:

```python
("users",)                    # All users
("user", "123")               # Specific user
("posts", "user", "123")      # Posts by user 123
```

Keys enable:
- Cache lookups
- Partial invalidation (invalidate `("users",)` clears all user queries)

### Query Options

Configure how a query behaves:

```python
QueryOptions(
    query_key=("user", "123"),
    query_fn=lambda: fetch_user(123),
    stale_time=60.0,    # Data fresh for 60 seconds
    retry=3,            # Retry 3 times on failure
)
```

### Stale-While-Revalidate

When data becomes stale, you get the cached data immediately while a background refresh happens:

```python
# First call: fetches from API
data = await client.fetch_query(opts)

# Wait for stale_time to pass...

# Second call: returns stale data instantly, refreshes in background
data = await client.fetch_query(opts)
```

Your users see data immediately. Fresh data loads in the background.

## Documentation

See the [docs/](./docs/) folder for comprehensive documentation:

- [Getting Started](./docs/getting-started.md) - Installation and basic usage
- [Query Options](./docs/query-options.md) - All configuration options explained
- [Mutations](./docs/mutations.md) - Handling POST/PUT/DELETE operations
- [Cache Management](./docs/cache-management.md) - Invalidation, prefetching, manual updates
- [Observers](./docs/observers.md) - Reactive state updates
- [Advanced Patterns](./docs/advanced-patterns.md) - Dependent queries, parallel fetching
- [Framework Integrations](./docs/framework-integrations.md) - FastAPI, Tkinter, Textual, CLI tools, Jupyter
- [API Reference](./docs/api-reference.md) - Complete API documentation

## License

MIT
