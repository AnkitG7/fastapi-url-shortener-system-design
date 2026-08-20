# ======================================================
# routes/url.py — URL Shortener API Endpoints
# ======================================================
# SYSTEM DESIGN CONCEPT: RESTful API Design
# -------------------------------------------------
# REST (Representational State Transfer) is an
# architectural style for designing APIs. Key principles:
#
# 1. RESOURCES — Everything is a "resource" (URL, User, etc.)
# 2. HTTP VERBS — Use the right verb for the right action:
#    - POST   = Create a new resource
#    - GET    = Read/retrieve a resource
#    - PUT    = Update (replace) a resource
#    - DELETE = Remove a resource
# 3. STATUS CODES — Tell the client WHAT HAPPENED:
#    - 200 OK          = Success
#    - 201 Created     = New resource created
#    - 301 Redirect    = Permanent redirect
#    - 307 Redirect    = Temporary redirect
#    - 400 Bad Request = Client sent invalid data
#    - 404 Not Found   = Resource doesn't exist
#    - 409 Conflict    = Resource already exists
#    - 429 Too Many    = Rate limited
#
# WHY DOES THIS MATTER?
# When you design systems at scale, EVERY team uses your
# API. If your API is inconsistent or confusing, you'll
# spend more time answering questions than writing code.
# A well-designed API is self-documenting.
# ======================================================

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import RedirectResponse
from datetime import datetime, timedelta, timezone
from typing import Optional

import shortuuid

from app.schemas.url import (
    URLCreateRequest,
    URLResponse,
    URLStatsResponse,
    ErrorResponse,
    MessageResponse,
)
from app.core.config import get_settings

# -------------------------------------------------------
# SYSTEM DESIGN CONCEPT: API Router / Modularization
# -------------------------------------------------------
# In any real system, you DON'T put all endpoints in one
# file. You split them by DOMAIN (urls, users, analytics).
#
# FastAPI's APIRouter is like a "mini app" that gets
# mounted onto the main app. This is the same concept as:
# - Django: urlpatterns per app
# - Express.js: Router()
# - Spring Boot: @RestController per domain
#
# WHY? Because when your app has 200 endpoints, you need
# ORGANIZATION. Each team owns their own router.
# -------------------------------------------------------

router = APIRouter(
    prefix="/api/v1",   # All routes start with /api/v1
    tags=["URLs"],      # Groups endpoints in Swagger docs
)

# -------------------------------------------------------
# IN-MEMORY STORAGE (Phase 1 only)
# -------------------------------------------------------
# We'll replace this with a real database in Phase 2.
# For now, a simple dictionary lets us focus on API design
# without database complexity.
#
# TRADEOFF: Simple but NOT production-ready because:
# 1. Data is lost when the server restarts
# 2. Can't be shared across multiple server instances
# 3. No ACID transactions
# 4. No querying capability
#
# This is intentional — we learn ONE concept at a time.
# -------------------------------------------------------

url_store: dict[str, dict] = {}


def generate_short_code() -> str:
    """
    Generate a unique short code.

    SYSTEM DESIGN CONCEPT: ID Generation
    ------------------------------------
    At scale, generating unique IDs is a REAL problem.
    Options include:
    1. Auto-increment (simple, but predictable & not distributed)
    2. UUID (unique, but too long — 36 chars)
    3. ShortUUID (unique & short — what we use here)
    4. Snowflake IDs (Twitter's approach — time-ordered, distributed)
    5. Hash-based (MD5/SHA of URL — risk of collisions)

    We use ShortUUID because it gives us short, URL-safe,
    unique strings. In Phase 2, we'll add collision checking
    against the database.
    """
    settings = get_settings()
    return shortuuid.uuid()[:settings.short_code_length]


# -------------------------------------------------------
# ENDPOINT 1: CREATE a short URL
# -------------------------------------------------------
# HTTP Method: POST (because we're CREATING a new resource)
# Why not GET? Because GET should be IDEMPOTENT (same request
# = same result). Creating a new URL is NOT idempotent.
# -------------------------------------------------------

