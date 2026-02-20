# Query Options

The `QueryOptions` object is the configuration heart of every request.

## Core Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `query_key` | `tuple` | **Required** | The unique identifier for the data. |
| `query_fn` | `coroutine` | **Required** | The async function responsible for data retrieval. |
| `stale_time` | `float` | `0.0` | How long (seconds) data stays fresh. |
| `gc_time` | `float` | `300.0` | Inactivity timeout before purging from cache. |

## Refetching & Polling

### refetch_interval
Enables automatic background polling. This only occurs if the query has at least one active observer.

```python
QueryOptions(..., refetch_interval=10.0) # Poll every 10s
```

## Transformation & Placeholders

### select
Transform data before it reaches the observer. The transformed value is not cached; only the raw result from `query_fn` is stored.

```python
QueryOptions(..., select=lambda data: data["nested"]["field"])
```

### placeholder_data
Used to provide an immediate value to observers while the first fetch is in flight.

```python
QueryOptions(..., placeholder_data={"status": "loading..."})
```

## Advanced Callbacks

*   **on_success:** Triggered on a successful network fetch.
*   **on_error:** Triggered after all retry attempts fail.
*   **on_settled:** Triggered regardless of success or failure.
