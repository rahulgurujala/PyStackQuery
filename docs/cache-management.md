# Cache Management

PyStackQuery provides full control over the cache. You can invalidate data, prefetch data, manually update the cache, and more.

## Cache Basics

Every query is stored in an in-memory cache using its query key. The cache:

- Returns data instantly on subsequent requests
- Supports LRU eviction when full
- Automatically garbage collects unused queries
- Enables partial key matching for bulk operations

## Invalidating Queries

Mark cached data as stale so it gets refetched.

### Invalidate by Exact Key

```python
await client.invalidate_queries(("user", "123"))
```

### Invalidate by Partial Key

Partial keys invalidate all matching queries:

```python
# Invalidate all user-related queries
await client.invalidate_queries(("user",))

# This invalidates:
# - ("user", "1")
# - ("user", "2")
# - ("user", "1", "posts")
# - Any key starting with ("user", ...)
```

### Invalidate All Queries

```python
await client.invalidate_queries()  # No filter = all queries
```

### Invalidation Behavior

When you invalidate a query:

1. The data is marked as stale
2. If the query has active observers, it refetches automatically
3. If no observers, data stays stale until next access

Control refetching with the `refetch` parameter:

```python
# Invalidate and refetch active queries (default)
await client.invalidate_queries(("users",), refetch=True)

# Invalidate only, don't refetch
await client.invalidate_queries(("users",), refetch=False)
```

## Prefetching

Fetch and cache data before it's needed. Great for anticipating user navigation.

```python
async def prefetch_user_data(user_id: str):
    # Prefetch in the background
    await client.prefetch_query(
        QueryOptions(
            query_key=("user", user_id),
            query_fn=lambda: fetch_user(user_id)
        )
    )

# Prefetch when you anticipate data will be needed
await prefetch_user_data("123")

# Later when you need it, data is already cached
user = await client.fetch_query(
    QueryOptions(
        query_key=("user", "123"),
        query_fn=lambda: fetch_user("123")
    )
)  # Returns instantly from cache
```

**Prefetch behavior:**
- Silent on failure (doesn't throw)
- Respects stale_time (won't refetch if data is fresh)
- Doesn't return data (use `fetch_query` to get data)

## Manual Cache Updates

### Get Cached Data

Read from cache without triggering a fetch:

```python
# Returns data if cached, None otherwise
data = client.get_query_data(("user", "123"))

if data is not None:
    print(f"Cached user: {data['name']}")
else:
    print("Not in cache")
```

### Set Cached Data

Manually update the cache:

```python
# Update cache directly
client.set_query_data(("user", "123"), {"id": 123, "name": "Updated Name"})

# Next fetch returns this data (until stale)
user = await client.fetch_query(
    QueryOptions(
        query_key=("user", "123"),
        query_fn=lambda: fetch_user("123")
    )
)
print(user["name"])  # "Updated Name"
```

Common use cases:
- Optimistic updates after mutations
- Hydrating cache from server-rendered data
- Updating cache from WebSocket events

### Get Query State

Access the full state, not just the data:

```python
state = client.get_query_state(("user", "123"))

if state is not None:
    print(f"Status: {state.status}")
    print(f"Data: {state.data}")
    print(f"Error: {state.error}")
    print(f"Updated at: {state.data_updated_at}")
```

## Removing Queries

### Remove Specific Queries

Completely remove queries from cache (not just invalidate):

```python
# Remove one query
client.remove_queries(("user", "123"))

# Remove all user queries
client.remove_queries(("user",))

# Remove all queries
client.remove_queries()
```

**Difference from invalidate:**
- `invalidate_queries`: Marks stale, keeps data, can trigger refetch
- `remove_queries`: Deletes data entirely, frees memory

### Clear Entire Cache

```python
client.clear()
```

This removes all queries and releases all resources.

## Resetting Queries

Reset queries to their initial state (as if never fetched):

```python
# Reset specific query
client.reset_queries(("user", "123"))

# Reset all user queries
client.reset_queries(("user",))

# Reset all queries
client.reset_queries()
```

**Reset sets:**
- `status` = IDLE
- `fetch_status` = IDLE
- `data` = None
- `error` = None
- All timestamps = None
- Failure count = 0

## Cache Configuration

### Maximum Cache Size

Control memory usage with `cache_max_size`:

```python
from pystackquery import QueryClient, QueryClientConfig

client = QueryClient(
    QueryClientConfig(cache_max_size=500)  # Store up to 500 queries
)
```

When the cache is full, the least recently used query is evicted.

### Garbage Collection Time

Control how long unused queries stay in cache:

```python
QueryOptions(
    query_key=("user", "123"),
    query_fn=lambda: fetch_user("123"),
    gc_time=60.0  # Remove after 60 seconds of no observers
)
```

**How GC works:**
1. When the last observer unsubscribes, a timer starts
2. After `gc_time` seconds, the query is removed
3. If a new observer subscribes, the timer cancels

## Accessing the Cache Directly

For advanced use cases, access the underlying cache:

```python
cache = client.cache

# Check cache size
print(f"Cached queries: {len(cache)}")

# Check if key exists
if ("user", "123") in cache:
    print("User is cached")

# Find all matching queries
user_queries = cache.find_all(("user",))
for query in user_queries:
    print(f"Key: {query.key}, Has data: {query.state.has_data}")
```

## Best Practices

### 1. Design Keys for Invalidation

Structure keys so you can invalidate related data easily:

```python
# Good: hierarchical
("user", user_id)
("user", user_id, "posts")
("user", user_id, "followers")

# Invalidate everything for a user
await client.invalidate_queries(("user", user_id))
```

### 2. Invalidate After Mutations

```python
async def update_user(user_id: str, data: dict) -> dict:
    result = await api.put(f"/users/{user_id}", data)
    await client.invalidate_queries(("user", user_id))
    return result
```

### 3. Prefetch Anticipated Data

```python
# After fetching a list, prefetch details you expect to need
async def fetch_users_with_prefetch():
    users = await client.fetch_query(
        QueryOptions(("users",), fetch_all_users)
    )

    # Prefetch first few user details in background
    for user in users[:5]:
        asyncio.create_task(
            client.prefetch_query(
                QueryOptions(("user", str(user["id"])), lambda u=user: fetch_user(u["id"]))
            )
        )

    return users
```

### 4. Use set_query_data for Optimistic Updates

```python
# Before mutation completes
client.set_query_data(("user", user_id), optimistic_data)

# After mutation
await client.invalidate_queries(("user", user_id))
```

### 5. Clean Up on Logout

```python
async def logout():
    await auth.logout()
    client.clear()  # Remove all cached user data
```
