# Framework Integrations

This guide shows how to integrate PyStackQuery with popular Python frameworks and environments.

## FastAPI

FastAPI is async-native, making PyStackQuery integration straightforward.

### Setup

```python
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends
from pystackquery import QueryClient, QueryOptions, QueryClientConfig

# Create a global client instance
client = QueryClient(
    QueryClientConfig(
        stale_time=30.0,      # Cache responses for 30 seconds
        gc_time=300.0,        # Keep unused queries for 5 minutes
        cache_max_size=1000,  # Limit memory usage
    )
)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: client is ready
    yield
    # Shutdown: clear cache
    client.clear()

app = FastAPI(lifespan=lifespan)
```

### Basic Usage - Caching External API Calls

```python
import httpx

async def fetch_weather(city: str) -> dict:
    async with httpx.AsyncClient() as http:
        response = await http.get(f"https://api.weather.com/{city}")
        return response.json()

@app.get("/weather/{city}")
async def get_weather(city: str):
    # First request hits the API, subsequent requests return cached data
    weather = await client.fetch_query(
        QueryOptions(
            query_key=("weather", city),
            query_fn=lambda: fetch_weather(city),
            stale_time=60.0  # Weather data fresh for 1 minute
        )
    )
    return weather
```

### Benefits for FastAPI

1. **Reduced External API Calls**: Multiple concurrent requests for the same data make only one external call
2. **Lower Latency**: Cached responses return instantly
3. **Rate Limit Protection**: Fewer outbound requests means less risk of hitting rate limits
4. **Automatic Retry**: Transient failures are handled automatically

### Request Deduplication in Action

```python
@app.get("/user/{user_id}")
async def get_user(user_id: str):
    # If 100 requests hit this endpoint simultaneously for the same user,
    # only ONE database/API call is made. All 100 requests get the same result.
    return await client.fetch_query(
        QueryOptions(
            query_key=("user", user_id),
            query_fn=lambda: fetch_user_from_db(user_id)
        )
    )
```

### Cache Invalidation After Updates

```python
from pystackquery import MutationOptions

@app.put("/user/{user_id}")
async def update_user(user_id: str, data: dict):
    mutation = client.mutation(
        MutationOptions(
            mutation_fn=lambda d: update_user_in_db(user_id, d),
            on_success=lambda result, _: asyncio.create_task(
                client.invalidate_queries(("user", user_id))
            )
        )
    )
    return await mutation.mutate(data)
```

### Dependency Injection Pattern

```python
from typing import Annotated

def get_query_client() -> QueryClient:
    return client

QueryClientDep = Annotated[QueryClient, Depends(get_query_client)]

@app.get("/products")
async def get_products(qc: QueryClientDep):
    return await qc.fetch_query(
        QueryOptions(("products",), fetch_products)
    )
```

---

## Tkinter

Tkinter runs a synchronous event loop, so you need to integrate asyncio carefully.

### Setup with asyncio

```python
import asyncio
import tkinter as tk
from pystackquery import QueryClient, QueryOptions

client = QueryClient()

class AsyncTk(tk.Tk):
    """Tkinter app with asyncio integration."""

    def __init__(self):
        super().__init__()
        self.loop = asyncio.new_event_loop()

    def run_async(self, coro):
        """Run a coroutine from Tkinter callbacks."""
        asyncio.run_coroutine_threadsafe(coro, self.loop)

    def mainloop(self):
        """Run both Tkinter and asyncio event loops."""
        import threading

        def run_asyncio():
            asyncio.set_event_loop(self.loop)
            self.loop.run_forever()

        thread = threading.Thread(target=run_asyncio, daemon=True)
        thread.start()
        super().mainloop()
        self.loop.call_soon_threadsafe(self.loop.stop)
```

### Fetching Data Without Blocking

```python
import httpx

async def fetch_data() -> dict:
    async with httpx.AsyncClient() as http:
        response = await http.get("https://api.example.com/data")
        return response.json()

class DataApp(AsyncTk):
    def __init__(self):
        super().__init__()
        self.title("Data Viewer")

        self.label = tk.Label(self, text="Click to load data")
        self.label.pack(pady=20)

        self.button = tk.Button(self, text="Load Data", command=self.load_data)
        self.button.pack()

    def load_data(self):
        self.label.config(text="Loading...")
        self.run_async(self._fetch_and_display())

    async def _fetch_and_display(self):
        try:
            # Cached fetch - fast on subsequent clicks
            data = await client.fetch_query(
                QueryOptions(
                    query_key=("data",),
                    query_fn=fetch_data,
                    stale_time=60.0
                )
            )
            # Update UI from async context
            self.after(0, lambda: self.label.config(text=f"Got: {data}"))
        except Exception as e:
            self.after(0, lambda: self.label.config(text=f"Error: {e}"))

if __name__ == "__main__":
    app = DataApp()
    app.mainloop()
```

