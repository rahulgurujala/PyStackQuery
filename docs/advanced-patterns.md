# Advanced Patterns

This guide covers advanced usage patterns and real-world scenarios.

## Parallel Queries

Fetch multiple queries simultaneously:

```python
from pystackquery import parallel_queries, QueryOptions

user, posts, settings = await parallel_queries(
    client,
    QueryOptions(("user", user_id), lambda: fetch_user(user_id)),
    QueryOptions(("posts", user_id), lambda: fetch_posts(user_id)),
    QueryOptions(("settings", user_id), lambda: fetch_settings(user_id)),
)
```

Results are returned in the same order as the options.

### Manual Parallel Fetch

You can also use `asyncio.gather` directly:

```python
import asyncio

user, posts = await asyncio.gather(
    client.fetch_query(QueryOptions(("user", user_id), fetch_user)),
    client.fetch_query(QueryOptions(("posts", user_id), fetch_posts)),
)
```

## Dependent Queries

When one query depends on another's result:

```python
from pystackquery import dependent_query, QueryOptions

# Fetch user first, then fetch their posts using the user's ID
posts = await dependent_query(
    client,
    depends_on=QueryOptions(("user", "current"), get_current_user),
    then=lambda user: QueryOptions(
        ("posts", str(user["id"])),
        lambda: fetch_posts(user["id"])
    ),
)
```

### Manual Dependent Queries

```python
# First, get the user
user = await client.fetch_query(
    QueryOptions(("user", "current"), get_current_user)
)

# Then, fetch their posts
posts = await client.fetch_query(
    QueryOptions(
        ("posts", str(user["id"])),
        lambda: fetch_posts(user["id"])
    )
)
```

## The @query Decorator

Wrap async functions with caching:

```python
from pystackquery import query, QueryClient

client = QueryClient()

@query(client, ("users",), stale_time=60.0)
async def get_users():
    return await api.get("/users")

# Now get_users() automatically caches
users = await get_users()
users_again = await get_users()  # From cache

# Access utilities
await get_users.invalidate()  # Invalidate cache
cached = get_users.get_data()  # Get cached data
```

### Decorator Limitations

The decorator works best for parameterless queries. For parameterized queries, use `fetch_query` directly:

```python
# This doesn't work well - key is static
@query(client, ("user",))  # Wrong: always same key
async def get_user(user_id):
    return await api.get(f"/users/{user_id}")

# Do this instead
async def get_user(user_id):
    return await client.fetch_query(
        QueryOptions(("user", str(user_id)), lambda: api.get(f"/users/{user_id}"))
    )
```

## Pagination

### Cursor-Based Pagination

```python
async def fetch_page(cursor: str | None = None) -> dict:
    params = {"cursor": cursor} if cursor else {}
    return await api.get("/items", params=params)

# Fetch first page
page1 = await client.fetch_query(
    QueryOptions(("items", "page", "1"), lambda: fetch_page(None))
)

# Fetch next page using cursor from previous
cursor = page1["next_cursor"]
page2 = await client.fetch_query(
    QueryOptions(("items", "page", "2"), lambda: fetch_page(cursor))
)
```

### Offset-Based Pagination

```python
async def fetch_items_page(page: int, limit: int = 20) -> list:
    return await api.get("/items", params={"offset": page * limit, "limit": limit})

# Fetch multiple pages
for page_num in range(5):
    items = await client.fetch_query(
        QueryOptions(
            ("items", "page", str(page_num)),
            lambda p=page_num: fetch_items_page(p)
        )
    )
```

## Infinite Queries

Load data incrementally by accumulating pages:

```python
class InfiniteQuery:
    def __init__(self, client, base_key, fetch_fn):
        self.client = client
        self.base_key = base_key
        self.fetch_fn = fetch_fn
        self.pages = []
        self.has_more = True

    async def fetch_next_page(self):
        if not self.has_more:
            return

        page_num = len(self.pages)
        data = await self.client.fetch_query(
            QueryOptions(
                (*self.base_key, "page", str(page_num)),
                lambda: self.fetch_fn(page_num)
            )
        )

        self.pages.append(data["items"])
        self.has_more = data.get("has_more", False)

    def get_all_items(self):
        return [item for page in self.pages for item in page]

# Usage
infinite = InfiniteQuery(client, ("posts",), fetch_posts_page)
await infinite.fetch_next_page()  # Page 0
await infinite.fetch_next_page()  # Page 1
all_posts = infinite.get_all_items()
```

## Optimistic Updates

Update local state before the server confirms:

```python
async def like_post(post_id: str):
    # 1. Get current data
    current = client.get_query_data(("post", post_id))

    # 2. Optimistically update
    optimistic = {**current, "likes": current["likes"] + 1, "liked": True}
    client.set_query_data(("post", post_id), optimistic)

    try:
        # 3. Send to server
        await api.post(f"/posts/{post_id}/like")
    except Exception:
        # 4. Rollback on failure
        client.set_query_data(("post", post_id), current)
        raise

    # 5. Refetch for consistency
    await client.invalidate_queries(("post", post_id))
```

