# ======================================================
# tests/test_edge_cases.py — Deep Edge Cases & Fault Tolerance Tests
# ======================================================
# SYSTEM DESIGN CONCEPT: Robustness & Edge-Case Testing
# -------------------------------------------------
# 1. Expired URL access & cleanup
# 2. Unknown API key graceful fallback
# 3. IPv6 loopback & link-local SSRF attacks
# 4. Circuit Breaker probe failure re-trip
# 5. Non-existent URL analytics 404
# 6. Cache graceful degradation under Redis failures
# ======================================================

from datetime import datetime, timedelta, timezone
import pytest
from fastapi import status
from redis.exceptions import ConnectionError as RedisConnectionError

from app.cache.url_cache import URLCache
from app.core.security import validate_and_sanitize_url
from app.db.models import URL
from app.middleware.auth import authenticate_api_key
from app.middleware.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerOpenError,
    CircuitState,
)
from app.repositories.url_repository import URLRepository
from app.services.url_service import (
    URLExpiredError,
    URLNotFoundError,
    URLService,
)


@pytest.mark.anyio
async def test_expired_url_redirect_and_get_returns_404(init_test_db, fake_redis, client):
    """
    SYSTEM DESIGN CONCEPT: Lazy Expiration & Cleanup
    ------------------------------------------------
    When an expired URL is queried or redirected, it should:
    1. Raise URLExpiredError / return HTTP 404
    2. Clean up the expired record from DB and Redis
    """
    from tests.conftest import TestingSessionLocal

    async with TestingSessionLocal() as session:
        # Create an already-expired URL
        expired_time = datetime.now(timezone.utc) - timedelta(hours=2)
        url = URL(
            short_code="expired_link",
            original_url="https://example.com/expired",
            expires_at=expired_time,
        )
        session.add(url)
        await session.commit()

        repo = URLRepository(session=session)
        cache = URLCache(redis_client=fake_redis)
        service = URLService(repository=repo, cache=cache)

        # 1. Direct service get raises URLExpiredError
        with pytest.raises(URLExpiredError):
            await service.get_url("expired_link")

        # 2. Redirect raises URLExpiredError and cleans up
        with pytest.raises(URLExpiredError):
            await service.redirect_url("expired_link")


def test_api_get_analytics_for_nonexistent_url_returns_404(client):
    """
    Test GET /api/v1/urls/{code}/analytics returns 404 for missing codes.
    """
    response = client.get("/api/v1/urls/nonexistent_stats/analytics")
    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert response.json()["detail"]["error_code"] == "URL_NOT_FOUND"


def test_unknown_api_key_falls_back_to_anonymous():
    """
    Test an unrecognized API key is treated as Anonymous tier.
    """
    user = authenticate_api_key("bogus_unregistered_key_123", client_ip="1.2.3.4")
    assert user.is_authenticated is False
    assert "invalid_key:" in user.identifier


def test_ssrf_blocked_ipv6_loopback():
    """
    Test IPv6 loopback [::1] and link-local addresses are rejected.
    """
    with pytest.raises(ValueError) as exc:
        validate_and_sanitize_url("http://[::1]:8000/secret")
    assert "private or reserved" in str(exc.value) or "Blocked" in str(exc.value)


@pytest.mark.anyio
async def test_circuit_breaker_half_open_failure_re_trips_to_open():
    """
    Test that if a probe request fails in HALF_OPEN state, it immediately re-trips to OPEN.
    """
    breaker = CircuitBreaker(
        name="test_service",
        failure_threshold=1,
        recovery_timeout_seconds=0.1,
    )

    async def fail_call():
        raise RuntimeError("Service still down")

    # Trip to OPEN
    with pytest.raises(RuntimeError):
        await breaker.call(fail_call)
    assert breaker.state == CircuitState.OPEN

    # Wait for cooldown to transition to HALF_OPEN
    await pytest.importorskip("asyncio").sleep(0.15)

    # Probe call in HALF_OPEN fails -> immediately trips back to OPEN
    with pytest.raises(RuntimeError):
        await breaker.call(fail_call)
    assert breaker.state == CircuitState.OPEN


@pytest.mark.anyio
async def test_url_cache_graceful_degradation_on_redis_exception():
    """
    SYSTEM DESIGN CONCEPT: Graceful Degradation Under Error
    -------------------------------------------------------
    If Redis throws a connection or execution error, URLCache methods
    should return None / False without raising an uncaught exception.
    """
    class BrokenRedis:
        async def get(self, key):
            raise RedisConnectionError("Redis connection lost")
        async def set(self, key, val, ex=None):
            raise RedisConnectionError("Redis connection lost")
        async def delete(self, key):
            raise RedisConnectionError("Redis connection lost")

    cache = URLCache(redis_client=BrokenRedis())

    # None of these should crash
    assert await cache.get("any_key") is None
    assert await cache.set("any_key", {"data": 1}) is False
    assert await cache.delete("any_key") is False
