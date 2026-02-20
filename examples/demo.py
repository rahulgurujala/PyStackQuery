"""
PyStackQuery Demo - Real-world usage examples.

Run: python -m examples.demo
"""

from __future__ import annotations

import asyncio
import ssl
import time
from typing import Any, cast
from urllib.request import Request, urlopen

from pystackquery import (
    MutationOptions,
    QueryClient,
    QueryOptions,
    parallel_queries,
)

# SSL context for macOS compatibility
SSL_CTX = ssl.create_default_context()
SSL_CTX.check_hostname = False
SSL_CTX.verify_mode = ssl.CERT_NONE

BASE_URL = "https://dummyjson.com"


def log(msg: str) -> None:
    """Print with timestamp."""
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


async def http_get(url: str) -> dict[str, Any]:
    """Simple async HTTP GET."""
    import json

    def _fetch() -> dict[str, Any]:
        req = Request(url, headers={"User-Agent": "PyStackQuery/1.0"})
        with urlopen(req, context=SSL_CTX, timeout=10) as resp:
            data = resp.read().decode()
            return cast(dict[str, Any], json.loads(data))

    return await asyncio.to_thread(_fetch)


# ─────────────────────────────────────────────────────────────
# Demo 1: Basic Caching
# ─────────────────────────────────────────────────────────────
async def demo_basic_caching() -> None:
    log("--- Demo 1: Basic Caching ---")
    client = QueryClient()

    opts = QueryOptions(
        query_key=("user", "1"),
        query_fn=lambda: http_get(f"{BASE_URL}/users/1"),
        stale_time=5.0,
    )

    log("Fetching user 1 (Cold)...")
    user = await client.fetch_query(opts)
    log(f"Result: {user['firstName']} {user['lastName']}")

    log("Fetching user 1 again (Hot)...")
    user2 = await client.fetch_query(opts)
    log(f"Result: {user2['firstName']} {user2['lastName']} (Cached)")


# ─────────────────────────────────────────────────────────────
# Demo 2: Parallel Queries
# ─────────────────────────────────────────────────────────────
async def demo_parallel_queries() -> None:
    log("--- Demo 2: Parallel Queries ---")
    client = QueryClient()

    results = await parallel_queries(
        client,
        QueryOptions(("user", "1"), lambda: http_get(f"{BASE_URL}/users/1")),
        QueryOptions(("user", "2"), lambda: http_get(f"{BASE_URL}/users/2")),
        QueryOptions(("product", "1"), lambda: http_get(f"{BASE_URL}/products/1")),
    )

    user1 = cast(dict[str, Any], results[0])
    user2 = cast(dict[str, Any], results[1])
    prod1 = cast(dict[str, Any], results[2])

    log(f"Users: {user1['firstName']}, {user2['firstName']}")
    log(f"Product: {prod1['title']}")


# ─────────────────────────────────────────────────────────────
# Demo 3: Reactive Observers
# ─────────────────────────────────────────────────────────────
async def demo_observers() -> None:
    log("--- Demo 3: Reactive Observers ---")
    client = QueryClient()

    async def fetcher() -> dict[str, float]:
        return {"price": 100.0}

    opts = QueryOptions(
        query_key=("stock", "price"),
        query_fn=fetcher,
        refetch_interval=0.5,
    )

    observer = client.watch(opts)

    def on_change(state: Any) -> None:
        log(f"Observer Notified: status={state.status.name}, data={state.data}")

    unsub = observer.subscribe(on_change)

    log("Observer subscribed. Waiting for updates...")
    await asyncio.sleep(1.2)

    unsub()
    log("Observer unsubscribed.")


# ─────────────────────────────────────────────────────────────
# Demo 4: Mutations
# ─────────────────────────────────────────────────────────────
async def demo_mutations() -> None:
    log("--- Demo 4: Mutations ---")
    client = QueryClient()

    async def add_user(data: dict[str, str]) -> dict[str, Any]:
        log(f"API: Adding user {data['firstName']}...")
        await asyncio.sleep(0.5)
        return {"id": 101, **data}

    mutation = client.mutation(MutationOptions(
        mutation_fn=add_user,
        on_success=lambda res, _: log(f"Mutation Success! New ID: {res['id']}"),
    ))

    await mutation.mutate({"firstName": "Jane", "lastName": "Doe"})


async def main() -> None:
    try:
        await demo_basic_caching()
        await demo_parallel_queries()
        await demo_observers()
        await demo_mutations()
    except Exception as e:
        log(f"Demo failed: {e}")


if __name__ == "__main__":
    asyncio.run(main())
