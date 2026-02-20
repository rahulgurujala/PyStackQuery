"""
Background Worker with PyStackQuery

A long-running service demonstrating:
- Periodic data fetching with caching
- Stale-while-revalidate for continuous operation
- Observers for monitoring
- Multi-source aggregation
- Graceful pause/resume

Run: python -m examples.background_worker
"""

from __future__ import annotations

import asyncio
import signal
import ssl
import time
from collections.abc import Callable
from typing import Any, cast
from urllib.request import Request, urlopen

from pystackquery import (
    QueryClient,
    QueryClientConfig,
    QueryOptions,
    QueryStatus,
    parallel_queries,
)

# ─────────────────────────────────────────────────────────────────────────────
# Configuration
# ─────────────────────────────────────────────────────────────────────────────

SSL_CTX = ssl.create_default_context()
SSL_CTX.check_hostname = False
SSL_CTX.verify_mode = ssl.CERT_NONE

BASE_URL = "https://dummyjson.com"

# Worker configuration
POLL_INTERVAL = 5.0  # Check for new data every 5 seconds
STALE_TIME = 10.0  # Data considered stale after 10 seconds

# Global client
client = QueryClient(
    QueryClientConfig(
        stale_time=STALE_TIME,
        gc_time=300.0,
        retry=3,
    )
)

# Metrics
metrics: dict[str, float] = {
    "fetches": 0,
    "cache_hits": 0,
    "errors": 0,
    "aggregations": 0,
    "start_time": time.time(),
}

# Control flag
running = True


# ─────────────────────────────────────────────────────────────────────────────
# HTTP Utilities
# ─────────────────────────────────────────────────────────────────────────────


async def http_get(url: str) -> dict[str, Any]:
    """Async HTTP GET."""

    def _fetch() -> dict[str, Any]:
        req = Request(url, headers={"User-Agent": "PyStackQuery-Worker/1.0"})
        with urlopen(req, context=SSL_CTX, timeout=10) as resp:
            data = resp.read().decode()
            return cast(dict[str, Any], json.loads(data))

    import json
    return await asyncio.to_thread(_fetch)


# ─────────────────────────────────────────────────────────────────────────────
# Data Sources
# ─────────────────────────────────────────────────────────────────────────────


async def fetch_users_data() -> dict[str, Any]:
    """Fetch user statistics."""
    metrics["fetches"] += 1
    log("  [Source 1] Fetching users...")
    data = await http_get(f"{BASE_URL}/users?limit=5&select=id,firstName,age")
    return {
        "source": "users",
        "count": len(data.get("users", [])),
        "data": data.get("users", []),
        "timestamp": time.time(),
    }


async def fetch_products_data() -> dict[str, Any]:
    """Fetch product statistics."""
    metrics["fetches"] += 1
    log("  [Source 2] Fetching products...")
    data = await http_get(f"{BASE_URL}/products?limit=5&select=id,title,price")
    return {
        "source": "products",
        "count": len(data.get("products", [])),
        "data": data.get("products", []),
        "timestamp": time.time(),
    }


async def fetch_posts_data() -> dict[str, Any]:
    """Fetch post statistics."""
    metrics["fetches"] += 1
    log("  [Source 3] Fetching posts...")
    data = await http_get(f"{BASE_URL}/posts?limit=5&select=id,title,reactions")
    return {
        "source": "posts",
        "count": len(data.get("posts", [])),
        "data": data.get("posts", []),
        "timestamp": time.time(),
    }


# ─────────────────────────────────────────────────────────────────────────────
# Logging
# ─────────────────────────────────────────────────────────────────────────────


def log(msg: str) -> None:
    """Print with timestamp."""
    ts = time.strftime("%H:%M:%S")
    print(f"[{ts}] {msg}")


def log_metrics() -> None:
    """Print current metrics."""
    uptime = time.time() - metrics["start_time"]
    log(
        f"Metrics: fetches={int(metrics['fetches'])}, "
        f"cache_hits={int(metrics['cache_hits'])}, "
        f"errors={int(metrics['errors'])}, "
        f"aggregations={int(metrics['aggregations'])}, "
        f"uptime={uptime:.0f}s"
    )


# ─────────────────────────────────────────────────────────────────────────────
# Worker Tasks
# ─────────────────────────────────────────────────────────────────────────────


async def aggregate_data() -> dict[str, Any]:
    """Aggregate data from all sources."""
    results = await parallel_queries(
        client,
        QueryOptions(("source", "users"), fetch_users_data, stale_time=STALE_TIME),
        QueryOptions(
            ("source", "products"), fetch_products_data, stale_time=STALE_TIME
        ),
        QueryOptions(("source", "posts"), fetch_posts_data, stale_time=STALE_TIME),
    )

    users = cast(dict[str, Any], results[0])
    products = cast(dict[str, Any], results[1])
    posts = cast(dict[str, Any], results[2])

    metrics["aggregations"] += 1

    return {
        "users": users,
        "products": products,
        "posts": posts,
        "aggregated_at": time.time(),
        "total_items": (
            int(users["count"]) + int(products["count"]) + int(posts["count"])
        ),
    }


