"""
FastAPI Application with PyStackQuery

A complete REST API demonstrating all PyStackQuery features:
- Request caching and deduplication
- Stale-while-revalidate
- Mutations with cache invalidation
- Parallel and dependent queries
- Observers for real-time updates
- Prefetching

Run: uvicorn examples.fastapi_app:app --reload
"""

from __future__ import annotations

import asyncio
import json
import time
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any, cast

# Simulated database
USERS_DB: dict[str, dict[str, Any]] = {
    "1": {"id": "1", "name": "Alice", "email": "alice@example.com", "role": "admin"},
    "2": {"id": "2", "name": "Bob", "email": "bob@example.com", "role": "user"},
    "3": {"id": "3", "name": "Charlie", "email": "charlie@example.com", "role": "user"},
}

POSTS_DB: dict[str, list[dict[str, Any]]] = {
    "1": [{"id": "p1", "title": "Hello World", "author_id": "1"}],
    "2": [{"id": "p2", "title": "My First Post", "author_id": "2"}],
    "3": [],
}

PRODUCTS_DB: list[dict[str, Any]] = [
    {"id": "prod1", "name": "Widget", "price": 9.99, "stock": 100},
    {"id": "prod2", "name": "Gadget", "price": 19.99, "stock": 50},
]

# Track API calls for demonstration
api_call_count: dict[str, int] = {}


def track_call(name: str) -> None:
    api_call_count[name] = api_call_count.get(name, 0) + 1
    print(f"[API CALL] {name} (total: {api_call_count[name]})")


# ─────────────────────────────────────────────────────────────────────────────
# PyStackQuery Setup
# ─────────────────────────────────────────────────────────────────────────────

from pystackquery import (  # noqa: E402
    MutationOptions,
    QueryClient,
    QueryClientConfig,
    QueryOptions,
    dependent_query,
    parallel_queries,
)

# Global client with sensible defaults
client = QueryClient(
    QueryClientConfig(
        stale_time=30.0,
        gc_time=300.0,
        retry=3,
        cache_max_size=1000,
    )
)


# ─────────────────────────────────────────────────────────────────────────────
# Simulated Data Access Layer
# ─────────────────────────────────────────────────────────────────────────────


async def fetch_all_users() -> list[dict[str, Any]]:
    """Simulate fetching all users from database."""
    track_call("fetch_all_users")
    await asyncio.sleep(0.1)
    return list(USERS_DB.values())


async def fetch_user_by_id(user_id: str) -> dict[str, Any] | None:
    """Simulate fetching a single user."""
    track_call(f"fetch_user_{user_id}")
    await asyncio.sleep(0.05)
    return USERS_DB.get(user_id)


async def fetch_user_posts(user_id: str) -> list[dict[str, Any]]:
    """Simulate fetching posts for a user."""
    track_call(f"fetch_posts_{user_id}")
    await asyncio.sleep(0.05)
    return POSTS_DB.get(user_id, [])


async def fetch_all_products() -> list[dict[str, Any]]:
    """Simulate fetching products."""
    track_call("fetch_all_products")
    await asyncio.sleep(0.08)
    return PRODUCTS_DB.copy()


async def fetch_stats() -> dict[str, Any]:
    """Simulate fetching statistics."""
    track_call("fetch_stats")
    await asyncio.sleep(0.05)
    return {
        "total_users": len(USERS_DB),
        "total_products": len(PRODUCTS_DB),
        "timestamp": time.time(),
    }


async def search_users(query: str) -> list[dict[str, Any]]:
    """Simulate user search."""
    track_call(f"search_{query}")
    await asyncio.sleep(0.2)
    query_lower = query.lower()
    return [u for u in USERS_DB.values() if query_lower in u["name"].lower()]


async def create_user_in_db(data: dict[str, Any]) -> dict[str, Any]:
    """Simulate creating a user."""
    track_call("create_user")
    await asyncio.sleep(0.1)
    new_id = str(len(USERS_DB) + 1)
    user = {"id": new_id, **data}
    USERS_DB[new_id] = user
    POSTS_DB[new_id] = []
    return user


