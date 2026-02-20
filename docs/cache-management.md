# Cache Management

PyStackQuery provides granular control over the data lifecycle, allowing both automatic and manual cache operations.

## Partial Invalidation

One of the most powerful features is prefix-based invalidation. Since keys are tuples, you can invalidate an entire branch of your state tree.

```python
# Keys in cache:
# ("users", "list")
# ("user", "1")
# ("user", "1", "posts")

# Invalidates both user 1 and all their posts
await client.invalidate_queries(("user", "1"))
```

Invalidation marks data as stale (timestamp `0.0`) and persists this state to L2. If any observers are active for these keys, a refetch is triggered immediately in the background.

## Manual Updates

You can manually inject data into the cache. This is commonly used after a mutation to keep the UI in sync without a fresh network request.

```python
# Immediately update the user in the cache
client.set_query_data(("user", "123"), updated_user_object)
```

## Cache Eviction (LRU)

The L1 (memory) cache uses an **LRU (Least Recently Used)** strategy. When the `cache_max_size` is reached, the oldest query is destroyed. If L2 storage is configured, the data remains available on disk/Redis even after being evicted from memory.

## Garbage Collection

Inactive queries (those with zero observers) are cleaned up after `gc_time`. 
- **L1:** The Query instance is destroyed.
- **L2:** The storage backend is notified to delete the serialized state (via TTL where supported).