async def process_aggregation(data: dict[str, Any]) -> None:
    """Process aggregated data (simulated)."""
    total = data["total_items"]
    log(f"  Processed {total} items from 3 sources")

    # Simulate some processing
    if data["users"]["data"]:
        ages = [u.get("age", 0) for u in data["users"]["data"]]
        avg_age = sum(ages) / len(ages)
        log(f"    Users avg age: {avg_age:.1f}")

    if data["products"]["data"]:
        prices = [p.get("price", 0) for p in data["products"]["data"]]
        avg_price = sum(prices) / len(prices)
        log(f"    Products avg price: ${avg_price:.2f}")


async def data_aggregation_worker() -> None:
    """Main aggregation worker loop."""
    log("Starting data aggregation worker...")

    while running:
        try:
            log("─" * 40)
            log("Aggregation cycle starting...")

            start = time.perf_counter()
            data = await aggregate_data()
            elapsed = (time.perf_counter() - start) * 1000

            log(f"  Aggregation completed in {elapsed:.1f}ms")
            await process_aggregation(data)
            log_metrics()

        except Exception as e:
            metrics["errors"] += 1
            log(f"  ERROR: {e}")

        await asyncio.sleep(POLL_INTERVAL)


# ─────────────────────────────────────────────────────────────────────────────
# Observer-based Monitoring
# ─────────────────────────────────────────────────────────────────────────────


async def start_observers() -> list[Callable[[], None]]:
    """Start observers to monitor data changes."""
    unsubscribes: list[Callable[[], None]] = []

    def create_observer(
        name: str,
        query_key: tuple[str, ...],
        fetch_fn: Callable[[], Any],
    ) -> None:
        """Create and subscribe to an observer."""
        observer = client.watch(
            QueryOptions(
                query_key=query_key,
                query_fn=fetch_fn,
                refetch_interval=POLL_INTERVAL * 2,
            )
        )

        def on_change(state: Any) -> None:
            if state.status == QueryStatus.SUCCESS and state.data:
                count = state.data.get("count", 0)
                log(f"  [Observer:{name}] Data updated: {count} items")
            elif state.status == QueryStatus.ERROR:
                log(f"  [Observer:{name}] Error: {state.error}")

        unsub = observer.subscribe(on_change)
        unsubscribes.append(unsub)
        log(f"Observer started: {name}")

    create_observer("users", ("source", "users"), fetch_users_data)
    create_observer("products", ("source", "products"), fetch_products_data)

    return unsubscribes


# ─────────────────────────────────────────────────────────────────────────────
# Health Check Worker
# ─────────────────────────────────────────────────────────────────────────────


async def health_check_worker() -> None:
    """Periodic health check."""
    log("Starting health check worker...")

    async def check_api_health() -> dict[str, Any]:
        """Check if API is responsive."""
        start = time.perf_counter()
        await http_get(f"{BASE_URL}/test")
        latency = (time.perf_counter() - start) * 1000
        return {"healthy": True, "latency_ms": latency, "checked_at": time.time()}

    while running:
        try:
            health = await client.fetch_query(
                QueryOptions(
                    query_key=("health",),
                    query_fn=check_api_health,
                    stale_time=15.0,
                )
            )

            if health["healthy"]:
                metrics["cache_hits"] += 1

        except Exception as e:
            log(f"  Health check failed: {e}")
            metrics["errors"] += 1

        await asyncio.sleep(10)


# ─────────────────────────────────────────────────────────────────────────────
# Cache Management Worker
# ─────────────────────────────────────────────────────────────────────────────


async def cache_management_worker() -> None:
    """Periodic cache management."""
    log("Starting cache management worker...")

    while running:
        await asyncio.sleep(30)

        log("  Prefetching data for next cycle...")
        await client.prefetch_query(QueryOptions(("source", "users"), fetch_users_data))
        await client.prefetch_query(
            QueryOptions(("source", "products"), fetch_products_data)
        )

        log(f"  Cache size: {len(client.cache)} queries")


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────


async def main() -> None:
    """Run the background worker."""
    global running

    log("=" * 50)
    log("  PyStackQuery Background Worker")
    log("=" * 50)
    log(f"Poll interval: {POLL_INTERVAL}s")
    log(f"Stale time: {STALE_TIME}s")
    log("Press Ctrl+C to stop")
    log("")

    def signal_handler(sig: int, frame: Any) -> None:
        global running
        log("\nShutting down gracefully...")
        running = False

    signal.signal(signal.SIGINT, signal_handler)

    unsubscribes = await start_observers()

    tasks = [
        asyncio.create_task(data_aggregation_worker()),
        asyncio.create_task(health_check_worker()),
        asyncio.create_task(cache_management_worker()),
    ]

    try:
        while running:
            await asyncio.sleep(1)
    finally:
        log("Cleaning up...")
        for unsub in unsubscribes:
            unsub()
        for task in tasks:
            task.cancel()

        log("")
        log("=" * 50)
        log("  Final Metrics")
        log("=" * 50)
        log_metrics()
        log(f"Cache entries at shutdown: {len(client.cache)}")

        client.clear()
        log("Worker stopped.")


if __name__ == "__main__":
    asyncio.run(main())
