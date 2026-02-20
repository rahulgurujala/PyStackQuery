"""
Tkinter GUI Application with PyStackQuery

A desktop application demonstrating:
- Non-blocking async data fetching in GUI
- Caching for instant response on repeat actions
- Observers for live data updates
- Background prefetching

Run: python -m examples.tkinter_app
"""

from __future__ import annotations

import asyncio
import json
import ssl
import threading
import time
import tkinter as tk
from collections.abc import Coroutine
from concurrent.futures import Future
from tkinter import ttk
from typing import Any, cast
from urllib.request import Request, urlopen

from pystackquery import (
    QueryClient,
    QueryClientConfig,
    QueryOptions,
    QueryStatus,
)

# ─────────────────────────────────────────────────────────────────────────────
# Configuration
# ─────────────────────────────────────────────────────────────────────────────

SSL_CTX = ssl.create_default_context()
SSL_CTX.check_hostname = False
SSL_CTX.verify_mode = ssl.CERT_NONE

BASE_URL = "https://dummyjson.com"

# Global PyStackQuery client
client = QueryClient(
    QueryClientConfig(
        stale_time=30.0,
        gc_time=300.0,
        retry=2,
    )
)


# ─────────────────────────────────────────────────────────────────────────────
# Async HTTP
# ─────────────────────────────────────────────────────────────────────────────


async def http_get(url: str) -> dict[str, Any]:
    """Async HTTP GET."""

    def _fetch() -> dict[str, Any]:
        req = Request(url, headers={"User-Agent": "PyStackQuery-TkApp/1.0"})
        with urlopen(req, context=SSL_CTX, timeout=10) as resp:
            data = resp.read().decode()
            return cast(dict[str, Any], json.loads(data))

    return await asyncio.to_thread(_fetch)


# ─────────────────────────────────────────────────────────────────────────────
# Data Fetching Functions
# ─────────────────────────────────────────────────────────────────────────────


async def fetch_users(limit: int = 10) -> dict[str, Any]:
    """Fetch users from API."""
    return await http_get(f"{BASE_URL}/users?limit={limit}")


async def fetch_user_detail(user_id: int) -> dict[str, Any]:
    """Fetch single user details."""
    return await http_get(f"{BASE_URL}/users/{user_id}")


async def search_users(query: str) -> dict[str, Any]:
    """Search users by name."""
    return await http_get(f"{BASE_URL}/users/search?q={query}")


async def fetch_quote() -> dict[str, Any]:
    """Fetch a random quote for the monitor."""
    return await http_get(f"{BASE_URL}/quotes/random")


# ─────────────────────────────────────────────────────────────────────────────
# Async-Tkinter Bridge
# ─────────────────────────────────────────────────────────────────────────────


