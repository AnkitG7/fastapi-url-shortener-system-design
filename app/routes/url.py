# ======================================================
# routes/url.py — URL Shortener API Endpoints (with Event-Driven Redirects)
# ======================================================
# SYSTEM DESIGN CONCEPT: Non-Blocking Hot Path
# -------------------------------------------------
# The redirect endpoint is the most critical "hot path" in the system.
# We publish a ClickEvent to the in-memory Event Bus asynchronously
# and return the 307 redirect immediately, with zero DB write latency!
# ======================================================

from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import RedirectResponse

from app.core.config import get_settings
from app.core.security import validate_and_sanitize_url
from app.dependencies import enforce_rate_limit, get_url_service
from app.events.event_bus import ClickEvent, get_event_bus
from app.middleware.auth import AuthenticatedUser
from app.schemas.url import (
    ErrorResponse,
    MessageResponse,
    URLCreateRequest,
    URLResponse,
    URLStatsResponse,
)
from app.services.url_service import (
    ShortCodeConflictError,
    URLExpiredError,
    URLNotFoundError,
    URLService,
)

router = APIRouter(
    prefix="/api/v1",
    tags=["URLs"],
)


def _to_url_response(url_model, base_url: str) -> URLResponse:
    return URLResponse(
        short_code=url_model.short_code,
        original_url=url_model.original_url,
        short_url=f"{base_url}/{url_model.short_code}",
        created_at=url_model.created_at,
        expires_at=url_model.expires_at,
        click_count=url_model.click_count,
    )


def _to_url_stats_response(url_model, base_url: str) -> URLStatsResponse:
    return URLStatsResponse(
        short_code=url_model.short_code,
        original_url=url_model.original_url,
        short_url=f"{base_url}/{url_model.short_code}",
        created_at=url_model.created_at,
        expires_at=url_model.expires_at,
        click_count=url_model.click_count,
        last_clicked_at=url_model.last_clicked_at,
    )


@router.post(
    "/shorten",
    response_model=URLResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a shortened URL (Rate-limited & SSRF-protected)",
    description="Takes a long URL and returns a shortened version. Enforces SSRF checks and tier-based rate limits.",
    responses={
        400: {"model": ErrorResponse, "description": "Invalid URL or SSRF attempt detected"},
        409: {"model": ErrorResponse, "description": "Custom code already taken"},
        429: {"model": ErrorResponse, "description": "Rate limit exceeded"},
    },
)
async def create_short_url(
    request: URLCreateRequest,
    user: AuthenticatedUser = Depends(enforce_rate_limit),
    service: URLService = Depends(get_url_service),
):
    settings = get_settings()

    try:
        sanitized_url = validate_and_sanitize_url(str(request.original_url))
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "detail": str(e),
                "error_code": "INVALID_OR_BLOCKED_URL",
            },
        )

    try:
        url = await service.create_short_url(
            original_url=sanitized_url,
            custom_code=request.custom_code,
            expires_in_hours=request.expires_in_hours,
        )
        return _to_url_response(url, settings.base_url)
    except ShortCodeConflictError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "detail": str(e),
                "error_code": "SHORT_CODE_CONFLICT",
            },
        )


@router.get(
    "/urls/{short_code}",
    response_model=URLStatsResponse,
    summary="Get URL details and stats",
    description="Retrieve details about a shortened URL including click statistics.",
    responses={
        404: {"model": ErrorResponse, "description": "URL not found or expired"},
        429: {"model": ErrorResponse, "description": "Rate limit exceeded"},
    },
)
async def get_url_details(
    short_code: str,
    user: AuthenticatedUser = Depends(enforce_rate_limit),
    service: URLService = Depends(get_url_service),
):
    settings = get_settings()
    try:
        url = await service.get_url(short_code)
        return _to_url_stats_response(url, settings.base_url)
    except URLNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "detail": str(e),
                "error_code": "URL_NOT_FOUND",
            },
        )
    except URLExpiredError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "detail": str(e),
                "error_code": "URL_EXPIRED",
            },
        )


@router.delete(
    "/urls/{short_code}",
    response_model=MessageResponse,
    summary="Delete a shortened URL",
    description="Permanently delete a shortened URL from the database and cache.",
    responses={
        404: {"model": ErrorResponse, "description": "URL not found"},
    },
)
async def delete_url(
    short_code: str,
    service: URLService = Depends(get_url_service),
):
    try:
        await service.delete_url(short_code)
        return MessageResponse(message=f"URL '{short_code}' deleted successfully")
    except URLNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "detail": str(e),
                "error_code": "URL_NOT_FOUND",
            },
        )


@router.get(
    "/urls",
    response_model=list[URLResponse],
    summary="List all shortened URLs",
    description="Retrieve all shortened URLs with pagination.",
    responses={
        429: {"model": ErrorResponse, "description": "Rate limit exceeded"},
    },
)
async def list_urls(
    skip: int = 0,
    limit: int = 10,
    user: AuthenticatedUser = Depends(enforce_rate_limit),
    service: URLService = Depends(get_url_service),
):
    settings = get_settings()
    urls = await service.list_urls(skip=skip, limit=limit)
    return [_to_url_response(url, settings.base_url) for url in urls]


# -------------------------------------------------------
# REDIRECT ROUTER
# -------------------------------------------------------
redirect_router = APIRouter(tags=["Redirect"])


@redirect_router.get(
    "/{short_code}",
    summary="Redirect to original URL (Event-Driven Click Tracking)",
    description="Redirects to destination URL and publishes a click event asynchronously.",
    responses={
        307: {"description": "Temporary redirect to the original URL"},
        404: {"model": ErrorResponse, "description": "URL not found or expired"},
    },
)
async def redirect_to_url(
    short_code: str,
    request: Request,
    service: URLService = Depends(get_url_service),
):
    """
    Execute instant redirect and asynchronously publish telemetry event.
    """
    try:
        original_url = await service.redirect_url(short_code)

        # SYSTEM DESIGN CONCEPT: Asynchronous Telemetry Publishing
        # Non-blocking publish to event bus -> handled by background worker
        event = ClickEvent(
            short_code=short_code,
            timestamp=datetime.now(timezone.utc),
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
            referrer=request.headers.get("referer"),
        )
        event_bus = get_event_bus()
        await event_bus.publish(event)

        return RedirectResponse(
            url=original_url,
            status_code=status.HTTP_307_TEMPORARY_REDIRECT,
        )
    except URLNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "detail": str(e),
                "error_code": "URL_NOT_FOUND",
            },
        )
    except URLExpiredError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "detail": str(e),
                "error_code": "URL_EXPIRED",
            },
        )