### Benefits for Tkinter

1. **Non-Blocking Fetches**: Network calls don't freeze the GUI
2. **Instant Cached Responses**: Previously fetched data returns immediately
3. **Automatic Retry**: Flaky network connections are handled gracefully

---

## Textual (TUI Applications)

Textual is async-native, making integration seamless.

### Basic Setup

```python
from textual.app import App, ComposeResult
from textual.widgets import Static, Button
from pystackquery import QueryClient, QueryOptions

client = QueryClient()

class DataViewer(App):
    CSS = """
    Screen {
        layout: vertical;
    }
    #status {
        height: 3;
        content-align: center middle;
    }
    """

    def compose(self) -> ComposeResult:
        yield Static("Click to load", id="status")
        yield Button("Load Data", id="load")

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        status = self.query_one("#status", Static)
        status.update("Loading...")

        try:
            data = await client.fetch_query(
                QueryOptions(
                    query_key=("items",),
                    query_fn=fetch_items,
                    stale_time=30.0
                )
            )
            status.update(f"Loaded {len(data)} items")
        except Exception as e:
            status.update(f"Error: {e}")

if __name__ == "__main__":
    app = DataViewer()
    app.run()
```

### Reactive Updates with Observers

```python
from textual.app import App, ComposeResult
from textual.widgets import Static
from pystackquery import QueryClient, QueryOptions

client = QueryClient()

class LiveDataApp(App):
    def compose(self) -> ComposeResult:
        yield Static("Waiting for data...", id="display")

    async def on_mount(self) -> None:
        # Start observing data
        observer = client.watch(
            QueryOptions(
                query_key=("live-data",),
                query_fn=fetch_live_data,
                refetch_interval=5.0  # Refresh every 5 seconds
            )
        )

        display = self.query_one("#display", Static)

        def on_update(state):
            if state.is_loading:
                self.call_from_thread(display.update, "Loading...")
            elif state.is_error:
                self.call_from_thread(display.update, f"Error: {state.error}")
            else:
                self.call_from_thread(display.update, f"Data: {state.data}")

        self.unsubscribe = observer.subscribe(on_update)

    def on_unmount(self) -> None:
        if hasattr(self, "unsubscribe"):
            self.unsubscribe()
```

---

## CLI Applications (Click/Typer)

For command-line tools that fetch external data.

### With Typer (Recommended)

```python
import asyncio
import typer
from pystackquery import QueryClient, QueryOptions

app = typer.Typer()
client = QueryClient()

async def fetch_package_info(name: str) -> dict:
    import httpx
    async with httpx.AsyncClient() as http:
        response = await http.get(f"https://pypi.org/pypi/{name}/json")
        response.raise_for_status()
        return response.json()

@app.command()
def info(package: str):
    """Get package information from PyPI."""

    async def run():
        data = await client.fetch_query(
            QueryOptions(
                query_key=("pypi", package),
                query_fn=lambda: fetch_package_info(package),
                stale_time=300.0  # Cache for 5 minutes
            )
        )
        return data

    result = asyncio.run(run())
    typer.echo(f"Name: {result['info']['name']}")
    typer.echo(f"Version: {result['info']['version']}")
    typer.echo(f"Summary: {result['info']['summary']}")

@app.command()
def compare(packages: list[str]):
    """Compare multiple packages."""

    async def run():
        from pystackquery import parallel_queries
        results = await parallel_queries(
            client,
            *[QueryOptions(("pypi", p), lambda p=p: fetch_package_info(p)) for p in packages]
        )
        return results

    results = asyncio.run(run())
    for pkg, data in zip(packages, results):
        typer.echo(f"{pkg}: {data['info']['version']}")

if __name__ == "__main__":
    app()
```

### Benefits for CLI Tools

1. **Faster Repeated Commands**: Running the same command twice uses cached data
2. **Parallel Fetching**: Fetch multiple resources simultaneously
3. **Graceful Error Handling**: Automatic retry on transient failures

---

## Background Services / Workers

For long-running services that periodically fetch or process data.

### Periodic Data Fetcher

```python
import asyncio
from pystackquery import QueryClient, QueryOptions

client = QueryClient()

async def fetch_metrics() -> dict:
    # Fetch from monitoring API, database, etc.
    ...

async def process_metrics(data: dict):
    # Process the fetched data
    ...

async def run_worker():
    """Background worker that processes metrics."""
    while True:
        try:
            # Fetch with caching - avoids hammering the source
            metrics = await client.fetch_query(
                QueryOptions(
                    query_key=("metrics", "current"),
                    query_fn=fetch_metrics,
                    stale_time=10.0  # Only fetch if data is older than 10 seconds
                )
            )
            await process_metrics(metrics)
        except Exception as e:
            print(f"Worker error: {e}")

        await asyncio.sleep(5)  # Check every 5 seconds

if __name__ == "__main__":
    asyncio.run(run_worker())
```