class AsyncTk(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.loop = asyncio.new_event_loop()
        self._loop_thread: threading.Thread | None = None

    def run_async(self, coro: Coroutine[Any, Any, Any]) -> Future[Any]:
        return asyncio.run_coroutine_threadsafe(coro, self.loop)

    def start_async_loop(self) -> None:
        def run_loop() -> None:
            asyncio.set_event_loop(self.loop)
            self.loop.run_forever()

        self._loop_thread = threading.Thread(target=run_loop, daemon=True)
        self._loop_thread.start()

    def stop_async_loop(self) -> None:
        self.loop.call_soon_threadsafe(self.loop.stop)

    def destroy(self) -> None:
        """Clean up on window close."""
        self.stop_async_loop()
        client.clear()
        super().destroy()


# ─────────────────────────────────────────────────────────────────────────────
# Main Application
# ─────────────────────────────────────────────────────────────────────────────


class PyStackQueryApp(AsyncTk):
    def __init__(self) -> None:
        super().__init__()

        self.title("PyStackQuery Tkinter Demo")
        self.geometry("800x600")

        self._setup_styles()
        self._create_widgets()
        self._setup_observer()

        self.start_async_loop()
        self.after(100, self._initial_load)

    def _initial_load(self) -> None:
        self.run_async(self._load_users())

    def _setup_styles(self) -> None:
        style = ttk.Style()
        style.configure("Header.TLabel", font=("Helvetica", 12, "bold"))
        style.configure("Status.TLabel", font=("Helvetica", 9))

    def _create_widgets(self) -> None:
        main = ttk.Frame(self, padding=10)
        main.pack(fill=tk.BOTH, expand=True)

        notebook = ttk.Notebook(main)
        notebook.pack(fill=tk.BOTH, expand=True)

        self._create_user_browser_tab(notebook)
        self._create_search_tab(notebook)
        self._create_monitor_tab(notebook)
        self._create_status_bar(main)

    def _create_user_browser_tab(self, notebook: ttk.Notebook) -> None:
        frame = ttk.Frame(notebook, padding=10)
        notebook.add(frame, text="User Browser")

        controls = ttk.Frame(frame)
        controls.pack(fill=tk.X, pady=(0, 10))

        ttk.Button(
            controls, text="Load Users", command=self._on_load_users
        ).pack(side=tk.LEFT, padx=5)
        ttk.Button(
            controls, text="Load Users (Fresh)", command=self._on_load_users_fresh
        ).pack(side=tk.LEFT, padx=5)
        ttk.Button(
            controls, text="Clear Cache", command=self._on_clear_cache
        ).pack(side=tk.LEFT, padx=5)

        list_frame = ttk.Frame(frame)
        list_frame.pack(fill=tk.BOTH, expand=True)

        self.user_list = ttk.Treeview(
            list_frame,
            columns=("id", "name", "email", "phone"),
            show="headings",
            selectmode="browse",
        )
        self.user_list.heading("id", text="ID")
        self.user_list.heading("name", text="Name")
        self.user_list.heading("email", text="Email")
        self.user_list.heading("phone", text="Phone")

        scrollbar = ttk.Scrollbar(
            list_frame, orient=tk.VERTICAL, command=self.user_list.yview
        )
        self.user_list.configure(yscrollcommand=scrollbar.set)
        self.user_list.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.user_list.bind("<<TreeviewSelect>>", self._on_user_select)

        self.detail_text = tk.Text(frame, height=5, state=tk.DISABLED, wrap=tk.WORD)
        self.detail_text.pack(fill=tk.X, pady=(10, 0))

    def _create_search_tab(self, notebook: ttk.Notebook) -> None:
        frame = ttk.Frame(notebook, padding=10)
        notebook.add(frame, text="Search")

        search_frame = ttk.Frame(frame)
        search_frame.pack(fill=tk.X, pady=(0, 10))

        self.search_entry = ttk.Entry(search_frame, width=30)
        self.search_entry.pack(side=tk.LEFT, padx=5)
        self.search_entry.bind("<Return>", lambda _: self._on_search())

        ttk.Button(
            search_frame, text="Search", command=self._on_search
        ).pack(side=tk.LEFT)

        self.search_results = ttk.Treeview(
            frame, columns=("id", "name", "email"), show="headings"
        )
        self.search_results.heading("id", text="ID")
        self.search_results.heading("name", text="Name")
        self.search_results.heading("email", text="Email")
        self.search_results.pack(fill=tk.BOTH, expand=True)

        self.search_info = ttk.Label(frame, text="", style="Status.TLabel")
        self.search_info.pack(pady=(5, 0))

    def _create_monitor_tab(self, notebook: ttk.Notebook) -> None:
        frame = ttk.Frame(notebook, padding=10)
        notebook.add(frame, text="Live Monitor")

        self.quote_text = tk.Text(frame, height=4, state=tk.DISABLED, wrap=tk.WORD)
        self.quote_text.pack(fill=tk.BOTH, expand=True)

        self.quote_status = ttk.Label(frame, text="", style="Status.TLabel")
        self.quote_status.pack(pady=(5, 0))

        controls = ttk.Frame(frame)
        controls.pack(fill=tk.X, pady=(10, 0))

        ttk.Button(
            controls, text="Refresh Now", command=self._on_refresh_quote
        ).pack(side=tk.LEFT, padx=5)
        ttk.Button(
            controls, text="Pause", command=self._on_pause_monitor
        ).pack(side=tk.LEFT, padx=5)
        ttk.Button(
            controls, text="Resume", command=self._on_resume_monitor
        ).pack(side=tk.LEFT, padx=5)

    def _create_status_bar(self, parent: ttk.Frame) -> None:
        status_frame = ttk.Frame(parent)
        status_frame.pack(fill=tk.X, pady=(10, 0))

        self.status_label = ttk.Label(status_frame, text="Ready", style="Status.TLabel")
        self.status_label.pack(side=tk.LEFT)

        self.cache_label = ttk.Label(
            status_frame,
            text="Cache: 0 queries",
            style="Status.TLabel",
        )
        self.cache_label.pack(side=tk.RIGHT)

    def _setup_observer(self) -> None:
        self.quote_observer = client.watch(
            QueryOptions(
                query_key=("quote", "random"),
                query_fn=fetch_quote,
                refetch_interval=10.0,
            )
        )
        self.quote_unsubscribe = self.quote_observer.subscribe(self._on_quote_update)

    def _update_status(self, text: str) -> None:
        self.status_label.config(text=text)
        self.cache_label.config(text=f"Cache: {len(client.cache)} queries")

    def _set_detail_text(self, text: str) -> None:
        self.detail_text.config(state=tk.NORMAL)
        self.detail_text.delete("1.0", tk.END)
        self.detail_text.insert("1.0", text)
        self.detail_text.config(state=tk.DISABLED)

    def _set_quote_text(self, text: str) -> None:
        self.quote_text.config(state=tk.NORMAL)
        self.quote_text.delete("1.0", tk.END)
        self.quote_text.insert("1.0", text)
        self.quote_text.config(state=tk.DISABLED)

    def _on_load_users(self) -> None:
        self._update_status("Loading users...")
        self.run_async(self._load_users())

    def _on_load_users_fresh(self) -> None:
        self._update_status("Invalidating cache and loading fresh...")
        self.run_async(self._load_users_fresh())

    def _on_clear_cache(self) -> None:
        client.clear()
        self._update_status("Cache cleared")
        self.user_list.delete(*self.user_list.get_children())
        self._set_detail_text("")

    def _on_user_select(self, _: Any) -> None:
        selection = self.user_list.selection()
        if selection:
            item = self.user_list.item(selection[0])
            user_id = item["values"][0]
            self.run_async(self._load_user_detail(int(user_id)))

    def _on_search(self) -> None:
        query = self.search_entry.get().strip()
        if query:
            self.run_async(self._do_search(query))

    def _on_refresh_quote(self) -> None:
        self.run_async(self.quote_observer.refetch())

    def _on_pause_monitor(self) -> None:
        key_hash = self.quote_observer.options.get_key_hash()
        query = cast(Any, client.cache.get(key_hash))
        if query:
            query.pause()
            self.quote_status.config(text="Paused")

    def _on_resume_monitor(self) -> None:
        key_hash = self.quote_observer.options.get_key_hash()
        query = cast(Any, client.cache.get(key_hash))
        if query:
            query.resume(refetch=True)
            self.quote_status.config(text="Resumed")

    def _on_quote_update(self, state: Any) -> None:
        def update() -> None:
            if state.status == QueryStatus.PENDING:
                self.quote_status.config(text="Loading...")
            elif state.status == QueryStatus.SUCCESS and state.data:
                quote = state.data
                author = quote.get("author", "Unknown")
                text = f'"{quote.get("quote", "")}"\n\n— {author}'
                self._set_quote_text(text)
                ts = time.strftime("%H:%M:%S")
                self.quote_status.config(text=f"Updated at {ts}")
            self._update_status("Ready")

        self.after(0, update)

    # ─────────────────────────────────────────────────────────────────────────
    # Async Operations
    # ─────────────────────────────────────────────────────────────────────────

    async def _load_users(self) -> None:
        try:

            def fetcher() -> Coroutine[Any, Any, dict[str, Any]]:
                return fetch_users(10)

            data = await client.fetch_query(
                QueryOptions(("users", "list"), fetcher, stale_time=30.0)
            )
            users = data.get("users", [])
            self.after(0, lambda: self._populate_user_list(users))
        except Exception as e:
            self.after(0, lambda err=e: self._update_status(f"Error: {err}"))

    async def _load_users_fresh(self) -> None:
        await client.invalidate_queries(("users", "list"), refetch=False)
        await self._load_users()

    async def _load_user_detail(self, user_id: int) -> None:
        try:

            def fetcher() -> Coroutine[Any, Any, dict[str, Any]]:
                return fetch_user_detail(user_id)

            user = await client.fetch_query(
                QueryOptions(("user", str(user_id)), fetcher, stale_time=60.0)
            )
            self.after(0, lambda: self._show_user_detail(user))
        except Exception as e:
            self.after(0, lambda err=e: self._update_status(f"Error: {err}"))

    async def _do_search(self, query: str) -> None:
        try:

            def fetcher() -> Coroutine[Any, Any, dict[str, Any]]:
                return search_users(query)

            data = await client.fetch_query(
                QueryOptions(
                    ("search", "users", query.lower()),
                    fetcher,
                    stale_time=60.0,
                )
            )
            users = data.get("users", [])
            self.after(0, lambda: self._show_search_results(users, query))
        except Exception as e:
            self.after(0, lambda err=e: self._update_status(f"Search error: {err}"))

    def _populate_user_list(self, users: list[dict[str, Any]]) -> None:
        self.user_list.delete(*self.user_list.get_children())
        for user in users:
            name = f"{user.get('firstName', '')} {user.get('lastName', '')}"
            self.user_list.insert(
                "",
                tk.END,
                values=(user["id"], name, user.get("email", ""), user.get("phone", "")),
            )
        self._update_status(f"Loaded {len(users)} users")

    def _show_user_detail(self, user: dict[str, Any]) -> None:
        name = f"{user.get('firstName')} {user.get('lastName')}"
        detail = f"ID: {user.get('id')}\nName: {name}\nEmail: {user.get('email')}"
        self._set_detail_text(detail)

    def _show_search_results(
        self, users: list[dict[str, Any]], query: str
    ) -> None:
        self.search_results.delete(*self.search_results.get_children())
        for user in users:
            name = f"{user.get('firstName', '')} {user.get('lastName', '')}"
            self.search_results.insert(
                "",
                tk.END,
                values=(user["id"], name, user.get("email", "")),
            )
        self.search_info.config(text=f"Found {len(users)} results for '{query}'")


if __name__ == "__main__":
    app = PyStackQueryApp()
    app.mainloop()