@router.post(
    "/shorten",
    response_model=URLResponse,
    status_code=status.HTTP_201_CREATED,  # 201 = "I created something new"
    summary="Create a shortened URL",
    description="Takes a long URL and returns a shortened version.",
    responses={
        409: {"model": ErrorResponse, "description": "Custom code already taken"},
    },
)
async def create_short_url(request: URLCreateRequest):
    """
    Create a new shortened URL.

    SYSTEM DESIGN CONCEPTS demonstrated here:
    1. INPUT VALIDATION — Pydantic validates the request automatically
    2. CONFLICT DETECTION — Check if custom code already exists (409)
    3. RESOURCE CREATION — Generate ID, store data, return 201
    4. RESPONSE SHAPING — Return only what the client needs
    """
    settings = get_settings()

    # --- Handle custom short code ---
    if request.custom_code:
        # Check for conflicts (idempotency concern)
        if request.custom_code in url_store:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "detail": f"Short code '{request.custom_code}' is already taken",
                    "error_code": "SHORT_CODE_CONFLICT",
                },
            )
        short_code = request.custom_code
    else:
        # Generate a unique code
        # In production, you'd retry on collision
        short_code = generate_short_code()
        while short_code in url_store:
            short_code = generate_short_code()

    # --- Calculate expiration ---
    now = datetime.now(timezone.utc)
    expires_at = None
    if request.expires_in_hours:
        expires_at = now + timedelta(hours=request.expires_in_hours)

    # --- Store the URL ---
    url_data = {
        "short_code": short_code,
        "original_url": str(request.original_url),
        "short_url": f"{settings.base_url}/{short_code}",
        "created_at": now,
        "expires_at": expires_at,
        "click_count": 0,
        "last_clicked_at": None,
    }
    url_store[short_code] = url_data

    return URLResponse(**url_data)


# -------------------------------------------------------
# ENDPOINT 2: REDIRECT — The core functionality
# -------------------------------------------------------
# This is mounted on the MAIN app (not the router) because
# short URLs should be as short as possible:
#   http://localhost:8000/abc1234
# NOT:
#   http://localhost:8000/api/v1/abc1234
#
# We'll set this up in main.py with a separate router.
# -------------------------------------------------------
# (See redirect_router below)


# -------------------------------------------------------
# ENDPOINT 3: GET URL details
# -------------------------------------------------------
# HTTP Method: GET (reading/retrieving data)
# This is IDEMPOTENT — calling it 100 times returns the
# same result (unlike POST which creates new resources).
# -------------------------------------------------------

@router.get(
    "/urls/{short_code}",
    response_model=URLStatsResponse,
    summary="Get URL details and stats",
    description="Retrieve details about a shortened URL including click statistics.",
    responses={
        404: {"model": ErrorResponse, "description": "URL not found"},
    },
)
async def get_url_details(short_code: str):
    """
    Get details about a shortened URL.

    SYSTEM DESIGN CONCEPT: Path Parameters vs Query Parameters
    ---------------------------------------------------------
    - PATH parameters (/urls/{id}) = identify a SPECIFIC resource
    - QUERY parameters (/urls?page=1) = filter/sort/paginate

    We use a path parameter here because we're asking for
    ONE SPECIFIC URL, identified by its short_code.
    """
    if short_code not in url_store:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "detail": f"URL with code '{short_code}' not found",
                "error_code": "URL_NOT_FOUND",
            },
        )

    url_data = url_store[short_code]

    # Check if expired
    if url_data["expires_at"] and url_data["expires_at"] < datetime.now(timezone.utc):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "detail": "This URL has expired",
                "error_code": "URL_EXPIRED",
            },
        )

    return URLStatsResponse(**url_data)


# -------------------------------------------------------
# ENDPOINT 4: DELETE a URL
# -------------------------------------------------------
# HTTP Method: DELETE (removing a resource)
# Returns 200 with a message, or 404 if not found.
#
# DESIGN DECISION: Soft delete vs Hard delete
# In production, you'd usually SOFT DELETE (set a flag)
# instead of actually removing data. This allows:
# 1. Recovery from accidental deletes
# 2. Audit trails
# 3. Analytics on deleted URLs
# We'll use hard delete for simplicity in Phase 1.
# -------------------------------------------------------

