# Observers

Observers provide reactive updates. Instead of fetching once, you subscribe to a query and receive updates whenever the state changes.

## Why Use Observers?

With `fetch_query`, you get data once:

```python
user = await client.fetch_query(opts)  # One-time fetch
```

With observers, you get continuous updates:

```python
observer = client.watch(opts)
observer.subscribe(lambda state: print(state.data))  # Called on every change
```

Observers are useful when:
- Data changes frequently
- Multiple parts of your application need the same data
- You want automatic refetching at intervals
- You need loading/error states in real-time

## Basic Usage

```python
from pystackquery import QueryClient, QueryOptions

client = QueryClient()

# Create an observer
observer = client.watch(
    QueryOptions(
        query_key=("user", "123"),
        query_fn=lambda: fetch_user("123")
    )
)

# Subscribe to updates
def on_state_change(state):
    if state.is_loading:
        print("Loading...")
    elif state.is_error:
        print(f"Error: {state.error}")
    elif state.is_success:
        print(f"Data: {state.data}")

unsubscribe = observer.subscribe(on_state_change)

# ... later, when you're done
unsubscribe()
```

## How Observers Work

1. **Create**: `client.watch(options)` creates an observer
2. **Subscribe**: `observer.subscribe(callback)` starts listening
3. **Fetch**: If data is stale, a fetch is triggered automatically
4. **Update**: Your callback is called with the new state
5. **Unsubscribe**: Call the returned function to stop listening

```
watch() -> subscribe() -> fetch triggered -> callback called -> ... -> unsubscribe()
```

## QueryState Properties

The callback receives a `QueryState` object:

```python
def on_state_change(state):
    # Status
    state.status         # QueryStatus enum
    state.is_idle        # True if never fetched
    state.is_pending     # True if first fetch in progress
    state.is_success     # True if data fetched successfully
    state.is_error       # True if fetch failed

    # Fetch status (orthogonal to main status)
    state.fetch_status   # FetchStatus enum
    state.is_fetching    # True if currently fetching
    state.is_loading     # True if pending AND fetching (first load)

    # Data
    state.data           # The data (or None)
    state.has_data       # True if data is not None
    state.error          # The error (or None)

    # Timestamps
    state.data_updated_at    # When data was last updated
    state.error_updated_at   # When error occurred

    # Failure tracking
    state.fetch_failure_count   # Number of consecutive failures
    state.fetch_failure_reason  # The last failure reason
```

## State Flow

A query goes through these states:

```
IDLE -> PENDING (fetching) -> SUCCESS
                          \-> ERROR
```

When refetching after success:
```
SUCCESS -> SUCCESS (fetching in background) -> SUCCESS (updated)
```

## Multiple Subscribers

Multiple callbacks can subscribe to the same observer:

```python
observer = client.watch(opts)

def update_header(state):
    print(f"Header: {state.data}")

def update_sidebar(state):
    print(f"Sidebar: {state.data}")

unsub1 = observer.subscribe(update_header)
unsub2 = observer.subscribe(update_sidebar)

# Both callbacks receive updates
```

## Shared Queries

Observers for the same query key share the underlying query:

```python
# Both watch the same query - only ONE fetch happens
observer1 = client.watch(QueryOptions(("user", "123"), fetch_user))
observer2 = client.watch(QueryOptions(("user", "123"), fetch_user))

observer1.subscribe(callback1)
observer2.subscribe(callback2)

# Both callbacks receive updates from the same fetch
```

## Automatic Refetching

With `refetch_interval`, observers trigger periodic refetches:

```python
observer = client.watch(
    QueryOptions(
        query_key=("stock", "AAPL"),
        query_fn=lambda: fetch_stock_price("AAPL"),
        refetch_interval=5.0  # Refetch every 5 seconds
    )
)

def on_price_update(state):
    if state.data:
        print(f"Price: ${state.data['price']}")

observer.subscribe(on_price_update)
# Callback is called every 5 seconds with fresh data
```

Refetching stops when all subscribers unsubscribe.

## Manual Refetch

Force a refetch regardless of stale state:

```python
observer = client.watch(opts)
observer.subscribe(callback)

# Force immediate refetch
await observer.refetch()
```

## Current Result

