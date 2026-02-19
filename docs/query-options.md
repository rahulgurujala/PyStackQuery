# Query Options

This document explains every option available when configuring a query.

## QueryOptions Reference

```python
from pystackquery import QueryOptions

opts = QueryOptions(
    query_key=("users",),           # Required
    query_fn=fetch_users,           # Required
    stale_time=0.0,                 # Optional
    gc_time=300.0,                  # Optional
    refetch_interval=None,          # Optional
    retry=3,                        # Optional
    retry_delay=default_retry_delay,# Optional
    enabled=True,                   # Optional
    on_success=None,                # Optional
    on_error=None,                  # Optional
    on_settled=None,                # Optional
    select=None,                    # Optional
    placeholder_data=None,          # Optional
)
```

## Required Options

### query_key

**Type:** `tuple[str, ...]`

Unique identifier for this query. Used for caching and invalidation.

```python
# Simple key
QueryOptions(query_key=("users",), ...)

# Hierarchical key
QueryOptions(query_key=("user", "123", "posts"), ...)

# With dynamic values (convert to strings)
user_id = 123
QueryOptions(query_key=("user", str(user_id)), ...)
```

**Key matching for invalidation:**

Keys support partial matching. Invalidating a parent key invalidates all children:

```python
# These keys exist in cache:
# ("user", "1")
# ("user", "1", "posts")
# ("user", "2")

await client.invalidate_queries(("user", "1"))
# Invalidates: ("user", "1") and ("user", "1", "posts")
# Keeps: ("user", "2")

await client.invalidate_queries(("user",))
# Invalidates all three
```

### query_fn

**Type:** `Callable[[], Awaitable[T]]`

Async function that fetches the data. Takes no arguments and returns the data.

```python
# Direct function
async def fetch_users():
    return await api.get("/users")

QueryOptions(query_key=("users",), query_fn=fetch_users)

# Lambda for parameterized fetches
user_id = 123
QueryOptions(
    query_key=("user", str(user_id)),
    query_fn=lambda: fetch_user(user_id)
)
```

**Important:** The function takes no arguments. Use closures or lambdas to capture parameters.

## Timing Options

### stale_time

**Type:** `float`
**Default:** `0.0`

Seconds before data is considered stale.

```python
# Data is always stale (refetches every time)
QueryOptions(..., stale_time=0.0)

# Data fresh for 1 minute
QueryOptions(..., stale_time=60.0)

# Data fresh for 1 hour
QueryOptions(..., stale_time=3600.0)
```

**Behavior when data is stale:**

1. Returns cached data immediately
2. Triggers background refetch
3. Updates cache when refetch completes

This is "stale-while-revalidate" - users see data instantly while fresh data loads.

### gc_time

**Type:** `float`
**Default:** `300.0` (5 minutes)

Seconds before an unused query is garbage collected from cache.

```python
# Remove after 1 minute of no access
QueryOptions(..., gc_time=60.0)

# Keep for 1 hour
QueryOptions(..., gc_time=3600.0)
```

A query is "unused" when it has no active observers (subscribers). The timer starts when the last observer unsubscribes.

### refetch_interval

**Type:** `float | None`
**Default:** `None`

If set, automatically refetch every N seconds while the query has observers.

```python
# Refetch every 30 seconds
QueryOptions(..., refetch_interval=30.0)

# No automatic refetching (default)
QueryOptions(..., refetch_interval=None)
```

Use this for data that changes frequently (stock prices, live scores, etc.).

**Note:** Refetching only happens while there are active observers. When the last observer unsubscribes, refetching stops.

## Retry Options

### retry

**Type:** `int`
**Default:** `3`

Number of retry attempts on failure.

```python
# No retries
QueryOptions(..., retry=0)

# Retry 3 times (4 total attempts)
QueryOptions(..., retry=3)

# Retry 10 times
QueryOptions(..., retry=10)
```

### retry_delay

**Type:** `Callable[[int], float]`
**Default:** Exponential backoff (1s, 2s, 4s, 8s, ... up to 30s)

Function that returns the delay before each retry attempt.