## Query Cancellation

Cancel ongoing queries when they're no longer needed:

```python
import asyncio

# Store the task
current_search_task = None

async def search(query: str):
    global current_search_task

    # Cancel previous search
    if current_search_task and not current_search_task.done():
        current_search_task.cancel()

    # Start new search
    async def do_search():
        return await client.fetch_query(
            QueryOptions(("search", query), lambda: api.search(query))
        )

    current_search_task = asyncio.create_task(do_search())

    try:
        return await current_search_task
    except asyncio.CancelledError:
        return None  # Search was superseded
```

## Pause and Resume

Pause queries during offline mode:

```python
# Get the underlying query
query = client._get_or_create_query(opts)

# Pause (stops refetch interval, sets status to PAUSED)
query.pause()

# Check if paused
if query.is_paused:
    print("Query is paused")

# Resume (restarts refetch interval)
query.resume()

# Resume and immediately refetch
query.resume(refetch=True)
```

## WebSocket Updates

Update cache from WebSocket events:

```python
import asyncio

async def handle_websocket():
    async with websockets.connect("ws://api.example.com/events") as ws:
        async for message in ws:
            event = json.loads(message)

            if event["type"] == "user_updated":
                user_data = event["data"]
                # Update cache directly
                client.set_query_data(("user", str(user_data["id"])), user_data)

            elif event["type"] == "post_created":
                # Invalidate the posts list
                await client.invalidate_queries(("posts",))
```

## Request Deduplication

PyStackQuery automatically deduplicates concurrent requests:

```python
# These run concurrently - only ONE API call is made
results = await asyncio.gather(
    client.fetch_query(opts),
    client.fetch_query(opts),
    client.fetch_query(opts),
)

# All three get the same result from a single fetch
```

This is automatic. No configuration needed.

## Error Boundaries

Centralize error handling:

```python
class QueryErrorBoundary:
    def __init__(self, client):
        self.client = client
        self.errors = []

    async def fetch(self, options):
        try:
            return await self.client.fetch_query(options)
        except Exception as e:
            self.errors.append({
                "key": options.query_key,
                "error": e,
                "time": time.time()
            })
            raise

    def get_recent_errors(self, seconds=60):
        cutoff = time.time() - seconds
        return [e for e in self.errors if e["time"] > cutoff]

# Usage
boundary = QueryErrorBoundary(client)

try:
    users = await boundary.fetch(QueryOptions(("users",), fetch_users))
except Exception:
    print(f"Recent errors: {boundary.get_recent_errors()}")
```

## Retry Strategies

### Custom Retry Logic

```python
def no_retry_on_404(attempt: int) -> float:
    # This is called between retries
    # Return delay in seconds
    return 2 ** attempt  # Exponential backoff

async def fetch_with_404_check():
    try:
        return await api.get("/resource")
    except NotFoundError:
        # Don't retry 404s
        raise
    except Exception:
        # Other errors will retry
        raise

QueryOptions(
    query_key=("resource",),
    query_fn=fetch_with_404_check,
    retry=3,
    retry_delay=no_retry_on_404
)
```

### Conditional Retry

```python
async def smart_fetch():
    try:
        return await api.get("/resource")
    except RateLimitError as e:
        # Wait for rate limit to reset
        await asyncio.sleep(e.retry_after)
        raise  # Will trigger retry
    except AuthError:
        # Don't retry auth errors
        raise
```

## Logging

Enable debug logging:

```python
import logging

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger("pystackquery")
logger.setLevel(logging.DEBUG)

# Now you'll see:
# DEBUG:pystackquery:Cache HIT (fresh) for ('user', '123')
# DEBUG:pystackquery:Cache MISS for ('posts',)
# DEBUG:pystackquery:Fetch success for ('posts',)
```

## Testing

### Mocking Queries

```python
import pytest
from unittest.mock import AsyncMock

@pytest.fixture
def client():
    return QueryClient()

@pytest.fixture
def mock_fetch():
    return AsyncMock(return_value={"id": 1, "name": "Test"})

async def test_fetch_user(client, mock_fetch):
    result = await client.fetch_query(
        QueryOptions(("user", "1"), mock_fetch)
    )

    assert result["name"] == "Test"
    mock_fetch.assert_called_once()

async def test_cache_hit(client, mock_fetch):
    opts = QueryOptions(("user", "1"), mock_fetch, stale_time=60)

    # First call
    await client.fetch_query(opts)
    # Second call - should use cache
    await client.fetch_query(opts)

    # Only one actual fetch
    assert mock_fetch.call_count == 1
```

### Testing Observers

```python
async def test_observer_updates(client):
    updates = []
    mock_fetch = AsyncMock(return_value={"value": 42})

    observer = client.watch(QueryOptions(("test",), mock_fetch))
    unsub = observer.subscribe(lambda s: updates.append(s.status.name))

    # Wait for fetch
    await asyncio.sleep(0.1)

    unsub()

    assert "PENDING" in updates or "SUCCESS" in updates
```
