# ======================================================
# services/url_service.py — Business Logic Layer (with Caching)
# ======================================================
# SYSTEM DESIGN CONCEPT: Cache-Aside in the Service Layer
# -------------------------------------------------
# The service layer orchestrates both the Cache (Fast Read Layer)
# and the Repository (Durable Storage Layer):
#
# Read Flow:
#   Request -> Check Cache -> [HIT] -> Return data (<1ms)
#                          -> [MISS] -> Query DB -> Populate Cache -> Return data
#
# Write / Delete Flow:
#   Delete -> Delete from DB -> Invalidate Cache (Delete key)
# ======================================================

from datetime import datetime, timedelta, timezone
from typing import Optional

import shortuuid

from app.cache.url_cache import URLCache
from app.core.config import get_settings
from app.db.models import URL
from app.repositories.url_repository import URLRepository


class URLService:
    """
    Business logic for URL operations, integrating Cache-Aside & DB persistence.
    """

    def __init__(
        self,
        repository: URLRepository,
        cache: Optional[URLCache] = None,
    ):
        """
        Receives repository and optional cache via Dependency Injection.
        """
        self.repository = repository
        self.cache = cache or URLCache()
        self.settings = get_settings()

    async def create_short_url(
        self,
        original_url: str,
        custom_code: Optional[str] = None,
        expires_in_hours: Optional[int] = None,
    ) -> URL:
        """
        Create a new shortened URL.
        """
        if custom_code:
            if await self.repository.short_code_exists(custom_code):
                raise ShortCodeConflictError(custom_code)
            short_code = custom_code
        else:
            short_code = await self._generate_unique_code()

        expires_at = None
        if expires_in_hours:
            expires_at = datetime.now(timezone.utc) + timedelta(hours=expires_in_hours)

        url = URL(
            short_code=short_code,
            original_url=original_url,
            expires_at=expires_at,
        )

        created_url = await self.repository.create(url)

        # Pre-warm the cache (Write-Through optimization)
        await self.cache.set(
            short_code=created_url.short_code,
            data={
                "short_code": created_url.short_code,
                "original_url": created_url.original_url,
                "created_at": created_url.created_at,
                "expires_at": created_url.expires_at,
                "click_count": created_url.click_count,
            },
        )

        return created_url

    async def get_url(self, short_code: str) -> URL:
        """
        Retrieve URL details with Cache-Aside pattern.
        """
        # 1. Check Cache first
        cached = await self.cache.get(short_code)
        if cached:
            # Reconstruct URL object or check expiration
            expires_at_str = cached.get("expires_at")
            if expires_at_str:
                exp_dt = datetime.fromisoformat(expires_at_str)
                if exp_dt < datetime.now(timezone.utc):
                    await self.cache.delete(short_code)
                    raise URLExpiredError(short_code)

        # 2. On Cache Miss, fetch from DB
        url = await self.repository.get_by_short_code(short_code)

        if url is None:
            raise URLNotFoundError(short_code)

        if url.is_expired():
            await self.cache.delete(short_code)
            raise URLExpiredError(short_code)

        # 3. Populate Cache on Miss
        await self.cache.set(
            short_code=url.short_code,
            data={
                "short_code": url.short_code,
                "original_url": url.original_url,
                "created_at": url.created_at,
                "expires_at": url.expires_at,
                "click_count": url.click_count,
            },
        )

        return url

    async def redirect_url(self, short_code: str) -> str:
        """
        Execute redirect with Cache-Aside optimization.
        """
        cached = await self.cache.get(short_code)
        if cached:
            # Check expiration in cache
            expires_at_str = cached.get("expires_at")
            if expires_at_str:
                exp_dt = datetime.fromisoformat(expires_at_str)
                if exp_dt < datetime.now(timezone.utc):
                    await self.cache.delete(short_code)
                    await self.repository.delete_by_short_code(short_code)
                    raise URLExpiredError(short_code)

            # Atomic increment in database (non-blocking in Phase 5)
            await self.repository.increment_click(short_code)
            return cached["original_url"]

        # Cache Miss: fallback to DB
        url = await self.repository.get_by_short_code(short_code)

        if url is None:
            raise URLNotFoundError(short_code)

        if url.is_expired():
            await self.cache.delete(short_code)
            await self.repository.delete_by_short_code(short_code)
            raise URLExpiredError(short_code)

        # Store in cache for future redirects
        await self.cache.set(
            short_code=url.short_code,
            data={
                "short_code": url.short_code,
                "original_url": url.original_url,
                "created_at": url.created_at,
                "expires_at": url.expires_at,
                "click_count": url.click_count,
            },
        )

        await self.repository.increment_click(short_code)
        return url.original_url

    async def list_urls(self, skip: int = 0, limit: int = 10) -> list[URL]:
        """List URLs with pagination."""
        limit = min(limit, 100)
        return await self.repository.get_all(skip=skip, limit=limit)

    async def delete_url(self, short_code: str) -> bool:
        """
        Delete URL and invalidate cache.
        """
        deleted = await self.repository.delete_by_short_code(short_code)
        if not deleted:
            raise URLNotFoundError(short_code)

        # SYSTEM DESIGN CONCEPT: Cache Invalidation
        await self.cache.delete(short_code)
        return True

    async def _generate_unique_code(self) -> str:
        """Generate unique code with collision checking."""
        for _ in range(10):
            code = shortuuid.uuid()[:self.settings.short_code_length]
            if not await self.repository.short_code_exists(code):
                return code

        raise RuntimeError("Failed to generate unique short code after 10 attempts")


class URLNotFoundError(Exception):
    """Raised when a URL with the given short code doesn't exist."""
    def __init__(self, short_code: str):
        self.short_code = short_code
        super().__init__(f"URL with code '{short_code}' not found")


class URLExpiredError(Exception):
    """Raised when a URL has expired."""
    def __init__(self, short_code: str):
        self.short_code = short_code
        super().__init__(f"URL with code '{short_code}' has expired")


class ShortCodeConflictError(Exception):
    """Raised when a custom short code is already taken."""
    def __init__(self, short_code: str):
        self.short_code = short_code
        super().__init__(f"Short code '{short_code}' is already taken")
