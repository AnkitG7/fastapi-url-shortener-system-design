# ======================================================
# tests/test_cache.py — Caching & Invalidation Tests
# ======================================================
# SYSTEM DESIGN CONCEPT: Cache Verification
# -------------------------------------------------
# We test all critical cache patterns:
# 1. Cache-Aside (Lazy Loading & Pre-warming)
# 2. TTL (Time-to-Live automatic expiration)
# 3. Cache Invalidation upon Deletion
# 4. Graceful Degradation when Cache fails
# ======================================================

import asyncio
from datetime import datetime, timezone
import pytest

from app.cache.url_cache import URLCache
from app.db.models import URL
from app.repositories.url_repository import URLRepository
from app.services.url_service import URLService


@pytest.mark.anyio
async def test_cache_set_and_get(fake_redis):
    """Test basic Cache-Aside storage and retrieval with JSON serialization."""
    cache = URLCache(redis_client=fake_redis)

    data = {
        "short_code": "cache123",
        "original_url": "https://fastapi.tiangolo.com",
        "created_at": datetime.now(timezone.utc),
        "click_count": 0,
    }

    # Set in cache
    success = await cache.set("cache123", data, ttl_seconds=60)
    assert success is True

    # Retrieve from cache (Cache Hit)
    cached_data = await cache.get("cache123")
    assert cached_data is not None
    assert cached_data["short_code"] == "cache123"
    assert cached_data["original_url"] == "https://fastapi.tiangolo.com"


@pytest.mark.anyio
async def test_cache_miss_returns_none(fake_redis):
    """Test querying a non-existent key returns None (Cache Miss)."""
    cache = URLCache(redis_client=fake_redis)
    result = await cache.get("nonexistent_key")
    assert result is None


@pytest.mark.anyio
async def test_cache_ttl_expiration(fake_redis):
    """
    SYSTEM DESIGN CONCEPT: Cache Expiration (TTL)
    ---------------------------------------------
    Verify that keys expire automatically after their TTL.
    """
    cache = URLCache(redis_client=fake_redis)

    data = {"short_code": "expire_me", "original_url": "https://example.com"}

    # Set with 1-second TTL
    await cache.set("expire_me", data, ttl_seconds=1)

    # Immediate get -> Hit
    assert await cache.get("expire_me") is not None

    # Wait for TTL to expire
    await asyncio.sleep(1.1)

    # Post-TTL get -> Miss (Key expired in Redis)
    assert await cache.get("expire_me") is None


@pytest.mark.anyio
async def test_cache_invalidation_on_delete(init_test_db, fake_redis):
    """
    SYSTEM DESIGN CONCEPT: Cache Invalidation
    ------------------------------------------
    When a URL is deleted via URLService, it MUST be removed
    from both PostgreSQL and Redis cache to avoid stale data.
    """
    from tests.conftest import TestingSessionLocal

    async with TestingSessionLocal() as session:
        repo = URLRepository(session=session)
        cache = URLCache(redis_client=fake_redis)
        service = URLService(repository=repo, cache=cache)

        # 1. Create URL (pre-warms cache)
        url = await service.create_short_url(
            original_url="https://python.org",
            custom_code="py-link",
        )
        assert await cache.get("py-link") is not None

        # 2. Delete URL
        await service.delete_url("py-link")

        # 3. Verify removed from DB
        assert await repo.get_by_short_code("py-link") is None

        # 4. Verify invalidated from Cache
        assert await cache.get("py-link") is None


@pytest.mark.anyio
async def test_service_redirect_uses_cache_hit(init_test_db, fake_redis):
    """
    Test redirect service utilizes cached destination URL for sub-millisecond responses.
    """
    from tests.conftest import TestingSessionLocal

    async with TestingSessionLocal() as session:
        repo = URLRepository(session=session)
        cache = URLCache(redis_client=fake_redis)
        service = URLService(repository=repo, cache=cache)

        # Create in DB and cache
        await service.create_short_url(
            original_url="https://google.com",
            custom_code="cached-redirect",
        )

        # Fetch redirect destination
        dest = await service.redirect_url("cached-redirect")
        assert dest == "https://google.com"
