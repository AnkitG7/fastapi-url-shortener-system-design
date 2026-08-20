# ======================================================
# conftest.py — Test Fixtures with DB & Cache Isolation
# ======================================================
# SYSTEM DESIGN CONCEPT: Multi-Resource Test Isolation
# -------------------------------------------------
# For fast and deterministic testing:
# 1. Database: In-memory async SQLite
# 2. Cache: In-memory fake Redis via fakeredis
#
# This guarantees:
# - Zero external dependencies required during test runs
# - 100% test isolation (no state leaked between test cases)
# - Sub-second test execution for the entire suite
# ======================================================

import asyncio
import fakeredis.aioredis
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import StaticPool

from app.cache.url_cache import URLCache
from app.db.database import get_db
from app.db.models import Base
from app.dependencies import get_url_cache
from app.main import app

# In-memory async SQLite engine for testing
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

test_engine = create_async_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)

TestingSessionLocal = async_sessionmaker(
    bind=test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


@pytest.fixture(autouse=True)
def init_test_db():
    """Ensure clean tables before each test."""
    async def _init_tables():
        async with test_engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
            await conn.run_sync(Base.metadata.create_all)

    asyncio.run(_init_tables())
    yield


@pytest.fixture()
def fake_redis():
    """Provide a fresh fake async Redis client for testing."""
    return fakeredis.aioredis.FakeRedis(decode_responses=True)


@pytest.fixture()
def test_cache(fake_redis):
    """Provide a URLCache instance backed by fake Redis."""
    return URLCache(redis_client=fake_redis)


@pytest.fixture()
def client(test_cache):
    """
    Create a test client with overridden DB and Cache dependencies.
    """
    async def override_get_db():
        async with TestingSessionLocal() as session:
            try:
                yield session
            finally:
                await session.close()

    async def override_get_cache():
        return test_cache

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_url_cache] = override_get_cache

    with TestClient(app) as c:
        yield c

    app.dependency_overrides.clear()


@pytest.fixture()
def sample_url(client):
    """Fixture that creates a sample short URL."""
    response = client.post(
        "/api/v1/shorten",
        json={"original_url": "https://www.example.com/long/path"},
    )
    return response.json()


@pytest.fixture()
def sample_url_with_expiry(client):
    """Fixture that creates a URL with a 24-hour expiration."""
    response = client.post(
        "/api/v1/shorten",
        json={
            "original_url": "https://www.example.com/expiring",
            "expires_in_hours": 24,
        },
    )
    return response.json()


@pytest.fixture()
def sample_custom_url(client):
    """Fixture that creates a URL with a custom short code."""
    response = client.post(
        "/api/v1/shorten",
        json={
            "original_url": "https://www.example.com/custom",
            "custom_code": "my-link",
        },
    )
    return response.json()