### Multi-Source Aggregator

```python
async def aggregate_from_sources():
    """Fetch from multiple sources and aggregate."""
    from pystackquery import parallel_queries

    results = await parallel_queries(
        client,
        QueryOptions(("source", "a"), fetch_from_source_a, stale_time=60.0),
        QueryOptions(("source", "b"), fetch_from_source_b, stale_time=60.0),
        QueryOptions(("source", "c"), fetch_from_source_c, stale_time=60.0),
    )

    # All sources fetched in parallel, results cached
    source_a, source_b, source_c = results
    return combine_results(source_a, source_b, source_c)
```

---

## Jupyter Notebooks

Interactive data analysis with external API caching.

### Setup

```python
# Cell 1: Setup
from pystackquery import QueryClient, QueryOptions
import httpx

client = QueryClient()

async def fetch_dataset(dataset_id: str) -> dict:
    async with httpx.AsyncClient() as http:
        response = await http.get(f"https://api.data.gov/{dataset_id}")
        return response.json()
```

### Fetching Data

```python
# Cell 2: Fetch data (first run hits API)
data = await client.fetch_query(
    QueryOptions(
        query_key=("dataset", "population-2023"),
        query_fn=lambda: fetch_dataset("population-2023"),
        stale_time=3600.0  # Cache for 1 hour
    )
)
print(f"Fetched {len(data['records'])} records")
```

```python
# Cell 3: Run again - instant from cache
# Re-running this cell is instant, no network delay
data = await client.fetch_query(
    QueryOptions(
        query_key=("dataset", "population-2023"),
        query_fn=lambda: fetch_dataset("population-2023"),
        stale_time=3600.0
    )
)
```

### Benefits for Notebooks

1. **Iteration Speed**: Re-running cells doesn't re-fetch data
2. **Notebook Restarts**: Data survives kernel restarts within stale_time
3. **Multiple Datasets**: Easily fetch and cache multiple datasets

### Force Refresh When Needed

```python
# Cell: Force refresh
await client.invalidate_queries(("dataset", "population-2023"))
# Next fetch will hit the API
```

---

## WebSocket Servers

Real-time applications with shared cached state.

### With websockets Library

```python
import asyncio
import websockets
import json
from pystackquery import QueryClient, QueryOptions

client = QueryClient()
connected_clients = set()

async def fetch_latest_data() -> dict:
    # Fetch from your data source
    ...

async def broadcast_updates():
    """Background task that broadcasts data changes."""
    observer = client.watch(
        QueryOptions(
            query_key=("live-data",),
            query_fn=fetch_latest_data,
            refetch_interval=5.0
        )
    )

    def on_update(state):
        if state.is_success and connected_clients:
            message = json.dumps({"type": "data", "payload": state.data})
            asyncio.create_task(
                asyncio.gather(*[ws.send(message) for ws in connected_clients])
            )

    observer.subscribe(on_update)

async def handler(websocket):
    connected_clients.add(websocket)
    try:
        # Send current cached data immediately
        current = client.get_query_data(("live-data",))
        if current:
            await websocket.send(json.dumps({"type": "data", "payload": current}))

        async for message in websocket:
            # Handle incoming messages
            pass
    finally:
        connected_clients.remove(websocket)

async def main():
    asyncio.create_task(broadcast_updates())
    async with websockets.serve(handler, "localhost", 8765):
        await asyncio.Future()  # Run forever

asyncio.run(main())
```

---

## Performance Considerations

### Memory Usage

Each cached query uses memory. Configure limits appropriately:

```python
# Memory-constrained environment
client = QueryClient(QueryClientConfig(
    cache_max_size=100,  # Fewer cached queries
    gc_time=60.0,        # Faster garbage collection
))

# Memory-rich server
client = QueryClient(QueryClientConfig(
    cache_max_size=10000,
    gc_time=600.0,
))
```

### When to Use PyStackQuery

**Good fit:**
- External API calls (rate-limited, slow, or costly)
- Database queries for read-heavy workloads
- Shared data across multiple consumers
- Data that doesn't change every request

**Not needed:**
- Simple in-memory lookups
- Write-heavy operations
- Data that must be real-time (use direct queries)
- Single-use data that won't be re-requested

### Measuring Impact

```python
import time

async def measure_fetch():
    start = time.perf_counter()
    await client.fetch_query(opts)
    elapsed = time.perf_counter() - start
    print(f"Fetch took {elapsed*1000:.2f}ms")

# First call: includes network time
await measure_fetch()  # ~200ms

# Second call: from cache
await measure_fetch()  # ~0.1ms
```