Access the current state without subscribing:

```python
observer = client.watch(opts)
observer.subscribe(callback)

# Get current state
current = observer.result
print(f"Current data: {current.data}")
```

## Data Transformation with Select

Transform data before it reaches subscribers:

```python
def extract_user_name(user_data):
    return user_data["name"]

observer = client.watch(
    QueryOptions(
        query_key=("user", "123"),
        query_fn=lambda: fetch_user("123"),
        select=extract_user_name  # Transform the data
    )
)

def on_update(state):
    # state.data is now just the name, not the full user object
    print(f"Name: {state.data}")

observer.subscribe(on_update)
```

**Note:** The full data is still cached. The transformation only applies when reading.

## Enabled Flag

Control whether the observer fetches automatically:

```python
user_id = get_current_user()  # Might be None

observer = client.watch(
    QueryOptions(
        query_key=("user", str(user_id or "")),
        query_fn=lambda: fetch_user(user_id),
        enabled=user_id is not None  # Only fetch if we have a user ID
    )
)

observer.subscribe(callback)
# If enabled=False, no fetch happens until enabled becomes True
```

## Placeholder Data

Show something immediately while loading:

```python
observer = client.watch(
    QueryOptions(
        query_key=("user", "123"),
        query_fn=lambda: fetch_user("123"),
        placeholder_data={"name": "Loading...", "email": "..."}
    )
)

def on_update(state):
    # First call: state.data is placeholder
    # Later call: state.data is real data
    print(f"Name: {state.data['name']}")

observer.subscribe(on_update)
```

## Lifecycle Example

```python
import asyncio
from pystackquery import QueryClient, QueryOptions, QueryStatus

client = QueryClient()

async def main():
    observer = client.watch(
        QueryOptions(
            query_key=("data",),
            query_fn=fetch_data,
            stale_time=60.0
        )
    )

    updates = []

    def track_updates(state):
        updates.append(state.status.name)
        print(f"Status: {state.status.name}, Data: {state.data}")

    unsubscribe = observer.subscribe(track_updates)

    # Wait for fetch to complete
    await asyncio.sleep(2)

    # Unsubscribe
    unsubscribe()

    print(f"Updates received: {updates}")
    # ['PENDING', 'SUCCESS'] or similar

asyncio.run(main())
```

## Integration Patterns

### Generic Subscription Pattern

```python
class DataSubscriber:
    """Base pattern for any component that needs reactive data."""

    def __init__(self, client, query_options):
        self.observer = client.watch(query_options)
        self.unsubscribe = None

    def start(self):
        """Start listening for updates."""
        self.unsubscribe = self.observer.subscribe(self.on_state_change)

    def stop(self):
        """Stop listening and clean up."""
        if self.unsubscribe:
            self.unsubscribe()

    def on_state_change(self, state):
        self.handle_update(state)

    def handle_update(self, state):
        if state.is_loading:
            print("Loading...")
        elif state.is_error:
            print(f"Error: {state.error}")
        else:
            print(f"Data: {state.data}")
```

### Long-Running Service Pattern

```python
# Background service that reacts to data changes
class DataMonitor:
    def __init__(self, client):
        self.client = client
        self.observers = []

    async def monitor(self, query_options, handler):
        """Monitor a query and call handler on changes."""
        observer = self.client.watch(query_options)
        unsub = observer.subscribe(handler)
        self.observers.append(unsub)

    def stop_all(self):
        for unsub in self.observers:
            unsub()
        self.observers.clear()
```

## Best Practices

### 1. Always Unsubscribe

```python
unsub = observer.subscribe(callback)
# ... later
unsub()  # Prevents memory leaks
```

### 2. Handle All States

```python
def on_update(state):
    if state.is_loading:
        print("Loading...")
    elif state.is_error:
        logging.error(f"Failed: {state.error}")
    elif state.is_success:
        process_data(state.data)
```

### 3. Use refetch_interval Sparingly

Only use for data that genuinely needs live updates. Unnecessary refetching wastes resources.

### 4. Keep Callbacks Fast

Callbacks block subsequent updates. Do heavy work asynchronously:

```python
def on_update(state):
    # Fast: schedule work, don't block
    asyncio.create_task(heavy_processing(state.data))
```
