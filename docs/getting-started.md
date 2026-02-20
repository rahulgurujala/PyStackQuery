# Getting Started

PyStackQuery is a robust asynchronous state management and caching library for Python, inspired by TanStack Query. It manages the complexities of fetching, caching, and updating server state.

## Installation

```bash
uv add pystackquery
# or
pip install pystackquery
```

## Basic Concepts

### 1. The QueryClient
The `QueryClient` is the brain of your application. It manages the cache and coordinates all background tasks.

```python
from pystackquery import QueryClient

client = QueryClient()
```

### 2. Fetching Data
Use `fetch_query` for one-time or manual fetches. It handles the "Stale-While-Revalidate" logic automatically.

```python
from pystackquery import QueryOptions

async def get_data():
    # Your async fetch logic here
    return {"id": 1, "value": "Hello"}

data = await client.fetch_query(
    QueryOptions(query_key=("example",), query_fn=get_data)
)
```

### 3. Reactive Observers
Observers allow you to subscribe to data changes. This is ideal for GUI or real-time applications.

```python
observer = client.watch(QueryOptions(query_key=("example",), query_fn=get_data))

# Subscribing is synchronous
unsubscribe = observer.subscribe(lambda state: print(state.data))

# ... later
unsubscribe()
```

## Configuring Defaults
You can set global behavior for all queries via `QueryClientConfig`.

```python
from pystackquery import QueryClient, QueryClientConfig

config = QueryClientConfig(
    stale_time=60.0,  # Data is fresh for 60 seconds
    retry=3           # Automatic retries on failure
)
client = QueryClient(config)
```
