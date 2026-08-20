# ======================================================
# tests/test_rate_limiter.py — Rate Limiting Tests
# ======================================================
# SYSTEM DESIGN CONCEPT: Rate Limiting & SLA Verification
# -------------------------------------------------
# 1. Sliding Window Accuracy
# 2. Tiered Rate Limits (Anonymous vs Free vs Premium)
# 3. HTTP 429 Status Code & RFC Headers
# ======================================================

import pytest
from fastapi import status
from app.core.security import UserTier
from app.middleware.rate_limiter import SlidingWindowRateLimiter


@pytest.mark.anyio
async def test_sliding_window_allows_under_limit(fake_redis):
    """Test requests within the limit are permitted."""
    limiter = SlidingWindowRateLimiter(redis_client=fake_redis)

    for i in range(5):
        result = await limiter.is_allowed(identifier="user_1", limit=5, window_seconds=60)
        assert result.allowed is True
        assert result.remaining == 4 - i


@pytest.mark.anyio
async def test_sliding_window_blocks_over_limit(fake_redis):
    """Test requests exceeding the limit are blocked with 429 parameters."""
    limiter = SlidingWindowRateLimiter(redis_client=fake_redis)

    # Exhaust limit
    for _ in range(3):
        await limiter.is_allowed(identifier="user_2", limit=3, window_seconds=60)

    # 4th request must be blocked
    result = await limiter.is_allowed(identifier="user_2", limit=3, window_seconds=60)
    assert result.allowed is False
    assert result.remaining == 0
    assert result.retry_after > 0


@pytest.mark.anyio
async def test_tier_limits(fake_redis):
    """Test tier limit configuration values."""
    limiter = SlidingWindowRateLimiter(redis_client=fake_redis)
    assert limiter.get_tier_limit(UserTier.ANONYMOUS) == 10
    assert limiter.get_tier_limit(UserTier.FREE) == 100
    assert limiter.get_tier_limit(UserTier.PREMIUM) == 1000


def test_api_rate_limit_headers_present(client):
    """Test API responses include standard X-RateLimit headers."""
    response = client.get("/api/v1/urls")
    assert response.status_code == status.HTTP_200_OK
    assert "X-RateLimit-Limit" in response.headers
    assert "X-RateLimit-Remaining" in response.headers
    assert "X-RateLimit-Reset" in response.headers


def test_api_rate_limit_exceeded_returns_429(client, test_limiter):
    """
    Test sending more requests than the anonymous limit triggers HTTP 429.
    """
    # Anonymous limit is 10
    for _ in range(10):
        res = client.get("/api/v1/urls")
        assert res.status_code == status.HTTP_200_OK

    # 11th request -> 429 Too Many Requests
    blocked_res = client.get("/api/v1/urls")
    assert blocked_res.status_code == status.HTTP_429_TOO_MANY_REQUESTS
    assert "Retry-After" in blocked_res.headers
    assert blocked_res.json()["detail"]["error_code"] == "RATE_LIMIT_EXCEEDED"


def test_authenticated_api_key_has_higher_limit(client):
    """
    Test that supplying an API Key applies the Free tier limit (100) instead of Anonymous (10).
    """
    headers = {"X-API-Key": "free-key-123"}
    # Can make 15 requests without getting 429
    for _ in range(15):
        res = client.get("/api/v1/urls", headers=headers)
        assert res.status_code == status.HTTP_200_OK
        assert res.headers["X-RateLimit-Limit"] == "100"
