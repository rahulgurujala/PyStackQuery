# Observers

Observers are the reactive core of PyStackQuery. While `fetch_query` is a one-time operation, an observer links your code to a query's lifecycle, receiving updates whenever the state changes.

## Usage

```python
from pystackquery import QueryClient, QueryOptions

client = QueryClient()
opts = QueryOptions(query_key=("user", "123"), query_fn=fetch_user)

# 1. Create the observer
observer = client.watch(opts)

# 2. Subscribe (Synchronous)
# The listener is called immediately with current data, then again on any change.
unsubscribe = observer.subscribe(lambda state: print(state.data))

# 3. Cleanup
unsubscribe()
```

## How Observers Work

When you subscribe to an observer:
1. It connects to the underlying `Query` instance (creating it if necessary).
2. It immediately pushes the current state to your listener.
3. If the data is stale, the library triggers a background refetch.
4. Any state transition (IDLE -> PENDING -> SUCCESS) is broadcast to all listeners.

## Shared Queries

Observers are extremely efficient. If you have five UI components watching the same `("users",)` key, PyStackQuery only manages **one** internal `Query` instance and performs **one** network request. All five observers will be notified simultaneously.

## Automatic Polling

You can turn any query into a live-updating stream using `refetch_interval`:

```python
observer = client.watch(
    QueryOptions(
        query_key=("metrics",),
        query_fn=fetch_stats,
        refetch_interval=5.0  # Poll every 5 seconds
    )
)

# Refetching only happens while there is at least one active subscriber.
unsubscribe = observer.subscribe(my_listener)
```

## Data Selection (Transformation)

You can transform data at the observer level using `select`. This is useful for large datasets where a component only needs a specific field.

```python
observer = client.watch(
    QueryOptions(
        query_key=("user", "1"),
        query_fn=fetch_user,
        select=lambda user: user["email"]  # Only notify me about the email
    )
)

# state.data will be a string (the email) instead of the full user dict.
observer.subscribe(lambda state: update_email_ui(state.data))
```

## Lifecycle Rules

*   **Always Unsubscribe:** Failing to call the `unsubscribe` function can lead to memory leaks and unnecessary background fetching.
*   **Synchronous Callbacks:** Observer listeners are called synchronously. If you need to perform heavy processing in a listener, offload it to a task: `asyncio.create_task(heavy_work(state.data))`.
