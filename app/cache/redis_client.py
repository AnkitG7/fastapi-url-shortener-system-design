# ======================================================
# cache/redis_client.py — Redis Client & Connection Management
# ======================================================
# SYSTEM DESIGN CONCEPT: Caching & Graceful Degradation
# -------------------------------------------------
# In distributed systems, a cache is an OPTIMIZATION, not
# the single source of truth.
#
# CRITICAL SYSTEM DESIGN PRINCIPLE:
# "If your cache dies, your system should get SLOWER,
#  NOT crash."
#
# This is called GRACEFUL DEGRADATION:
# 1. When Redis is healthy → Serve responses from cache (sub-millisecond)
# 2. When Redis is down → Fall back to querying PostgreSQL directly
# 3. Log the cache failure as a warning, but keep serving user requests!
#
# REDIS CONNECTION POOLING:
# Just like database connections, creating TCP connections to
# Redis per request is inefficient. We use a Redis ConnectionPool
# to reuse open connections.
# ======================================================

import logging
from typing import Optional
import redis.asyncio as aioredis
from redis.asyncio.connection import ConnectionPool

from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

# Global connection pool for Redis
_redis_pool: Optional[ConnectionPool] = None


def get_redis_pool() -> ConnectionPool:
    """
    SYSTEM DESIGN CONCEPT: Singleton Connection Pool
    ------------------------------------------------
    Maintain a single global connection pool for Redis
    across the entire application lifecycle.
    """
    global _redis_pool
    if _redis_pool is None:
        _redis_pool = ConnectionPool.from_url(
            settings.redis_url,
            max_connections=20,     # Max simultaneous connections in pool
            decode_responses=True,   # Automatically decode bytes to strings (UTF-8)
            socket_timeout=2.0,      # Max 2 seconds to wait on socket operations
            socket_connect_timeout=2.0, # Max 2 seconds to establish connection
        )
    return _redis_pool


def get_redis_client() -> aioredis.Redis:
    """
    Get an async Redis client from the shared connection pool.
    """
    pool = get_redis_pool()
    return aioredis.Redis(connection_pool=pool)


async def close_redis_pool() -> None:
    """Gracefully close all open connections in the Redis pool on app shutdown."""
    global _redis_pool
    if _redis_pool is not None:
        await _redis_pool.disconnect()
        _redis_pool = None
        logger.info("[REDIS] Redis connection pool closed.")


async def check_redis_health() -> bool:
    """
    Health check to verify if Redis is reachable and responding.
    Returns True if healthy, False if down.
    """
    try:
        client = get_redis_client()
        response = await client.ping()
        return response is True
    except Exception as e:
        logger.warning(f"[REDIS] Health check failed: {e}")
        return False
