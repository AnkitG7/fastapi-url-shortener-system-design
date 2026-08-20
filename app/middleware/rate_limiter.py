# ======================================================
# middleware/rate_limiter.py — Redis Sliding Window Rate Limiter
# ======================================================
# SYSTEM DESIGN CONCEPT: Rate Limiting Algorithms
# -------------------------------------------------
# Rate limiting protects APIs from:
# 1. Denial of Service (DoS) attacks & abusive traffic
# 2. Resource exhaustion (CPU, DB connections, memory)
# 3. Ensuring fair resource allocation across tenants
#
# COMMON ALGORITHMS & TRADEOFFS:
#
# 1. FIXED WINDOW COUNTER:
#    - E.g., Max 100 req/min. Resets at 12:01:00, 12:02:00.
#    - Flaw: "Boundary Burst" — 100 requests at 12:01:59 + 100
#      requests at 12:02:01 = 200 requests in 2 seconds!
#
# 2. SLIDING WINDOW LOG (Implemented below via Redis ZSET):
#    - Tracks timestamps of every request in a Redis Sorted Set.
#    - Perfectly accurate sliding 60-second window.
#    - Eliminates the boundary burst problem.
#
# 3. TOKEN BUCKET / LEAKY BUCKET:
#    - Great for allowing controlled bursts while keeping
#      average rate steady.
#
# HOW SLIDING WINDOW LOG WORKS WITH REDIS:
#   1. Current timestamp T = now()
#   2. Remove all timestamps older than (T - window_size):
#      `ZREMRANGEBYSCORE key 0 (T - window_size)`
#   3. Count requests in the current window:
#      `ZCARD key`
#   4. If count < limit:
#      - Add current timestamp: `ZADD key T <request_uuid>`
#      - Set TTL on the key: `EXPIRE key window_size`
#      - Allow request!
#   5. If count >= limit:
#      - Reject with HTTP 429 Too Many Requests
#      - Include Retry-After & X-RateLimit headers
# ======================================================

import time
import uuid
import logging
from dataclasses import dataclass
from typing import Optional, Tuple

import redis.asyncio as aioredis
from redis.exceptions import RedisError

from app.cache.redis_client import get_redis_client
from app.core.config import get_settings
from app.core.security import UserTier

logger = logging.getLogger(__name__)


@dataclass
class RateLimitResult:
    """Rate limit evaluation result."""
    allowed: bool
    limit: int
    remaining: int
    reset_seconds: int
    retry_after: int = 0


class SlidingWindowRateLimiter:
    """
    Redis-backed Sliding Window Rate Limiter using Sorted Sets (ZSET).
    """

    def __init__(self, redis_client: Optional[aioredis.Redis] = None):
        self._redis = redis_client
        self.settings = get_settings()

    @property
    def redis(self) -> aioredis.Redis:
        if self._redis is None:
            self._redis = get_redis_client()
        return self._redis

    def get_tier_limit(self, tier: UserTier) -> int:
        """Get the rate limit for a specific user tier."""
        if tier == UserTier.PREMIUM:
            return self.settings.rate_limit_premium
        elif tier == UserTier.FREE:
            return self.settings.rate_limit_free
        else:
            return self.settings.rate_limit_anonymous

    async def is_allowed(
        self,
        identifier: str,
        limit: int,
        window_seconds: int = 60,
    ) -> RateLimitResult:
        """
        Evaluate if a request from `identifier` is within the rate limit.

        Args:
            identifier: Unique client identifier (IP address or API key).
            limit: Maximum allowed requests in the window.
            window_seconds: Window duration in seconds (default: 60s).

        Returns:
            RateLimitResult with decision and header metadata.
        """
        key = f"ratelimit:{identifier}"
        now = time.time()
        window_start = now - window_seconds
        req_id = str(uuid.uuid4())

        try:
            # Use a Redis Pipeline for atomic multi-command execution
            pipe = self.redis.pipeline()

            # 1. Remove old entries outside the current sliding window
            pipe.zremrangebyscore(key, 0, window_start)

            # 2. Count requests currently in the window
            pipe.zcard(key)

            results = await pipe.execute()
            current_count = results[1]

            if current_count < limit:
                # Under limit: Record this request
                pipe2 = self.redis.pipeline()
                pipe2.zadd(key, {req_id: now})
                pipe2.expire(key, window_seconds + 1)
                await pipe2.execute()

                remaining = max(0, limit - (current_count + 1))
                return RateLimitResult(
                    allowed=True,
                    limit=limit,
                    remaining=remaining,
                    reset_seconds=window_seconds,
                    retry_after=0,
                )
            else:
                # Rate limit exceeded: calculate retry-after
                logger.warning(f"[RATE LIMIT EXCEEDED] Identifier: {identifier}, Limit: {limit}/{window_seconds}s")
                return RateLimitResult(
                    allowed=False,
                    limit=limit,
                    remaining=0,
                    reset_seconds=window_seconds,
                    retry_after=window_seconds,
                )

        except (RedisError, Exception) as e:
            # SYSTEM DESIGN CONCEPT: Fail-Open for Reliability
            # If Redis is unavailable, we choose to ALLOW traffic
            # rather than rejecting legitimate users.
            logger.warning(f"[RATE LIMIT ERROR] Redis error, failing open: {e}")
            return RateLimitResult(
                allowed=True,
                limit=limit,
                remaining=limit,
                reset_seconds=window_seconds,
                retry_after=0,
            )