async def update_user_in_db(user_id: str, data: dict[str, Any]) -> dict[str, Any]:
    """Simulate updating a user."""
    track_call(f"update_user_{user_id}")
    await asyncio.sleep(0.1)
    if user_id in USERS_DB:
        USERS_DB[user_id].update(data)
    return USERS_DB[user_id]


# ─────────────────────────────────────────────────────────────────────────────
# FastAPI Application
# ─────────────────────────────────────────────────────────────────────────────

try:
    from fastapi import (  # type: ignore
        FastAPI,
        HTTPException,
        WebSocket,
        WebSocketDisconnect,
    )
    from fastapi.responses import JSONResponse  # type: ignore
except ImportError:
    # Stub for demonstration if not installed
    class FastAPI:  # type: ignore
        def __init__(self, **kw: Any) -> None:
            pass

        def get(self, *a: Any, **kw: Any) -> Any:
            return lambda f: f

        def post(self, *a: Any, **kw: Any) -> Any:
            return lambda f: f

        def websocket(self, *a: Any, **kw: Any) -> Any:
            return lambda f: f

    class HTTPException(Exception):  # type: ignore
        def __init__(self, status_code: int, detail: str) -> None:
            pass

    class WebSocket:  # type: ignore
        pass

    class WebSocketDisconnect(Exception):  # type: ignore
        pass

    class JSONResponse:  # type: ignore
        def __init__(self, content: Any) -> None:
            pass


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifecycle."""
    print("Starting up... PyStackQuery client ready")
    yield
    print("Shutting down... clearing cache")
    client.clear()


app = FastAPI(
    title="PyStackQuery FastAPI Example",
    description="Demonstrates PyStackQuery in a REST API",
    lifespan=lifespan,
)


# ─────────────────────────────────────────────────────────────────────────────
# Endpoints
# ─────────────────────────────────────────────────────────────────────────────


@app.get("/users")  # type: ignore
async def list_users() -> dict[str, Any]:
    """List all users with caching."""
    users = await client.fetch_query(
        QueryOptions(query_key=("users",), query_fn=fetch_all_users, stale_time=30.0)
    )
    return {"users": users, "cached": True, "api_calls": api_call_count}


@app.get("/users/{user_id}")  # type: ignore
async def get_user(user_id: str) -> dict[str, Any]:
    """Get a single user with caching."""
    user = await client.fetch_query(
        QueryOptions(
            query_key=("user", user_id),
            query_fn=lambda: fetch_user_by_id(user_id),
            stale_time=60.0,
        )
    )
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return {"user": user, "api_calls": api_call_count}


@app.get("/dashboard")  # type: ignore
async def get_dashboard() -> dict[str, Any]:
    """Dashboard with parallel queries."""
    results = await parallel_queries(
        client,
        QueryOptions(("users",), fetch_all_users, stale_time=30.0),
        QueryOptions(("products",), fetch_all_products, stale_time=60.0),
        QueryOptions(("stats",), fetch_stats, stale_time=10.0),
    )
    users = cast(list[Any], results[0])
    products = cast(list[Any], results[1])
    stats = cast(dict[str, Any], results[2])

    return {
        "users_count": len(users),
        "products_count": len(products),
        "stats": stats,
        "api_calls": api_call_count,
    }


@app.get("/users/{user_id}/full")  # type: ignore
async def get_user_full(user_id: str) -> dict[str, Any]:
    """Get user with their posts using dependent query."""
    user = await client.fetch_query(
        QueryOptions(
            query_key=("user", user_id),
            query_fn=lambda: fetch_user_by_id(user_id),
        )
    )

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    posts = await client.fetch_query(
        QueryOptions(
            query_key=("posts", user_id),
            query_fn=lambda: fetch_user_posts(user_id),
        )
    )

    return {"user": user, "posts": posts, "api_calls": api_call_count}


@app.get("/users/{user_id}/profile")  # type: ignore
async def get_user_profile(user_id: str) -> dict[str, Any]:
    """Get user profile using dependent_query helper."""
    try:

        def then_posts(user: Any) -> QueryOptions[object]:
            u = cast(dict[str, Any], user)

            async def posts_fetcher() -> list[dict[str, Any]]:
                return await fetch_user_posts(u["id"]) if u else []

            return QueryOptions(
                ("posts", u["id"]) if u else ("posts", "none"),
                posts_fetcher,
            )

        posts = await dependent_query(
            client,
            depends_on=QueryOptions(
                ("user", user_id),
                lambda: fetch_user_by_id(user_id),
            ),
            then=then_posts,
        )
        user = client.get_query_data(("user", user_id))
        return {"user": user, "posts": posts}
    except Exception:
        raise HTTPException(status_code=404, detail="User not found")


@app.get("/search")  # type: ignore
async def search(q: str) -> dict[str, Any]:
    """Search users with automatic deduplication."""
    results = await client.fetch_query(
        QueryOptions(
            query_key=("search", q.lower()),
            query_fn=lambda: search_users(q),
            stale_time=60.0,
        )
    )
    return {"query": q, "results": results, "api_calls": api_call_count}


@app.post("/users")  # type: ignore
async def create_user(name: str, email: str, role: str = "user") -> dict[str, Any]:
    """Create a new user with cache invalidation."""

    async def mutation_fn(data: dict[str, Any]) -> dict[str, Any]:
        return await create_user_in_db(data)

    mutation = client.mutation(
        MutationOptions(
            mutation_fn=mutation_fn,
            on_success=lambda result, _: print(
                f"Created user: {cast(dict[str, Any], result)['id']}"
            ),
        )
    )

    new_user = await mutation.mutate({"name": name, "email": email, "role": role})
    await client.invalidate_queries(("users",))

    return {"user": new_user, "message": "User created, cache invalidated"}


@app.post("/users/{user_id}")  # type: ignore
async def update_user(
    user_id: str, name: str | None = None, email: str | None = None
) -> dict[str, Any]:
    """Update a user with optimistic updates."""
    update_data: dict[str, Any] = {}
    if name:
        update_data["name"] = name
    if email:
        update_data["email"] = email

    if not update_data:
        raise HTTPException(status_code=400, detail="No update data provided")

    current = client.get_query_data(("user", user_id))

    def optimistic_update(data: dict[str, Any]) -> dict[str, Any]:
        if current:
            curr = cast(dict[str, Any], current)
            optimistic = {**curr, **data}
            client.set_query_data(("user", user_id), optimistic)
            return curr
        return {}

    async def update_fn(d: dict[str, Any]) -> dict[str, Any]:
        return await update_user_in_db(user_id, d)

    mutation = client.mutation(
        MutationOptions(
            mutation_fn=update_fn,
            on_mutate=optimistic_update,
        )
    )

    result = await mutation.mutate(update_data)
    await client.invalidate_queries(("user", user_id))
    await client.invalidate_queries(("users",))

    return {"user": result, "message": "User updated"}


@app.get("/cache/stats")  # type: ignore
async def cache_stats() -> dict[str, Any]:
    """Get cache statistics."""
    return {"cached_queries": len(client.cache), "api_calls": api_call_count}


@app.post("/cache/invalidate")  # type: ignore
async def invalidate_cache(prefix: str | None = None) -> dict[str, Any]:
    """Invalidate cache entries."""
    if prefix:
        key = tuple(prefix.split(","))
        await client.invalidate_queries(key)
        return {"invalidated": prefix}
    await client.invalidate_queries()
    return {"invalidated": "all"}


@app.websocket("/ws/users")  # type: ignore
async def websocket_users(websocket: WebSocket) -> None:
    """WebSocket for real-time user updates."""
    await websocket.accept()

    observer = client.watch(
        QueryOptions(
            query_key=("users",),
            query_fn=fetch_all_users,
            refetch_interval=10.0,
        )
    )

    async def send_update(state: Any) -> None:
        try:
            await websocket.send_json(
                {
                    "type": "users_update",
                    "status": state.status.name,
                    "data": state.data,
                    "timestamp": time.time(),
                }
            )
        except Exception:
            pass

    unsubscribe = observer.subscribe(lambda s: asyncio.create_task(send_update(s)))

    try:
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)
            if message.get("action") == "refresh":
                await observer.refetch()
    except WebSocketDisconnect:
        pass
    finally:
        unsubscribe()


if __name__ == "__main__":
    try:
        import uvicorn  # type: ignore

        uvicorn.run(app, host="0.0.0.0", port=8000)
    except ImportError:
        print("Install fastapi uvicorn to run.")