```python
from pystackquery import default_retry_delay

# Default: exponential backoff
QueryOptions(..., retry_delay=default_retry_delay)

# Custom: fixed 1 second delay
QueryOptions(..., retry_delay=lambda attempt: 1.0)

# Custom: linear backoff (1s, 2s, 3s, ...)
QueryOptions(..., retry_delay=lambda attempt: float(attempt + 1))

# Custom: exponential with jitter
import random
def jittered_backoff(attempt: int) -> float:
    base = min(2 ** attempt, 30)
    return base + random.uniform(0, 1)

QueryOptions(..., retry_delay=jittered_backoff)
```

The `attempt` parameter is zero-indexed (first retry is attempt 0).

## Behavior Options

### enabled

**Type:** `bool`
**Default:** `True`

If `False`, the query will not automatically fetch when observed.

```python
# Normal behavior
QueryOptions(..., enabled=True)

# Disabled - won't fetch automatically
QueryOptions(..., enabled=False)
```

Use this for conditional fetching:

```python
user_id = get_current_user_id()  # Might be None

opts = QueryOptions(
    query_key=("user", str(user_id or "")),
    query_fn=lambda: fetch_user(user_id),
    enabled=user_id is not None  # Only fetch if logged in
)
```

## Callback Options

### on_success

**Type:** `Callable[[T], Any] | None`
**Default:** `None`

Called when fetch succeeds.

```python
def handle_success(data):
    print(f"Fetched {len(data)} users")

QueryOptions(..., on_success=handle_success)
```

### on_error

**Type:** `Callable[[Exception], Any] | None`
**Default:** `None`

Called when fetch fails (after all retries).

```python
def handle_error(error):
    print(f"Fetch failed: {error}")
    log_to_sentry(error)

QueryOptions(..., on_error=handle_error)
```

### on_settled

**Type:** `Callable[[T | None, Exception | None], Any] | None`
**Default:** `None`

Called when fetch completes (success or failure).

```python
def handle_settled(data, error):
    if error:
        print(f"Failed: {error}")
    else:
        print(f"Success: {data}")

QueryOptions(..., on_settled=handle_settled)
```

## Data Transformation Options

### select

**Type:** `Callable[[T], Any] | None`
**Default:** `None`

Transform data before returning to observers.

```python
# Only return user names
QueryOptions(
    ...,
    select=lambda users: [u["name"] for u in users]
)

# Extract specific field
QueryOptions(
    ...,
    select=lambda response: response["data"]["user"]
)
```

**Note:** The full data is still cached. The transform only applies when reading.

### placeholder_data

**Type:** `T | None`
**Default:** `None`

Data to use while the first fetch is pending.

```python
# Show empty list while loading
QueryOptions(
    query_key=("users",),
    query_fn=fetch_users,
    placeholder_data=[]
)

# Show skeleton data
QueryOptions(
    query_key=("user", user_id),
    query_fn=lambda: fetch_user(user_id),
    placeholder_data={"name": "Loading...", "email": "..."}
)
```

## QueryClientConfig Reference

Set defaults for all queries:

```python
from pystackquery import QueryClient, QueryClientConfig

client = QueryClient(
    QueryClientConfig(
        stale_time=30.0,         # Default: 0.0
        gc_time=600.0,           # Default: 300.0
        retry=5,                 # Default: 3
        retry_delay=my_delay_fn, # Default: exponential backoff
        cache_max_size=500,      # Default: 1000
    )
)
```

### cache_max_size

**Type:** `int`
**Default:** `1000`

Maximum number of queries to keep in cache. When exceeded, least recently used queries are evicted.

```python
# Small cache for memory-constrained environments
QueryClientConfig(cache_max_size=100)

# Large cache for data-heavy applications
QueryClientConfig(cache_max_size=10000)
```

## Option Precedence

Query-level options override client-level defaults:

```python
client = QueryClient(QueryClientConfig(stale_time=60.0, retry=5))

# Uses client defaults: stale_time=60.0, retry=5
await client.fetch_query(QueryOptions(("users",), fetch_users))

# Overrides stale_time, keeps retry=5
await client.fetch_query(QueryOptions(("users",), fetch_users, stale_time=120.0))
```
