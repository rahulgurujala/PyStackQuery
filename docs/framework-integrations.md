# Framework Integrations

PyStackQuery is framework-agnostic. Its dual-tier caching logic and reactive observers integrate easily into any async-capable environment.

## FastAPI

PyStackQuery is ideal for FastAPI because it deduplicates concurrent requests to expensive external APIs.

### Setup

```python
from contextlib import asynccontextmanager
from fastapi import FastAPI
from pystackquery import QueryClient, QueryClientConfig

client = QueryClient(QueryClientConfig(stale_time=30.0))

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup logic here
    yield
    client.clear()

app = FastAPI(lifespan=lifespan)
```

### Usage

```python
@app.get("/weather/{city}")
async def get_weather(city: str):
    return await client.fetch_query(
        QueryOptions(query_key=("weather", city), query_fn=lambda: fetch_api(city))
    )
```

---

## Tkinter (Desktop GUI)

Tkinter runs a synchronous loop. To use PyStackQuery, run the `asyncio` loop in a background thread and use observers to update the UI safely.

### Implementation

```python
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.observer = client.watch(opts)
        
        # Subscribe is synchronous, perfect for GUI setup
        self.unsub = self.observer.subscribe(self.on_data_change)

    def on_data_change(self, state):
        # Use .after() to ensure UI updates happen on the main thread
        if state.is_success:
            self.after(0, lambda: self.label.config(text=state.data))
```

---

## Textual (TUI)

Textual is built on `asyncio`, making it a native fit for PyStackQuery observers.

```python
class DataWidget(Static):
    def on_mount(self):
        self.observer = client.watch(opts)
        # Sync subscribe allows mounting without complex await logic
        self.unsub = self.observer.subscribe(self.update_ui)

    def update_ui(self, state):
        if state.is_success:
            self.update(state.data)
```

---

## Deployment Recommendations

### Memory Management
In high-traffic environments, adjust `cache_max_size` and `gc_time` to prevent memory bloat.

### Persistent Storage
Use the `StorageBackend` Protocol to connect PyStackQuery to Redis (distributed) or SQLite (local). This ensures that your cache survives server reloads and scales across multiple worker processes.