@router.delete(
    "/urls/{short_code}",
    response_model=MessageResponse,
    summary="Delete a shortened URL",
    description="Permanently delete a shortened URL.",
    responses={
        404: {"model": ErrorResponse, "description": "URL not found"},
    },
)
async def delete_url(short_code: str):
    """Delete a shortened URL."""
    if short_code not in url_store:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "detail": f"URL with code '{short_code}' not found",
                "error_code": "URL_NOT_FOUND",
            },
        )

    del url_store[short_code]
    return MessageResponse(message=f"URL '{short_code}' deleted successfully")


# -------------------------------------------------------
# ENDPOINT 5: LIST all URLs (with pagination)
# -------------------------------------------------------
# SYSTEM DESIGN CONCEPT: Pagination
# -------------------------------------------------
# NEVER return ALL records in a single response because:
# 1. Memory — 1 million URLs in one response = OOM
# 2. Latency — Client waits forever for huge payloads
# 3. Bandwidth — Wastes network resources
#
# Common pagination strategies:
# 1. OFFSET-BASED: ?page=2&size=10 (simple, but slow for deep pages)
# 2. CURSOR-BASED: ?after=abc123 (better for large datasets)
# 3. KEYSET: ?created_after=2024-01-01 (good for time-series)
#
# We use offset-based for simplicity. In Phase 2 with a
# real database, we'll discuss cursor-based pagination.
# -------------------------------------------------------

@router.get(
    "/urls",
    response_model=list[URLResponse],
    summary="List all shortened URLs",
    description="Retrieve all shortened URLs with pagination.",
)
async def list_urls(
    skip: int = 0,     # Offset — how many to skip
    limit: int = 10,   # Page size — how many to return (max 100)
):
    """
    List all shortened URLs with pagination.

    DESIGN DECISION: Default limit = 10, not unlimited
    Because "SELECT * FROM urls" with 1 million rows
    would crash both the server and the client.
    """
    # Cap the limit to prevent abuse
    limit = min(limit, 100)

    urls = list(url_store.values())
    paginated = urls[skip: skip + limit]

    return [URLResponse(**url) for url in paginated]


# -------------------------------------------------------
# REDIRECT ROUTER — Separate from API routes
# -------------------------------------------------------
# This handles the actual redirect: GET /{short_code}
# It's on a separate router with NO prefix so the URL
# stays short: http://localhost:8000/abc1234
# -------------------------------------------------------

redirect_router = APIRouter(tags=["Redirect"])


@redirect_router.get(
    "/{short_code}",
    summary="Redirect to original URL",
    description="Redirects to the original URL associated with the short code.",
    responses={
        307: {"description": "Temporary redirect to the original URL"},
        404: {"model": ErrorResponse, "description": "URL not found or expired"},
    },
)
async def redirect_to_url(short_code: str):
    """
    Redirect a short URL to its original destination.

    SYSTEM DESIGN CONCEPT: 301 vs 307 Redirects
    --------------------------------------------
    - 301 (Permanent): Browser CACHES the redirect. Next time,
      the browser goes directly to the original URL without
      hitting our server. Good for SEO, bad for analytics.

    - 307 (Temporary): Browser ALWAYS hits our server first.
      This means we can COUNT every click. Good for analytics,
      slightly slower.

    We use 307 because click tracking is a core feature.
    Services like bit.ly also use 307 for the same reason.

    TRADEOFF: Latency (extra hop) vs Analytics (click counting)
    In Phase 5, we'll make click counting async so the
    redirect is fast AND we still get analytics.
    """
    if short_code not in url_store:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "detail": f"URL with code '{short_code}' not found",
                "error_code": "URL_NOT_FOUND",
            },
        )

    url_data = url_store[short_code]

    # Check expiration
    if url_data["expires_at"] and url_data["expires_at"] < datetime.now(timezone.utc):
        # Clean up expired URL
        del url_store[short_code]
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "detail": "This URL has expired",
                "error_code": "URL_EXPIRED",
            },
        )

    # Update click count (synchronous for now — async in Phase 5)
    url_data["click_count"] += 1
    url_data["last_clicked_at"] = datetime.now(timezone.utc)

    # 307 Temporary Redirect
    return RedirectResponse(
        url=url_data["original_url"],
        status_code=status.HTTP_307_TEMPORARY_REDIRECT,
    )
