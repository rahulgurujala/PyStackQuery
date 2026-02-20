# Advanced Patterns

This guide explores architectural patterns for scaling PyStackQuery in complex applications.

## Prefetching for Speed

Anticipate user navigation by warming up the cache. Prefetching is silent and never throws on network failure.

```python
async def on_user_hover(user_id):
    # Start fetching data before the user even clicks
    await client.prefetch_query(
        QueryOptions(query_key=("user", user_id), query_fn=fetch_user)
    )
```

## Parallel and Dependent Queries

### Parallel
Use `parallel_queries` to reduce total latency when a screen needs data from multiple sources.

```python
from pystackquery import parallel_queries

# Fetches all three concurrently
users, settings, posts = await parallel_queries(client, opt1, opt2, opt3)
```

### Dependent
Use `dependent_query` when the second request requires an ID from the first.

```python
from pystackquery import dependent_query

posts = await dependent_query(
    client,
    depends_on=QueryOptions(("user", "me"), fetch_me),
    then=lambda user: QueryOptions(("posts", user["id"]), fetch_posts)
)
```

## Testing Observers

Since PyStackQuery uses background tasks for hydration and refetching, your tests should account for event loop cycles.

```python
async def test_observer_flow(client):
    observer = client.watch(opts)
    states = []
    
    # Subscribe is synchronous
    unsub = observer.subscribe(lambda s: states.append(s.status))
    
    # Wait for the background fetch to settle
    await asyncio.sleep(0.1)
    
    assert QueryStatus.SUCCESS in states
    unsub()
```

## Production L2 Backends

For production, we recommend implementing a robust `StorageBackend` using Redis or SQLite.

### Why SQLite?
For single-server or desktop applications, SQLite is often faster than Redis and requires zero infrastructure management. It’s perfect for ensuring data persists across application restarts.

### Why Redis?
Use Redis if you have multiple server instances (distributed system) that need to share the same cached state to stay synchronized.
