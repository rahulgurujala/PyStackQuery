from __future__ import annotations

from collections.abc import AsyncGenerator

import pytest

from pystackquery import QueryClient, QueryClientConfig

# --- Mock Storage for Testing Persistence ---

class MockStorage:
    def __init__(self) -> None:
        self.data: dict[str, tuple[str | None, float]] = {}

    async def get(self, key: str) -> str | None:
        return self.data.get(key, (None, 0.0))[0]

    async def set(self, key: str, value: str, ttl: float | None = None) -> None:
        self.data[key] = (value, 0.0) # We ignore TTL for basic tests

    async def delete(self, key: str) -> None:
        self.data.pop(key, None)

    async def clear(self) -> None:
        self.data.clear()

# --- Fixtures ---

@pytest.fixture
def mock_storage() -> MockStorage:
    return MockStorage()

@pytest.fixture
async def client() -> AsyncGenerator[QueryClient, None]:
    """Provides a fresh QueryClient for each test."""
    client = QueryClient(QueryClientConfig(retry=0)) # Disable retries for faster tests
    yield client
    client.clear()

@pytest.fixture
async def persistent_client(
    mock_storage: MockStorage,
) -> AsyncGenerator[QueryClient, None]:
    """Provides a QueryClient with a mock persistence layer."""
    config = QueryClientConfig(storage=mock_storage, retry=0)
    client = QueryClient(config)
    yield client
    client.clear()
