# ======================================================
# services/url_service.py — Business Logic Layer
# ======================================================
# SYSTEM DESIGN CONCEPT: Service Layer / Use Cases
# -------------------------------------------------
# The Service layer sits BETWEEN routes and repositories:
#
#   Route (HTTP) → Service (Logic) → Repository (Data)
#
# Each layer has a SINGLE RESPONSIBILITY:
# - Route:      Handle HTTP (parse request, format response)
# - Service:    Business rules (validate, transform, orchestrate)
# - Repository: Data access (CRUD operations)
#
# WHY NOT put business logic in the route handler?
# Because business rules should be REUSABLE:
# - The same "create URL" logic might be called from:
#   1. REST API endpoint
#   2. CLI tool
#   3. Background job
#   4. GraphQL resolver
#
# If logic is in the route, you'd have to duplicate it.
# In the service layer, all entry points share it.
#
# SYSTEM DESIGN CONCEPT: Clean Architecture
# -------------------------------------------------
# This layering is from Clean Architecture / Hexagonal
# Architecture. The key rule is:
#
#   DEPENDENCIES POINT INWARD
#   Route → Service → Repository → Database
#   (outer layers know about inner, not vice versa)
#
# The Service doesn't know about HTTP (no Request/Response).
# The Repository doesn't know about business rules.
# This makes each layer independently testable.
# ======================================================

from datetime import datetime, timedelta, timezone
from typing import Optional

import shortuuid

from app.core.config import get_settings
from app.db.models import URL
from app.repositories.url_repository import URLRepository


class URLService:
    """
    Business logic for URL operations.

    This class ORCHESTRATES the workflow:
    1. Validate business rules
    2. Transform data
    3. Call repository for persistence
    4. Return results

    It does NOT know about HTTP, JSON, or Pydantic schemas.
    """

    def __init__(self, repository: URLRepository):
        """
        Receives repository via Dependency Injection.

        The service doesn't CREATE the repository — it
        receives one. In tests, we can pass a mock repository.
        """
        self.repository = repository
        self.settings = get_settings()

    async def create_short_url(
        self,
        original_url: str,
        custom_code: Optional[str] = None,
        expires_in_hours: Optional[int] = None,
    ) -> URL:
        """
        Create a new shortened URL.

        BUSINESS RULES (enforced here, not in repository):
        1. Custom codes must not conflict with existing ones
        2. Auto-generated codes must be unique
        3. Expiration is optional
        """
        # --- Determine short code ---
        if custom_code:
            # Check if custom code is already taken
            if await self.repository.short_code_exists(custom_code):
                raise ShortCodeConflictError(custom_code)
            short_code = custom_code
        else:
            short_code = await self._generate_unique_code()

        # --- Calculate expiration ---
        expires_at = None
        if expires_in_hours:
            expires_at = datetime.now(timezone.utc) + timedelta(hours=expires_in_hours)

        # --- Create URL entity ---
        url = URL(
            short_code=short_code,
            original_url=original_url,
            expires_at=expires_at,
        )

        return await self.repository.create(url)

    async def get_url(self, short_code: str) -> URL:
        """
        Get URL details, raising if not found or expired.

        BUSINESS RULE: Expired URLs are treated as non-existent.
        """
        url = await self.repository.get_by_short_code(short_code)

        if url is None:
            raise URLNotFoundError(short_code)

        if url.is_expired():
            raise URLExpiredError(short_code)

        return url

    async def redirect_url(self, short_code: str) -> str:
        """
        Get the original URL for redirect AND track the click.

        Returns the original URL string.

        BUSINESS RULES:
        1. URL must exist
        2. URL must not be expired
        3. Click count is incremented atomically
        """
        url = await self.repository.get_by_short_code(short_code)

        if url is None:
            raise URLNotFoundError(short_code)

        if url.is_expired():
            # Clean up expired URL
            await self.repository.delete_by_short_code(short_code)
            raise URLExpiredError(short_code)

        # Atomic click increment
        await self.repository.increment_click(short_code)

        return url.original_url

    async def list_urls(self, skip: int = 0, limit: int = 10) -> list[URL]:
        """List URLs with pagination, capping limit at 100."""
        limit = min(limit, 100)
        return await self.repository.get_all(skip=skip, limit=limit)

    async def delete_url(self, short_code: str) -> bool:
        """
        Delete a URL by short code.

        Returns True if deleted, raises if not found.
        """
        deleted = await self.repository.delete_by_short_code(short_code)
        if not deleted:
            raise URLNotFoundError(short_code)
        return True

    async def _generate_unique_code(self) -> str:
        """
        Generate a short code that doesn't exist in the DB.

        SYSTEM DESIGN CONCEPT: Collision Handling
        -----------------------------------------
        ShortUUID with 7 chars gives ~3.5 trillion combos.
        Collision probability is LOW but NOT ZERO.

        Strategy: Generate → Check DB → Retry if exists.

        At small scale (< 1M URLs), collisions are extremely
        rare. At massive scale, you'd use:
        1. Pre-generated ID pools
        2. Snowflake-style distributed IDs
        3. Counter-based encoding (Base62)

        We cap retries at 10 to prevent infinite loops
        (if pool is somehow exhausted).
        """
        for _ in range(10):
            code = shortuuid.uuid()[:self.settings.short_code_length]
            if not await self.repository.short_code_exists(code):
                return code

        raise RuntimeError("Failed to generate unique short code after 10 attempts")


# ======================================================
# CUSTOM EXCEPTIONS — Domain-Specific Errors
# ======================================================
# SYSTEM DESIGN CONCEPT: Domain Exceptions
# -------------------------------------------------
# Instead of raising generic HTTPException in the service
# layer, we raise DOMAIN exceptions (URLNotFoundError, etc.)
#
# WHY? Because the service doesn't know about HTTP.
# The route handler CATCHES these and converts them to
# the appropriate HTTP response (404, 409, etc.)
#
# This keeps the service layer TRANSPORT-AGNOSTIC:
# - REST API: Convert to HTTP 404
# - CLI: Print "URL not found"
# - GraphQL: Return error in errors array
# ======================================================

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
