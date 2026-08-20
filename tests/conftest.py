# ======================================================
# conftest.py — Test Fixtures with Database Isolation
# ======================================================
# SYSTEM DESIGN CONCEPT: Test Database Isolation
# -------------------------------------------------
# For tests, we use an in-memory SQLite database via
# aiosqlite or a separate test DB session.
# FastAPI's `app.dependency_overrides` allows us to
# intercept calls to `get_db` and provide a clean,
# isolated test session per test!
# ======================================================

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import StaticPool

from app.db.database import get_db
from app.db.models import Base
from app.main import app

# In-memory async SQLite engine specifically for testing
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
    """
    Ensure tables are created in the test engine synchronously/cleanly before tests.
    """
    import asyncio

    async def _init_tables():
        async with test_engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
            await conn.run_sync(Base.metadata.create_all)

    asyncio.run(_init_tables())
    yield


@pytest.fixture()
def client():
    """
    Create a test client with overridden DB dependency for isolation.
    """
    async def override_get_db():
        async with TestingSessionLocal() as session:
            try:
                yield session
            finally:
                await session.close()

    app.dependency_overrides[get_db] = override_get_db

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
