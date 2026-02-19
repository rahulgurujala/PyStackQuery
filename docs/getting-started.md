# Getting Started

This guide walks you through installing PyStackQuery and writing your first queries.

## Installation

### Using pip

```bash
pip install pystackquery
```

### Using uv

```bash
uv add pystackquery
```

### Requirements

- Python 3.11 or higher
- No external dependencies (only `typing_extensions` for Python < 3.13)

## Your First Query

Let's fetch some data from an API.

### Step 1: Create a Client

```python
from pystackquery import QueryClient

client = QueryClient()
```

The client manages all your queries. Create one instance and use it throughout your application.

### Step 2: Define a Fetch Function

```python
import aiohttp

async def fetch_users() -> list[dict]:
    async with aiohttp.ClientSession() as session:
        async with session.get("https://api.example.com/users") as response:
            return await response.json()
```

This is your data fetching logic. It can be any async function that returns data.

### Step 3: Fetch with Caching

```python
from pystackquery import QueryOptions

users = await client.fetch_query(
    QueryOptions(
        query_key=("users",),
        query_fn=fetch_users
    )
)
```

That's it. The data is now cached. Subsequent calls with the same key return instantly.

## Complete Example

```python
import asyncio
import aiohttp
from pystackquery import QueryClient, QueryOptions

client = QueryClient()

async def fetch_user(user_id: int) -> dict:
    async with aiohttp.ClientSession() as session:
        url = f"https://jsonplaceholder.typicode.com/users/{user_id}"
        async with session.get(url) as response:
            return await response.json()

async def main():
    # First fetch - hits the API
    print("Fetching user 1...")
    user = await client.fetch_query(
        QueryOptions(
            query_key=("user", "1"),
            query_fn=lambda: fetch_user(1)
        )
    )
    print(f"Got: {user['name']}")

    # Second fetch - returns from cache instantly
    print("Fetching user 1 again...")
    user = await client.fetch_query(
        QueryOptions(
            query_key=("user", "1"),
            query_fn=lambda: fetch_user(1)
        )
    )
    print(f"Got: {user['name']} (from cache)")

if __name__ == "__main__":
    asyncio.run(main())
```

## Understanding Query Keys

Query keys uniquely identify cached data. They're tuples of strings.

```python
# Good: Hierarchical keys
("users",)                     # List of all users
("user", "123")                # User with ID 123
("user", "123", "posts")       # Posts for user 123
("posts", "page", "1")         # First page of posts

# The key structure enables partial invalidation
await client.invalidate_queries(("user", "123"))  # Clears user 123 and their posts
```

### Key Design Tips

1. **Start general, get specific**: `("users",)` → `("user", "123")` → `("user", "123", "posts")`

2. **Use string IDs**: Even if your IDs are integers, convert them: `("user", str(user_id))`

3. **Be consistent**: Pick a naming convention and stick with it

## Configuring Freshness

By default, data is always considered stale (fetched every time). Set `stale_time` to keep data fresh:

```python
users = await client.fetch_query(
    QueryOptions(
        query_key=("users",),
        query_fn=fetch_users,
        stale_time=60.0  # Data is fresh for 60 seconds
    )
)
```

When data is fresh, subsequent fetches return the cached data without any network request.

When data becomes stale:
1. You get the stale data immediately
2. A background fetch updates the cache
3. Next access gets fresh data

This is called "stale-while-revalidate" and provides the best user experience.

## Error Handling

Queries automatically retry on failure:

```python
users = await client.fetch_query(
    QueryOptions(
        query_key=("users",),
        query_fn=fetch_users,
        retry=3  # Retry up to 3 times (default)
    )
)
```

If all retries fail, the exception is raised. You can catch it normally:

```python
try:
    users = await client.fetch_query(opts)
except Exception as e:
    print(f"Failed to fetch users: {e}")
```

## Global Defaults

Instead of setting options on every query, configure defaults on the client:

```python
from pystackquery import QueryClient, QueryClientConfig

client = QueryClient(
    QueryClientConfig(
        stale_time=30.0,      # All queries fresh for 30 seconds
        retry=5,              # All queries retry 5 times
        gc_time=600.0,        # Cache entries live for 10 minutes
        cache_max_size=500,   # Store up to 500 queries
    )
)
```

Individual query options override these defaults.

## Next Steps

- [Query Options](./query-options.md) - All configuration options explained
- [Cache Management](./cache-management.md) - Invalidation and manual updates
- [Mutations](./mutations.md) - Handling POST/PUT/DELETE
