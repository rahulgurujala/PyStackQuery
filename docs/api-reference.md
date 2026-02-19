# API Reference

Complete reference for all PyStackQuery classes, methods, and types.

## QueryClient

The main entry point for all operations.

### Constructor

```python
QueryClient(config: QueryClientConfig | None = None)
```

**Parameters:**
- `config`: Optional configuration with default values

**Example:**
```python
# Default configuration
client = QueryClient()

# Custom configuration
client = QueryClient(QueryClientConfig(stale_time=60.0))
```

### Methods

#### fetch_query

```python
async def fetch_query(self, options: QueryOptions[T]) -> T
```

Fetch data with automatic caching.

**Behavior:**
- Fresh data in cache → returns immediately
- Stale data in cache → returns stale data, refetches in background
- No data in cache → fetches and returns

**Parameters:**
- `options`: Query configuration

**Returns:** The fetched data

**Raises:** Exception if fetch fails after all retries

---

#### prefetch_query

```python
async def prefetch_query(self, options: QueryOptions[T]) -> None
```

Fetch and cache data without returning it.

**Parameters:**
- `options`: Query configuration

**Notes:**
- Silent on failure (doesn't throw)
- Respects stale_time

---

#### get_query_data

```python
def get_query_data(self, key: QueryKey) -> Any | None
```

Get cached data for a query key.

**Parameters:**
- `key`: The query key tuple

**Returns:** Cached data or None

---

#### set_query_data

```python
def set_query_data(self, key: QueryKey, data: Any) -> None
```

Manually update cached data.

**Parameters:**
- `key`: The query key tuple
- `data`: The data to cache

---

#### get_query_state

```python
def get_query_state(self, key: QueryKey) -> QueryState[Any] | None
```

Get the full state for a query key.

**Parameters:**
- `key`: The query key tuple

**Returns:** QueryState or None if not cached

---

#### invalidate_queries

```python
async def invalidate_queries(
    self,
    filter_key: QueryKey | None = None,
    *,
    refetch: bool = True,
) -> None
```

Invalidate queries matching the filter key.

**Parameters:**
- `filter_key`: Partial key to match (None = all queries)
- `refetch`: Whether to refetch active queries (default: True)

---

#### remove_queries

```python
def remove_queries(self, filter_key: QueryKey | None = None) -> None
```

Remove queries from cache entirely.

**Parameters:**
- `filter_key`: Partial key to match (None = all queries)

---

#### reset_queries

```python
def reset_queries(self, filter_key: QueryKey | None = None) -> None
```

Reset queries to their initial state.

**Parameters:**
- `filter_key`: Partial key to match (None = all queries)

---

#### watch

```python
def watch(self, options: QueryOptions[T]) -> QueryObserver[T]
```

Create an observer for reactive state updates.

**Parameters:**
- `options`: Query configuration

**Returns:** QueryObserver instance

---

#### mutation

```python
def mutation(
    self,
    options: MutationOptions[TInput, TData],
) -> Mutation[TInput, TData]
```

Create a mutation instance.

**Parameters:**
- `options`: Mutation configuration

**Returns:** Mutation instance

---

#### clear

```python
def clear(self) -> None
```

Clear the entire cache and destroy all queries.

---

### Properties

#### cache

```python
@property
def cache(self) -> QueryCache
```

The underlying query cache.

---

## QueryClientConfig

Global defaults for all queries.

```python
@dataclass
class QueryClientConfig:
    stale_time: float = 0.0
    gc_time: float = 300.0
    retry: int = 3
    retry_delay: RetryDelayFn = default_retry_delay
    cache_max_size: int = 1000
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `stale_time` | `float` | `0.0` | Seconds before data is stale |
| `gc_time` | `float` | `300.0` | Seconds before unused query is collected |
| `retry` | `int` | `3` | Default retry attempts |
| `retry_delay` | `RetryDelayFn` | exponential | Retry delay function |
| `cache_max_size` | `int` | `1000` | Maximum queries to cache |

---

## QueryOptions

Configuration for a query.

```python
@dataclass
class QueryOptions(Generic[T]):
    query_key: QueryKey
    query_fn: QueryFn[T]
    stale_time: float = 0.0
    gc_time: float = 300.0
    refetch_interval: float | None = None
    retry: int = 3
    retry_delay: RetryDelayFn = default_retry_delay
    enabled: bool = True
    on_success: SuccessCallback[T] | None = None
    on_error: ErrorCallback | None = None
    on_settled: SettledCallback[T] | None = None
    select: SelectFn[T] | None = None
    placeholder_data: T | None = None
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `query_key` | `tuple[str, ...]` | Required | Unique identifier |
| `query_fn` | `Callable[[], Awaitable[T]]` | Required | Async fetch function |
| `stale_time` | `float` | `0.0` | Seconds before stale |
| `gc_time` | `float` | `300.0` | Seconds before GC |
| `refetch_interval` | `float \| None` | `None` | Auto-refetch interval |
| `retry` | `int` | `3` | Retry attempts |
| `retry_delay` | `RetryDelayFn` | exponential | Retry delay function |
| `enabled` | `bool` | `True` | Auto-fetch when observed |
| `on_success` | callback | `None` | Success callback |
| `on_error` | callback | `None` | Error callback |
| `on_settled` | callback | `None` | Completion callback |
| `select` | transform fn | `None` | Data transformer |
| `placeholder_data` | `T \| None` | `None` | Initial placeholder |

---

## MutationOptions

Configuration for a mutation.

```python
@dataclass
class MutationOptions(Generic[TInput, TData]):
    mutation_fn: MutationFn[TInput, TData]
    on_success: MutationSuccessCallback[TData, TInput] | None = None
    on_error: MutationErrorCallback[TInput] | None = None
    on_settled: MutationSettledCallback[TData, TInput] | None = None
    on_mutate: Callable[[TInput], Awaitable[Any] | Any] | None = None
    retry: int = 0
    retry_delay: RetryDelayFn = default_retry_delay
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `mutation_fn` | `Callable[[TInput], Awaitable[TData]]` | Required | Async mutation function |
| `on_success` | callback | `None` | Success callback |
| `on_error` | callback | `None` | Error callback |
| `on_settled` | callback | `None` | Completion callback |
| `on_mutate` | callback | `None` | Optimistic update callback |
| `retry` | `int` | `0` | Retry attempts |
| `retry_delay` | `RetryDelayFn` | exponential | Retry delay function |

---

## QueryState

Query state container.

```python
class QueryState(Generic[T, TError]):
    status: QueryStatus
    fetch_status: FetchStatus
    data: T | None
    error: TError | None
    data_updated_at: float | None
    error_updated_at: float | None
    fetch_failure_count: int
    fetch_failure_reason: TError | None
```

### Properties

| Property | Type | Description |
|----------|------|-------------|
| `is_idle` | `bool` | Query not triggered |
| `is_pending` | `bool` | First fetch in progress |
| `is_success` | `bool` | Fetch succeeded |
| `is_error` | `bool` | Fetch failed |
| `is_fetching` | `bool` | Currently fetching |
| `is_loading` | `bool` | Pending and fetching |
| `has_data` | `bool` | Data is not None |

---

## MutationState

Mutation state container.

```python
class MutationState(Generic[T, TError]):
    status: MutationStatus
    data: T | None
    error: TError | None
    submitted_at: float | None
    settled_at: float | None
```

### Properties

| Property | Type | Description |
|----------|------|-------------|
| `is_idle` | `bool` | Not executed |
| `is_pending` | `bool` | In progress |
| `is_success` | `bool` | Succeeded |
| `is_error` | `bool` | Failed |

---

## QueryObserver

Subscribes to query state updates.

### Methods

#### subscribe

```python
def subscribe(
    self,
    listener: Callable[[QueryState[T]], None],
) -> Callable[[], None]
```

Subscribe to state changes.

**Parameters:**
- `listener`: Callback invoked on state changes

**Returns:** Unsubscribe function

---

#### refetch

```python
async def refetch(self) -> QueryState[T]
```

Force a refetch.

**Returns:** Updated QueryState

---

### Properties

#### result

```python
@property
def result(self) -> QueryState[T]
```

Current query state with select transform applied.

---

## Mutation

Handles side effects.

### Methods

#### mutate

```python
async def mutate(self, input_data: TInput) -> TData
```

Execute the mutation.

**Parameters:**
- `input_data`: Input to pass to mutation function

**Returns:** Mutation result

**Raises:** Exception if all retries fail

---

#### subscribe

```python
def subscribe(
    self,
    listener: Callable[[MutationState[TData]], None],
) -> Callable[[], None]
```

Subscribe to state changes.

**Parameters:**
- `listener`: Callback invoked on state changes

**Returns:** Unsubscribe function

---

#### reset

```python
def reset(self) -> None
```

Reset mutation to idle state.

---

### Properties

#### state

```python
@property
def state(self) -> MutationState[TData]
```

Current mutation state.

---

## Enums

### QueryStatus

```python
class QueryStatus(Enum):
    IDLE = auto()      # Not triggered
    PENDING = auto()   # First fetch in progress
    SUCCESS = auto()   # Fetch succeeded
    ERROR = auto()     # Fetch failed
```

### FetchStatus

```python
class FetchStatus(Enum):
    IDLE = auto()      # Not fetching
    FETCHING = auto()  # Currently fetching
    PAUSED = auto()    # Paused (offline)
```

### MutationStatus

```python
class MutationStatus(Enum):
    IDLE = auto()      # Not executed
    PENDING = auto()   # In progress
    SUCCESS = auto()   # Succeeded
    ERROR = auto()     # Failed
```

---

## Type Aliases

```python
QueryKey = tuple[str, ...]
QueryFn = Callable[[], Awaitable[T]]
RetryDelayFn = Callable[[int], float]
SuccessCallback = Callable[[T], Any]
ErrorCallback = Callable[[Exception], Any]
SettledCallback = Callable[[T | None, Exception | None], Any]
MutationFn = Callable[[TInput], Awaitable[TData]]
MutationSuccessCallback = Callable[[TData, TInput], Any]
MutationErrorCallback = Callable[[Exception, TInput], Any]
MutationSettledCallback = Callable[[TData | None, Exception | None, TInput], Any]
SelectFn = Callable[[T], Any]
```

---

## Convenience Functions

### parallel_queries

```python
async def parallel_queries(
    client: QueryClient,
    *options_list: QueryOptions[Any],
) -> list[Any]
```

Execute multiple queries in parallel.

---

### dependent_query

```python
async def dependent_query(
    client: QueryClient,
    depends_on: QueryOptions[T],
    then: Callable[[T], QueryOptions[Any]],
) -> Any
```

Execute a query that depends on another.

---

### query (decorator)

```python
def query(
    client: QueryClient,
    key: QueryKey,
    *,
    stale_time: float = 0.0,
    gc_time: float = 300.0,
    retry: int = 3,
) -> Callable[[Callable[[], Awaitable[T]]], CachedQuery[T]]
```

Decorator that wraps an async function with caching.

---

## Helper Functions

### default_retry_delay

```python
def default_retry_delay(attempt: int) -> float
```

Default exponential backoff: 1s, 2s, 4s, 8s... up to 30s.

---

### hash_key

```python
def hash_key(key: QueryKey) -> str
```

Convert query key to string hash.

---

### partial_match

```python
def partial_match(filter_key: QueryKey, target_key: QueryKey) -> bool
```

Check if filter_key is a prefix of target_key.
