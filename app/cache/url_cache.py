# ======================================================
# cache/url_cache.py — URL Caching & Invalidation
# ======================================================
# SYSTEM DESIGN CONCEPT: Cache-Aside Pattern & TTL
# -------------------------------------------------
# The Cache-Aside (Lazy Loading) pattern is the most
# widely used caching strategy:
#
# 1. READ PATH:
#    - Check Cache for `url:{short_code}`
#    - [Cache Hit]: Return cached object immediately (<1ms)
#    - [Cache Miss]: Read from Database (~5-10ms)
#      -> Store in Cache with TTL
#      -> Return object to user
#
# 2. WRITE/DELETE PATH (Cache Invalidation):
#    - When a URL is updated or deleted in the Database,
#      we MUST DELETE it from the cache.
#    - "There are only two hard things in Computer Science:
#       cache invalidation and naming things." — Phil Karlton
#
# 3. TTL (Time To Live):
#    - Every cache key MUST have a TTL (e.g. 1 hour / 86400s).
#    - Why? If a cache invalidation bug occurs, the stale data
#      will naturally expire rather than staying forever.
#    - Also prevents the cache from running out of memory (OOM).
#
# 4. KEY NAMESPACING:
#    - Keys are prefixed: `url:{short_code}`
#    - In Redis, colons `:` create logical hierarchy/namespaces.
# ======================================================

import json
import logging
from datetime import datetime
from typing import Any, Optional

import redis.asyncio as aioredis
from redis.exceptions import RedisError

from app.cache.redis_client import get_redis_client

logger = logging.getLogger(__name__)

# Default Cache Time-To-Live: 24 hours (in seconds)
DEFAULT_CACHE_TTL_SECONDS = 86400


class URLCache:
    """
    Cache manager for URL lookups implementing the Cache-Aside pattern.
    """

    def __init__(self, redis_client: Optional[aioredis.Redis] = None):
        """
        Initialize with a Redis client (allows injection of mock/fake in tests).
        """
        self._redis = redis_client

    @property
    def redis(self) -> aioredis.Redis:
        if self._redis is None:
            self._redis = get_redis_client()
        return self._redis

    def _make_key(self, short_code: str) -> str:
        """Namespace cache keys to avoid collision with other services/domains."""
        return f"url:{short_code}"

    async def get(self, short_code: str) -> Optional[dict[str, Any]]:
        """
        Retrieve cached URL data.

        Returns:
            dict with URL data if Cache Hit, None if Cache Miss or Redis is down.
        """
        key = self._make_key(short_code)
        try:
            cached_val = await self.redis.get(key)
            if cached_val is not None:
                logger.debug(f"[CACHE HIT] Key: {key}")
                data = json.loads(cached_val)
                # Parse datetime strings back into ISO objects if needed
                return data
            logger.debug(f"[CACHE MISS] Key: {key}")
            return None
        except (RedisError, Exception) as e:
            # SYSTEM DESIGN CONCEPT: Graceful Degradation
            # If Redis fails, log warning and return None (fall back to DB)
            logger.warning(f"[CACHE ERROR] Failed to read key '{key}' from Redis: {e}")
            return None

    async def set(
        self,
        short_code: str,
        data: dict[str, Any],
        ttl_seconds: int = DEFAULT_CACHE_TTL_SECONDS,
    ) -> bool:
        """
        Store URL data in cache with a TTL (Time To Live).
        """
        key = self._make_key(short_code)
        try:
            # Convert datetime objects to ISO strings for JSON serialization
            serialized_data = {}
            for k, v in data.items():
                if isinstance(v, datetime):
                    serialized_data[k] = v.isoformat()
                else:
                    serialized_data[k] = v

            payload = json.dumps(serialized_data)
            await self.redis.set(key, payload, ex=ttl_seconds)
            logger.debug(f"[CACHE SET] Key: {key} with TTL: {ttl_seconds}s")
            return True
        except (RedisError, Exception) as e:
            logger.warning(f"[CACHE ERROR] Failed to set key '{key}' in Redis: {e}")
            return False

    async def delete(self, short_code: str) -> bool:
        """
        SYSTEM DESIGN CONCEPT: Cache Invalidation
        ------------------------------------------
        Delete key from cache when the underlying resource is
        deleted or modified in PostgreSQL.
        """
        key = self._make_key(short_code)
        try:
            await self.redis.delete(key)
            logger.debug(f"[CACHE INVALIDATED] Key: {key}")
            return True
        except (RedisError, Exception) as e:
            logger.warning(f"[CACHE ERROR] Failed to delete key '{key}' from Redis: {e}")
            return False
