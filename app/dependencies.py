# ======================================================
# dependencies.py — Dependency Injection Providers
# ======================================================
# SYSTEM DESIGN CONCEPT: Composability of Dependencies
# -------------------------------------------------
# FastAPI dependencies can depend on other dependencies:
# Request -> get_authenticated_user -> check_rate_limit -> Route Handler
# ======================================================

from typing import Optional
from fastapi import Depends, Header, HTTPException, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.cache.url_cache import URLCache
from app.db.database import get_db
from app.middleware.auth import AuthenticatedUser, authenticate_api_key
from app.middleware.rate_limiter import SlidingWindowRateLimiter
from app.repositories.url_repository import URLRepository
from app.services.url_service import URLService


async def get_url_cache() -> URLCache:
    """Provide a URLCache instance."""
    return URLCache()


async def get_rate_limiter() -> SlidingWindowRateLimiter:
    """Provide a SlidingWindowRateLimiter instance."""
    return SlidingWindowRateLimiter()


async def get_url_repository(
    db: AsyncSession = Depends(get_db),
) -> URLRepository:
    """Provide a URLRepository instance bound to the request's DB session."""
    return URLRepository(session=db)


async def get_url_service(
    repository: URLRepository = Depends(get_url_repository),
    cache: URLCache = Depends(get_url_cache),
) -> URLService:
    """Provide a URLService instance with injected repository and cache."""
    return URLService(repository=repository, cache=cache)


async def get_authenticated_user(
    request: Request,
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
) -> AuthenticatedUser:
    """
    Extract client IP and API key to resolve AuthenticatedUser context.
    """
    client_ip = request.client.host if request.client else "127.0.0.1"
    return authenticate_api_key(api_key=x_api_key, client_ip=client_ip)


async def enforce_rate_limit(
    response: Response,
    user: AuthenticatedUser = Depends(get_authenticated_user),
    limiter: SlidingWindowRateLimiter = Depends(get_rate_limiter),
) -> AuthenticatedUser:
    """
    SYSTEM DESIGN CONCEPT: Rate Limiting Enforcement & Headers
    ----------------------------------------------------------
    Enforces sliding window rate limit for the current user tier.
    Appends standard RFC RateLimit headers to the response:
    - X-RateLimit-Limit
    - X-RateLimit-Remaining
    - X-RateLimit-Reset
    - Retry-After (on 429)
    """
    limit = limiter.get_tier_limit(user.tier)
    result = await limiter.is_allowed(identifier=user.identifier, limit=limit)

    # Set RFC RateLimit headers on successful responses
    response.headers["X-RateLimit-Limit"] = str(result.limit)
    response.headers["X-RateLimit-Remaining"] = str(result.remaining)
    response.headers["X-RateLimit-Reset"] = str(result.reset_seconds)

    if not result.allowed:
        # Pass headers directly into HTTPException so they are rendered on 429 responses
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "detail": f"Rate limit exceeded for tier '{user.tier.value}'. Limit: {result.limit} req/min.",
                "error_code": "RATE_LIMIT_EXCEEDED",
                "retry_after_seconds": result.retry_after,
            },
            headers={
                "Retry-After": str(result.retry_after),
                "X-RateLimit-Limit": str(result.limit),
                "X-RateLimit-Remaining": "0",
                "X-RateLimit-Reset": str(result.reset_seconds),
            },
        )

    return user
