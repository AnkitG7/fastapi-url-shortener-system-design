# ======================================================
# routes/url.py — URL Shortener API Endpoints (DB-backed)
# ======================================================
# SYSTEM DESIGN CONCEPT: Clean Architecture Route Handlers
# -------------------------------------------------
# With the Service and Repository layers in place:
# 1. Routes are THIN — they only handle HTTP concerns:
#    - Receiving and validating JSON payloads
#    - Catching Domain Exceptions & translating to HTTP Status Codes
#    - Returning standardized Pydantic responses
# 2. All business logic lives in URLService.
# 3. All SQL/persistence lives in URLRepository.
# ======================================================

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import RedirectResponse

from app.core.config import get_settings
from app.dependencies import get_url_service
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
    """Helper to convert ORM model to Pydantic URLResponse schema."""
    return URLResponse(
        short_code=url_model.short_code,
        original_url=url_model.original_url,
        short_url=f"{base_url}/{url_model.short_code}",
        created_at=url_model.created_at,
        expires_at=url_model.expires_at,
        click_count=url_model.click_count,
    )


def _to_url_stats_response(url_model, base_url: str) -> URLStatsResponse:
    """Helper to convert ORM model to Pydantic URLStatsResponse schema."""
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
    summary="Create a shortened URL",
    description="Takes a long URL and returns a shortened version persisted in the database.",
    responses={
        409: {"model": ErrorResponse, "description": "Custom code already taken"},
    },
)
async def create_short_url(
    request: URLCreateRequest,
    service: URLService = Depends(get_url_service),
):
    """Create a new shortened URL using the business service layer."""
    settings = get_settings()
    try:
        url = await service.create_short_url(
            original_url=str(request.original_url),
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
    description="Retrieve details about a shortened URL including click statistics from DB.",
    responses={
        404: {"model": ErrorResponse, "description": "URL not found or expired"},
    },
)
async def get_url_details(
    short_code: str,
    service: URLService = Depends(get_url_service),
):
    """Retrieve details and statistics for a given short code."""
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
    description="Permanently delete a shortened URL from the database.",
    responses={
        404: {"model": ErrorResponse, "description": "URL not found"},
    },
)
async def delete_url(
    short_code: str,
    service: URLService = Depends(get_url_service),
):
    """Delete a shortened URL record."""
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
)
async def list_urls(
    skip: int = 0,
    limit: int = 10,
    service: URLService = Depends(get_url_service),
):
    """List URLs with offset-based pagination."""
    settings = get_settings()
    urls = await service.list_urls(skip=skip, limit=limit)
    return [_to_url_response(url, settings.base_url) for url in urls]


# -------------------------------------------------------
# REDIRECT ROUTER
# -------------------------------------------------------
redirect_router = APIRouter(tags=["Redirect"])


@redirect_router.get(
    "/{short_code}",
    summary="Redirect to original URL",
    description="Redirects to the original URL associated with the short code and increments click count.",
    responses={
        307: {"description": "Temporary redirect to the original URL"},
        404: {"model": ErrorResponse, "description": "URL not found or expired"},
    },
)
async def redirect_to_url(
    short_code: str,
    service: URLService = Depends(get_url_service),
):
    """Execute redirection and atomic click counter increment in DB."""
    try:
        original_url = await service.redirect_url(short_code)
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
