# API Reference

PyStackQuery is designed to be minimal but powerful. The entire public API revolves around the `QueryClient`.

## QueryClient

The main orchestrator for the dual-tier cache.

### fetch_query

```python
async def fetch_query[T](self, options: QueryOptions[T]) -> T
```

The standard way to request data. Uses the **Stale-While-Revalidate** pattern:
1.  **Fresh L1/L2:** Returns data instantly.
2.  **Stale L1/L2:** Returns stale data instantly, triggers background network fetch.
3.  **Cold Cache:** Performs blocking network fetch.

### prefetch_query

```python
async def prefetch_query[T](self, options: QueryOptions[T]) -> None
```

Warms up the cache for a specific key. Unlike `fetch_query`, this never blocks for the result and fails silently on network errors.

### watch

```python
def watch[T](self, options: QueryOptions[T]) -> QueryObserver[T]
```

Creates a reactive observer. Use this when you need your UI or service to react to data changes over time.

---

## QueryObserver

The bridge between a Query and a listener.

### subscribe

```python
def subscribe(self, listener: Callable[[QueryState[T, Exception]], object]) -> Callable[[], None]
```

**Synchronous.** Attaches a callback to the query. 
- The `listener` is called immediately with the current state.
- If the query is stale, a background fetch is initiated.
- Returns an **unsubscribe function**.

---

## Persistence and Hydration

PyStackQuery supports pluggable L2 storage (Redis, SQLite, Disk, etc.).

### How Hydration Works
1.  When you call `watch()` or `fetch_query()` on a cold key, the client creates a Query instance and starts a background **Hydration Task**.
2.  `fetch_query()` will `await` this task before checking staleness.
3.  If L2 data exists, it is loaded into memory (L1).
4.  This allows data to survive process restarts or be shared across multiple workers.

### Implementation Protocol
To implement your own L2 storage, provide a class matching the `StorageBackend` Protocol:

```python
class MyStorage:
    async def get(self, key: str) -> str | None: ...
    async def set(self, key: str, value: str, ttl: float | None = None) -> None: ...
    async def delete(self, key: str) -> None: ...
```

---

## Core Configuration

### QueryClientConfig

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `stale_time` | `float` | `0.0` | Seconds before data is considered stale. |
| `gc_time` | `float` | `300.0` | How long inactive queries persist in L1/L2. |
| `retry` | `int` | `3` | Number of exponential backoff attempts. |
| `storage` | `StorageBackend` | `None` | The L2 persistence layer. |

### QueryOptions

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `query_key` | `tuple` | **Required** | The hierarchical identifier. |
| `query_fn` | `coroutine` | **Required** | The async logic to get data. |
| `refetch_interval` | `float` | `None` | Auto-poll interval (only while observed). |
| `select` | `callable` | `None` | Transformation applied at the observer level. |
| `placeholder_data` | `T` | `None` | Instant data to show while first fetch is pending. |
